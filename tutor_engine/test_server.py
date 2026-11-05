"""Regresiones de integridad del motor, sin descargar ni aprobar modelos."""
import hashlib
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODULES = (("guard", "ai_tutor/services/output_guard.py"), ("classifier_runtime", "ai_tutor/ml/runtime.py"),
           ("bounded_http", "utils/bounded_http.py"), ("tutor_prompt", "ai_tutor/ml/prompt.py"), ("tutor_server", "tutor_engine/server.py"))
for module, file in MODULES:
    spec = importlib.util.spec_from_file_location(module, ROOT / file)
    instance = importlib.util.module_from_spec(spec)
    sys.modules[module] = instance
    spec.loader.exec_module(instance)
server = sys.modules["tutor_server"]
# Sin manejador propio, logging imprimiría en stderr cada rechazo que las pruebas provocan a propósito.
logging.getLogger("tutor_engine").addHandler(logging.NullHandler())


class IntegrityTests(unittest.TestCase):
    def test_technical_artifact_is_rejected_by_default_and_requires_synthetic_classifier(self):
        with TemporaryDirectory() as temp:
            old_root = server.ROOT
            self.addCleanup(setattr, server, "ROOT", old_root)
            server.ROOT = Path(temp)
            (server.ROOT / "model.gguf").write_bytes(b"fixture-not-a-real-model")
            classifier = server.ROOT / "classifier.json"
            classifier.write_text(json.dumps({"dataset_version": "fixture", "scope": "technical-demo"}))

            def entry(path):
                return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {"scope": "technical-demo", "decision": "demonstration", "human_review": "not-performed",
                        "license": "fixture", "model_revision": "a" * 40, "dataset_version": "fixture",
                        "generator": entry(server.ROOT / "model.gguf"), "classifier": entry(classifier)}
            (server.ROOT / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                server.load_artifacts()
            self.assertEqual(server.load_artifacts(technical_demo=True)[0]["scope"], "technical-demo")

    def test_only_exact_model_path_can_be_approved(self):
        with TemporaryDirectory() as temp:
            server.ROOT = Path(temp)
            approved = server.ROOT / "approved"
            approved.mkdir()
            (approved / "model.gguf").write_bytes(b"synthetic-reviewed-fixture")
            (server.ROOT / "model.gguf").write_bytes(b"synthetic-unreviewed-fixture")
            classifier = server.ROOT / "classifier.json"
            classifier.write_text(json.dumps({"dataset_version": "fixture"}))

            def entry(path):
                return {"file": str(path.relative_to(server.ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {"decision": "integrate", "reviewer": "fixture-reviewer", "trained_by": "fixture-author", "reviewed_at": "2026-01-01",
                        "license": "fixture", "model_revision": "fixture", "dataset_version": "fixture",
                        "generator": entry(approved / "model.gguf"), "classifier": entry(classifier)}
            (server.ROOT / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                server.load_artifacts()

    def test_inline_and_multiline_programs_are_rejected(self):
        for text in ("a,b=map(int,open(0).read().split()); print(a+b)",
                     'x = __import__("sys").stdin.read(); __import__("sys").stdout.write(str(sum(map(int,x.split()))))',
                     "a,b=map(int,open(0).read().split())\nprint(a+b)",
                     "Observa el siguiente paso: console.log(a + b)",
                     "Revisa esto: System.out.println(a+b);"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                server.validate_output({"content": text, "uncertainty": "", "model_version": "fixture"})


class FakeModel(BaseHTTPRequestHandler):
    """llama.cpp sin streaming: cabeceras solo al terminar de generar (o goteo tras ellas)."""
    delay = 0.0
    drip = False
    staged = False
    header_drip = False
    body = json.dumps({"choices": [{"message": {"content": json.dumps(
        {"content": "Revisa cómo cambia el acumulador en cada iteración.", "uncertainty": "", "model_version": "x"})}}]}).encode()
    queue = []  # respuestas sucesivas; cuando se agotan se usa body
    requests = []  # cuerpos JSON recibidos

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        FakeModel.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = FakeModel.queue.pop(0) if FakeModel.queue else self.body
        try:
            if self.header_drip:
                self.wfile.write(b"HTTP/1.0 200 OK\r\nX-Fixture: ")
                self.wfile.flush()
                for _ in range(20):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.2)
                return
            if self.drip:
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                for _ in range(100):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.3)
                return
            time.sleep(self.delay)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.staged:
                time.sleep(0.7)
            self.wfile.write(body)
        except OSError:
            pass  # el motor cortó antes: es el caso esperado en las pruebas de exceso


def serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.model = serve(FakeModel)
        self.engine = serve(server.Handler)
        saved = {name: getattr(server, name) for name in ("MODEL_URL", "MODEL_TIMEOUT_S", "SUGGEST_TIMEOUT_S", "SUGGEST_RETRY_MIN_S", "ARTIFACTS", "predict")}
        self.addCleanup(lambda: [setattr(server, name, value) for name, value in saved.items()])
        for httpd in (self.engine, self.model):
            self.addCleanup(lambda httpd=httpd: (httpd.shutdown(), httpd.server_close()))
        server.MODEL_URL = "http://127.0.0.1:%d" % self.model.server_address[1]
        server.ARTIFACTS = ({"model_revision": "fixture"}, {})
        server.predict = lambda classifier, record: ("fixture", 0.5)
        FakeModel.delay, FakeModel.drip, FakeModel.staged = 0.0, False, False
        FakeModel.header_drip = False
        FakeModel.queue, FakeModel.requests = [], []
        self.addCleanup(setattr, FakeModel, "body", FakeModel.body)

    def post(self, path, data):
        request = urllib.request.Request("http://127.0.0.1:%d%s" % (self.engine.server_address[1], path), json.dumps(data).encode(),
                                         {"Content-Type": "application/json"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read()), time.monotonic() - started
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), time.monotonic() - started

    def feedback(self):
        context = {"schema_version": 1, "action": "hint", "level": 1, "concept": "c", "problem": {}, "code": "x", "language": "C",
                   "diagnostic": {}, "concepts": [], "history": [], "config_version": 1}
        return self.post("/v1/feedback", context)


class TimeoutTests(EngineTestCase):
    """Regresión: el timeout de socket no puede ser más corto que la generación."""

    def test_slow_generation_within_budget_is_accepted(self):
        FakeModel.delay = 1.0  # con el timeout anterior de 0.5 s esto fallaba
        server.MODEL_TIMEOUT_S = 3
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(data["model_version"], "fixture")

    def test_generation_over_budget_is_rejected(self):
        FakeModel.delay = 2.5
        server.MODEL_TIMEOUT_S = 1
        status, data, elapsed = self.feedback()
        self.assertEqual((status, data), (503, {"error": "unavailable"}))
        self.assertLess(elapsed, 2.0)

    def test_dripping_response_is_cut_by_total_deadline(self):
        FakeModel.drip = True  # cada lectura llega antes del timeout de socket
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 2.0)

    def test_budget_configuration_is_validated(self):
        for raw, expected in (("8", 8.0), ("1", 1.0), ("30", 30.0), ("2.5", 2.5)):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"MODEL_TIMEOUT_S": raw}):
                self.assertEqual(server.model_timeout(), expected)
        with mock.patch.dict(os.environ):
            os.environ.pop("MODEL_TIMEOUT_S", None)
            self.assertEqual(server.model_timeout(), 8.0)
        for raw in ("0", "0.5", "31", "-1", "abc", "", "nan", "inf"):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"MODEL_TIMEOUT_S": raw}), self.assertRaises(ValueError):
                server.model_timeout()

    def test_suggest_budget_configuration_is_validated(self):
        for raw, expected in (("90", 90.0), ("30", 30.0), ("100", 100.0), ("45.5", 45.5)):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"SUGGEST_TIMEOUT_S": raw}):
                self.assertEqual(server.suggest_timeout(), expected)
        with mock.patch.dict(os.environ):
            os.environ.pop("SUGGEST_TIMEOUT_S", None)
            self.assertEqual(server.suggest_timeout(), 90.0)
        for raw in ("0", "29", "101", "180", "-1", "abc", "", "nan", "inf"):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"SUGGEST_TIMEOUT_S": raw}), self.assertRaises(ValueError):
                server.suggest_timeout()

    def test_late_headers_do_not_grant_another_body_budget(self):
        FakeModel.delay, FakeModel.staged = 0.7, True
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 1.25)

    def test_integrated_model_uses_fixed_uncertainty(self):
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(data["uncertainty"], server.UNCERTAINTY)

    def test_extra_learned_keys_are_dropped(self):
        original = FakeModel.body
        self.addCleanup(setattr, FakeModel, "body", original)
        FakeModel.body = json.dumps({"choices": [{"message": {"content": json.dumps(
            {"content": "Revisa cómo cambia el acumulador en cada iteración del ciclo.", "uncertainty": "x",
             "model_version": "adapter", "history": ["x"]})}}]}).encode()
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"content", "uncertainty", "model_version"})

    def test_unhelpful_generations_fall_back(self):
        original = FakeModel.body
        self.addCleanup(setattr, FakeModel, "body", original)
        for content in ("Traza una línea y termina.",
                        "Aquí tienes una posible solución en C para este problema de enteros.",
                        "El código proporcionado es correcto y funciona para el caso público.",
                        "Check the loop because your counter should start at zero always."):
            with self.subTest(content=content):
                FakeModel.body = json.dumps({"choices": [{"message": {"content": json.dumps(
                    {"content": content, "uncertainty": "", "model_version": "x"})}}]}).encode()
                status, data, _ = self.feedback()
                self.assertEqual((status, data), (503, {"error": "unavailable"}))

    def test_dripping_headers_are_also_cut_by_total_deadline(self):
        FakeModel.header_drip = True
        server.MODEL_TIMEOUT_S = 1
        status, _, elapsed = self.feedback()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 1.25)


def model_reply(content, tokens=None, finish="stop"):
    reply = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
    if tokens is not None:
        reply["usage"] = {"completion_tokens": tokens}
    return json.dumps(reply).encode()


class BudgetTests(EngineTestCase):
    """Menos tokens y caché del prompt: en CPU el tiempo lo dominan el prefill y la generación."""

    def test_observation_asks_for_few_tokens_and_reuses_the_prompt_cache(self):
        self.assertEqual(self.feedback()[0], 200)
        sent = FakeModel.requests[-1]
        self.assertEqual(sent["max_tokens"], 120)
        self.assertIs(sent["cache_prompt"], True)

    def test_cut_generation_keeps_a_completed_content_string(self):
        FakeModel.body = model_reply('{"content": "Revisa cómo cambia el acumulador en cada iteración del ciclo.", "uncertainty": "Observ')
        status, data, _ = self.feedback()
        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "Revisa cómo cambia el acumulador en cada iteración del ciclo.")
        self.assertEqual(data["uncertainty"], server.UNCERTAINTY)

    def test_cut_generation_without_a_completed_content_falls_back(self):
        FakeModel.body = model_reply('{"content": "Revisa cómo cambia el acumulador en cada')
        self.assertEqual(self.feedback()[:2], (503, {"error": "unavailable"}))


SUGGESTION = {"concepts": [{"name": "Lectura de enteros", "explanation": "Antes de operar hay que leer cada valor con el tipo adecuado."},
                           {"name": "Acumulador", "explanation": "Una variable que guarda el resultado parcial mientras se recorren los datos."}],
              "hints": {"concept": "¿Qué tipo de dato necesitas para guardar la suma?",
                        "location": "Revisa cómo declaras las variables que reciben la lectura.",
                        "strategy": "Compara el rango de los valores con el rango del tipo elegido."}}
PROBLEM = {"title": "Suma grande", "description": "Lee A y B (hasta 10^18) y muestra su suma.", "input_description": "Dos enteros.",
           "output_description": "La suma.", "samples": [{"input": "1 2", "output": "3"}]}


# Salidas reales de Qwen2.5-Coder-1.5B Q4_K_M (llama.cpp, 5 hilos) que el motor 2.2.1 rechazaba, sin más recorte que el del modelo.
REAL_OUTPUTS = {
    # BLZ2-145, intento 1: max_tokens cortó la salida tras unas pistas completas (finish_reason=length)
    "CENSO_CORTADO": (
        '{"concepts":[{"name":"Relación entre puntos y rectángulos","explanation":"Recuerda que cada punto puede '
        'pertenecer a varios rectángulos."},{"name":"Traza dos líneas y determina cuántos puntos hay '
        'dentro.","explanation":"Traza una línea y cuenta los puntos que estén por encima. Traza otra línea y vuelve '
        'a contar los puntos que estén por debajo."},{"name":"Recuerda que un punto puede pertenecer a más de una '
        'rectángulo.","explanation":"Cuenta todos los puntos que estén dentro o sobre cada línea y luego suma los '
        'resultados."}],"hints":{"concept":"Traza dos líneas y determina cuántos puntos hay '
        'dentro.","location":"Deducí dos líneas que puedan contener al menos un punto y '
        'calcúlalos.","strategy":"Traza una primera línea y cuenta los puntos que estén por encima. Traza otra línea '
        'y vuelve a contar los puntos que estén por debajo. La intersección de las dos líneas dará el número exacto '
        'de puntos que hay dentro."},"location":"Inspecciona la última coordenada del primer rectángulo y la primera '
        'coordenada del segundo recuadro.","'),

    # MED-MOCHILA-028, intento 1: la clave hints se repite y la última queda cortada (finish_reason=length)
    "MOCHILA_CORTADA_CON_PISTAS_REPETIDAS": (
        '{"concepts":[{"name":"Recursión","explanation":"Traza dos opciones y elige la que mejor resultado '
        'da."},{"name":"Caso base y condición de finalización.","explanation":"Deducí cuándo no hay más objetos y qué'
        ' valor consigue trazer."},{"name":"Pasar al siguiente objeto.","explanation":"Relaciona el recorrido con el '
        'recorrido sin incluir el objeto actual."}],"hints":{"concept":"Traza dos opciones y elige la que mejor '
        'resultado da.","location":"Dentro del recorrido.","strategy":"Cuenta cuántos objetos has traído hasta ahora '
        'y el valor que consigue traer. Traza dos opciones:"},"hints":{"concept":"Traza dos opciones y elige la que '
        'mejor resultado da.","location":"El primer recorrido incluye el primer objeto.","strategy":"Deducí cuál '
        'sería el valor que consigue traer sin incluir el primer objeto y contra ese valor sumale el peso del primer '
        'objeto."},"hints":{"concept":"Traza dos opciones y elige la que mejor resultado da.","location":"El segundo '
        'recorrido no incluye el primer objeto.","strategy":"Deducí cuál sería el valor máximo que consigue traer sin'),

    # BLZ2-076, intento 1: concepts es una lista de cadenas y no de objetos {name, explanation}
    "RELOJES_CONCEPTOS_COMO_CADENAS": (
        '{"concepts":["relaciones entre variables","módulo y residuo","demostración pedagógica","recorrido hasta '
        'encontrar la solución"],"hints":{"concept":"Recorre todos los candidatos hasta que encuentres uno que cumpla'
        ' las condiciones.","location":"Inspecciona el valor actual y determina si es posible que produzca ambas '
        'lecturas.","strategy":"Traza dos recorridos distintos: uno para x módulo m y otro para x módulo n. Localiza '
        'la primera intersección."}}'),

    # BLZ2-145, intento 2 («más breve»): concept en singular en lugar de concepts
    "CENSO_CLAVE_EN_SINGULAR": (
        '{"concept":"Traza dos líneas y determina cuántos puntos hay entre ellas.","hints":{"concept":"Cuenta los '
        'pares que estén dentro del recuadro formado por las dos líneas.","location":"Relaciona la cantidad de '
        'intersecciones con el número de puntos.","strategy":"Recorre todos los pares y comprueba si forman una '
        'intersección."},"examples":["Traza dos líneas y cuenta cuántos puntos hay entre ellas.","Examina el primer '
        'recuadro y determina cuántos puntos hay entre las dos líneas."]}'),

    # BLZ2-094, intento 1: concepts vacío
    "PARCELAS_SIN_CONCEPTOS": (
        '{"concepts":[],"hints":{"concept":"Traza dos recuadros y localiza la intersección.","location":"Cuenta las '
        'casillas que estén entre los límites de ambos recuadros.","strategy":"Distingue entre el primer punto y el '
        'último y cuenta solo las casillas que van dentro."} }'),

    # MED-MOCHILA-028, intento 2: el segundo concepto usa la clave concept en lugar de name
    "MOCHILA_CONCEPTO_SIN_NOMBRE": (
        '{"concepts":[{"name":"Recursión","explanation":"Traza dos ramas: una que incluye el primer objeto y otra que'
        ' lo excluye."},{"concept":"Caching","explanation":"Guarda los resultados ya calculados para evitarnos '
        'recalcularlos."}],"hints":{"concept":"Relación entre W y el valor del primer objeto","location":"Traza la '
        'primera rama y determina si vale la pena continuar investigando.","strategy":"Pide cuenta del primer objeto '
        'y decide si incluirlo o no en la mochila."}}'),

    # BLZ2-050, intento 1: la pista strategy mide 359 caracteres
    "ZONA_PISTA_DE_359_CARACTERES": (
        '{"concepts":[{"name":"Relación entre puntos y segmentos","explanation":"Recuerda que una recta se define por'
        ' dos puntos y tiene un punto de intersección con cualquier otra recta."},{"name":"Intersección de '
        'rectas","explanation":"Traza las rectas y localiza los puntos de intersección. Recuerda que dos rectas '
        'trazen hasta donde queden pendientes y cortan al primer punto en común."},{"name":"Operaciones con '
        'números","explanation":"Recuerda que puedes sumar, restar, multiplicar y dividir '
        'números."}],"hints":{"concept":"Traza las rectas y localiza los puntos de '
        'intersección.","location":"Comienza trazando la primera recta y recórrela hasta encontrar un punto que pueda'
        ' intersecar con la segunda recta.","strategy":"Traza la primera recta y localiza el primer punto que puede '
        'intersecar con la segunda recta. Traza la segunda recta y localiza el primer punto que puede intersecar con '
        'la primera recta. Ahora tienes dos puntos de intersección. Compara las coordenadas de estos puntos y '
        'determina cuál es el área que pertenece a ambos."}}'),

    # MED-MOCHILA-028, intento 2: location y strategy son idénticas
    "MOCHILA_PISTAS_IGUALES": (
        '{"concepts":[{"name":"Recursión","explanation":"Traza dos opciones y elige la que mejor resultado '
        'da."},{"name":"Caso base y condición de parada.","explanation":"Distingue entre dos casos posibles y termina'
        ' si llegas a una circunstancia que consigue resolver el problema."}],"hints":{"concept":"Recuerda trazar las'
        ' dos opciones y elegir la mejor.","location":"Traza dos opciones y elige la que mejor resultado '
        'da.","strategy":"Traza dos opciones y elige la que mejor resultado da."}}'),
}


class SanitizeTests(unittest.TestCase):
    """Cada fixture de REAL_OUTPUTS es una salida real que el motor 2.2.1 devolvía como 503 sin dejar rastro."""

    def accepted(self, name):
        notes = []
        return server.parse_suggestion(REAL_OUTPUTS[name], notes), notes

    def reason(self, name):
        with self.assertRaises(server.Rejected) as caught:
            server.parse_suggestion(REAL_OUTPUTS[name])
        return str(caught.exception)

    def test_generation_cut_by_max_tokens_keeps_what_was_complete(self):
        result, notes = self.accepted("CENSO_CORTADO")
        self.assertEqual(len(result["concepts"]), 3)
        self.assertTrue(result["hints"]["strategy"].endswith("el número exacto de puntos que hay dentro."))
        self.assertEqual(notes, [])

    def test_cut_generation_with_a_repeated_hints_key_completes_the_missing_hint_with_generic_text(self):
        result, notes = self.accepted("MOCHILA_CORTADA_CON_PISTAS_REPETIDAS")
        self.assertEqual(result["hints"]["location"], "El segundo recorrido no incluye el primer objeto.")
        self.assertEqual(result["hints"]["strategy"], server.GENERIC_HINTS["strategy"])
        self.assertEqual(notes, ["pista strategy: missing"])

    def test_concepts_that_are_not_objects_are_rejected_with_their_reason(self):
        for name in ("RELOJES_CONCEPTOS_COMO_CADENAS", "CENSO_CLAVE_EN_SINGULAR", "PARCELAS_SIN_CONCEPTOS"):
            with self.subTest(name):
                self.assertEqual(self.reason(name), "no-concepts")

    def test_a_concept_without_name_is_dropped_and_the_rest_is_kept(self):
        result, notes = self.accepted("MOCHILA_CONCEPTO_SIN_NOMBRE")
        self.assertEqual([item["name"] for item in result["concepts"]], ["Recursión"])
        self.assertEqual(notes, ["concepto 2: missing"])

    def test_a_long_hint_is_cut_at_a_sentence_boundary(self):
        original = json.loads(REAL_OUTPUTS["ZONA_PISTA_DE_359_CARACTERES"])["hints"]["strategy"]
        result, notes = self.accepted("ZONA_PISTA_DE_359_CARACTERES")
        self.assertGreater(len(original), server.TEXT_LIMIT)
        self.assertLessEqual(len(result["hints"]["strategy"]), server.TEXT_LIMIT)
        self.assertTrue(result["hints"]["strategy"].endswith("."))
        self.assertTrue(original.startswith(result["hints"]["strategy"]))
        self.assertEqual(notes, [])

    def test_a_repeated_hint_is_replaced_with_generic_text(self):
        result, notes = self.accepted("MOCHILA_PISTAS_IGUALES")
        self.assertEqual(result["hints"]["location"], "Traza dos opciones y elige la que mejor resultado da.")
        self.assertEqual(result["hints"]["strategy"], server.GENERIC_HINTS["strategy"])
        self.assertEqual(notes, ["pista strategy: duplicate"])

    def test_generic_hints_pass_the_student_filter_and_are_distinct(self):
        for key, text in server.GENERIC_HINTS.items():
            with self.subTest(key):
                self.assertEqual(server.suggestion_text(text, server.TEXT_LIMIT, server.MODEL_TEXT_MAX), text)
        self.assertEqual(set(server.GENERIC_HINTS), set(server.HINT_KEYS))
        self.assertEqual(len(set(server.GENERIC_HINTS.values())), 3)

    def test_text_cut_by_the_grammar_is_trimmed_to_a_whole_word(self):
        # Salida real con la gramática de 2.2.2: la cota de 130 caracteres cortó la pista a mitad de palabra.
        cut = "Comienza en el extremo superior izquierdo y vuelve a recorrer hacia abajo y derecha hasta encontrar una coordenada que salga del r"
        self.assertEqual(len(cut), server.MODEL_TEXT_MAX)
        content = json.dumps({**SUGGESTION, "hints": {**SUGGESTION["hints"], "location": cut}})
        self.assertEqual(server.parse_suggestion(content)["hints"]["location"], cut[:-2] + "…")
        # Un texto que llega a la cota pero cierra la frase no se toca.
        whole = ("Cuenta los puntos de cada rectángulo. " * 4)[:129] + "."
        self.assertEqual((len(whole), whole[-1]), (130, "."))
        content = json.dumps({**SUGGESTION, "hints": {**SUGGESTION["hints"], "location": whole}})
        self.assertEqual(server.parse_suggestion(content)["hints"]["location"], whole)

    def test_json_is_read_from_fences_text_and_cut_strings(self):
        self.assertEqual(server.read_json_object('Aquí va:\n```json\n{"a": 1}\n```\nListo {x}'), {"a": 1})
        self.assertEqual(server.read_json_object('{"a": ["x \\"q\\" y", "zz'), {"a": ['x "q" y']})
        self.assertEqual(server.read_json_object('{"a": {"b": 1, "c": [1, 2'), {"a": {"b": 1, "c": [1]}})
        for text in ("sin json", "[1, 2]", '{"a": ', "{"):
            with self.subTest(text), self.assertRaises(server.Rejected):
                server.read_json_object(text)

    def test_math_notation_is_not_mistaken_for_code(self):
        for text in ("Compara x1 ≤ x ≤ x2 y y1 ≤ y ≤ y2.", "Cada rectángulo se describe con x1 y1 x2 y2.", "Cuenta los puntos con a ≤ x ≤ b.",
                     "Si x < a o x > b, el punto queda fuera.", "Usa x1 <= x y x <= x2, o bien y >= a.", "Con 1 ≤ n ≤ 100000 no basta un recorrido por consulta."):
            with self.subTest(text):
                self.assertTrue(server.suggestion_text(text, server.TEXT_LIMIT, server.MODEL_TEXT_MAX))
                self.assertFalse(server.CODE_LINE.search(text))
        self.assertEqual(server.suggestion_text("Si x < a o x >= b.", 300, 130), "Si x menor que a o x ≥ b.")

    def test_html_and_programs_are_still_rejected(self):
        for text in ("Usa <b>negrita</b> aquí.", "<script>alert(1)</script>", "x = input()", "int total = 0;", 'Escribe printf("%d", a + b);',
                     "import os", "Usa ```int x = 0;``` para empezar."):
            with self.subTest(text), self.assertRaises(ValueError):
                server.suggestion_text(text, 300, 130)

    def test_code_in_two_texts_or_a_fence_rejects_the_whole_proposal(self):
        one_code = {**SUGGESTION, "hints": {**SUGGESTION["hints"], "strategy": "x = input()"}}
        notes = []
        result = server.parse_suggestion(json.dumps(one_code), notes)
        self.assertEqual(result["hints"]["strategy"], server.GENERIC_HINTS["strategy"])
        self.assertEqual(notes, ["pista strategy: guard-program-syntax"])
        two_codes = {**one_code, "hints": {**one_code["hints"], "location": "total = 0"}}
        with self.assertRaises(server.Rejected) as caught:
            server.parse_suggestion(json.dumps(two_codes))
        self.assertEqual(str(caught.exception), "guard")
        fenced = {**SUGGESTION, "concepts": [{**SUGGESTION["concepts"][0], "explanation": "Usa ```int x = 0;``` para empezar."}]}
        with self.assertRaises(server.Rejected) as caught:
            server.parse_suggestion(json.dumps(fenced))
        self.assertEqual(str(caught.exception), "code")

    def test_retry_tokens_follow_the_speed_measured_in_the_first_attempt(self):
        self.assertEqual(server.retry_tokens(30, 100, 10), server.SUGGEST_RETRY_MAX_TOKENS)
        self.assertEqual(server.retry_tokens(13, 100, 10), int((13 - server.SUGGEST_MARGIN_S) * 10))
        self.assertLess(server.retry_tokens(6, 100, 10), server.SUGGEST_RETRY_MIN_TOKENS)
        # Sin medida de velocidad se conserva el tope fijo.
        self.assertEqual(server.retry_tokens(30, None, 10), server.SUGGEST_RETRY_MAX_TOKENS)
        self.assertEqual(server.retry_tokens(30, 0, 10), server.SUGGEST_RETRY_MAX_TOKENS)


class SuggestTests(EngineTestCase):
    def setUp(self):
        super().setUp()
        # Plazos distintos a propósito: /suggest solo debe usar el suyo.
        server.MODEL_TIMEOUT_S = 5
        server.SUGGEST_TIMEOUT_S = 5
        server.SUGGEST_RETRY_MIN_S = 0.5
        FakeModel.body = model_reply(json.dumps(SUGGESTION))

    def suggest(self, problem=PROBLEM):
        return self.post("/suggest", {"problem": problem})

    def test_valid_suggestion_is_returned_with_a_bounded_prompt(self):
        long_problem = {**PROBLEM, "description": "x" * 5000, "samples": PROBLEM["samples"] * 3}
        status, data, _ = self.suggest(long_problem)
        self.assertEqual((status, data), (200, SUGGESTION))
        sent = FakeModel.requests[-1]
        self.assertEqual((sent["max_tokens"], sent["cache_prompt"]), (260, True))
        # La gramática fija la forma de la salida: sin ella, el modelo devolvía claves ajenas, listas vacías o cadenas en vez de objetos.
        self.assertEqual(sent["response_format"], server.SUGGEST_FORMAT)
        self.assertEqual(sent["response_format"]["json_schema"]["schema"]["required"], ["concepts", "hints"])
        self.assertEqual([item["role"] for item in sent["messages"]], ["system", "user"])
        prompt = json.loads(sent["messages"][1]["content"])["problem"]
        self.assertEqual(prompt["title"], "Suma grande")
        self.assertEqual(len(prompt["description"]), server.SUGGEST_LIMIT)
        self.assertEqual(len(prompt["samples"]), 3)

    def test_fenced_json_with_surrounding_text_is_accepted_and_text_is_normalized(self):
        content = "Aquí está:\n```json\n" + json.dumps({**SUGGESTION, "concepts": [
            {"name": "  Lectura   de enteros ", "explanation": "Leer cada valor\ncon el tipo adecuado."}]}) + "\n```"
        FakeModel.body = model_reply(content)
        status, data, _ = self.suggest()
        self.assertEqual(status, 200)
        self.assertEqual(data["concepts"], [{"name": "Lectura de enteros", "explanation": "Leer cada valor con el tipo adecuado."}])

    def test_invalid_json_is_retried_once_with_a_shorter_request(self):
        FakeModel.queue = [model_reply('{"concepts": [{"name": "Acumulador"'), model_reply(json.dumps(SUGGESTION))]
        self.assertEqual(self.suggest()[:2], (200, SUGGESTION))
        self.assertEqual(len(FakeModel.requests), 2)
        first, second = (item["messages"] for item in FakeModel.requests)
        # El segundo prompt no repite el primero, pero lo conserva como prefijo para que llama.cpp lo reutilice de su caché.
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(second[:2], first)
        self.assertEqual(second[2], {"role": "user", "content": server.SUGGEST_BREVITY})

    def test_each_attempt_and_each_request_uses_its_own_seed(self):
        FakeModel.queue = [model_reply("no es JSON")]
        self.assertEqual(self.suggest()[0], 200)
        self.assertEqual(self.suggest()[0], 200)
        seeds = [item["seed"] for item in FakeModel.requests]
        self.assertEqual(len(seeds), 3)
        self.assertNotEqual(seeds[0], seeds[1])
        self.assertNotIn(2026, seeds)
        self.assertNotEqual(seeds[1], seeds[2])

    def test_second_invalid_answer_is_rejected_without_a_third_attempt(self):
        FakeModel.body = model_reply("no es JSON")
        self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
        self.assertEqual(len(FakeModel.requests), 2)

    def test_unusable_proposals_are_rejected_after_two_attempts(self):
        good = SUGGESTION["concepts"][0]
        hints = SUGGESTION["hints"]
        code_hint = 'int total = 0;\nfor (int i = 0; i < n; i++) {\n total += a[i];\n}\nprintf("%d", total);'
        cases = {
            "sin conceptos": {"concepts": []},
            "todos los conceptos inválidos": {"concepts": [{**good, "name": "n" * 81}, {**good, "explanation": "  "}]},
            "dos pistas ausentes": {"hints": {"concept": hints["concept"]}},
            "dos pistas repetidas": {"hints": {**hints, "location": hints["concept"], "strategy": hints["concept"]}},
            "bloque de código": {"concepts": [{**good, "explanation": "Usa ```int x = 0;``` para empezar."}]},
            "cuatro líneas de código": {"hints": {**hints, "strategy": code_hint}},
            "dos textos que la guardia rechaza": {"hints": {**hints, "location": "x = input()", "strategy": "total = 0"}},
            "conceptos en inglés": {"concepts": [{**good, "explanation": "Check the loop because your counter is wrong."}]},
            "tipo incorrecto": {"concepts": ["Acumulador"]},
            "conceptos no es una lista": {"concepts": "Acumulador"},
            "sin pistas": {"hints": []},
        }
        for name, change in cases.items():
            with self.subTest(name):
                FakeModel.requests, FakeModel.queue = [], []
                FakeModel.body = model_reply(json.dumps({**SUGGESTION, **change}))
                self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
                self.assertEqual(len(FakeModel.requests), 2)

    def test_invalid_parts_are_dropped_or_cut_instead_of_rejecting_the_proposal(self):
        good, other = SUGGESTION["concepts"]
        hints = SUGGESTION["hints"]
        generic = server.GENERIC_HINTS
        cases = {
            "cinco conceptos": ({"concepts": [{**good, "name": "Concepto %d" % number} for number in range(5)]},
                                lambda data: self.assertEqual(len(data["concepts"]), server.MAX_CONCEPTS)),
            "nombre largo": ({"concepts": [{**good, "name": "n" * 81}, other]},
                             lambda data: self.assertEqual(data["concepts"], [other])),
            "explicación larga": ({"concepts": [{**good, "explanation": " ".join(["Esta frase tiene unas cuarenta letras."] * 12)}]},
                                  lambda data: self.assertEqual(data["concepts"][0]["explanation"], " ".join(["Esta frase tiene unas cuarenta letras."] * 7))),
            "explicación vacía": ({"concepts": [{**good, "explanation": "  "}, other]},
                                  lambda data: self.assertEqual(data["concepts"], [other])),
            "pista larga": ({"hints": {**hints, "strategy": "p" * 301}},
                            lambda data: self.assertEqual(data["hints"]["strategy"], "p" * 299 + "…")),
            "pistas repetidas": ({"hints": {**hints, "location": hints["concept"]}},
                                 lambda data: self.assertEqual(data["hints"], {**hints, "location": generic["location"]})),
            "pista ausente": ({"hints": {"concept": hints["concept"], "location": hints["location"]}},
                              lambda data: self.assertEqual(data["hints"], {**hints, "strategy": generic["strategy"]})),
            "pista con claves de más": ({"hints": {**hints, "extra": "otra cosa"}},
                                        lambda data: self.assertEqual(data["hints"], hints)),
            "conceptos repetidos": ({"concepts": [good, {**good, "name": good["name"].upper()}]},
                                    lambda data: self.assertEqual(data["concepts"], [good])),
            "pista en inglés": ({"hints": {**hints, "location": "Check the loop because your counter is wrong."}},
                                lambda data: self.assertEqual(data["hints"]["location"], generic["location"])),
            "concepto sin nombre": ({"concepts": [{"explanation": "Sin nombre."}, good]},
                                    lambda data: self.assertEqual(data["concepts"], [good])),
            "un texto que la guardia rechaza": ({"hints": {**hints, "strategy": "<script>alert(1)</script>"}},
                                                lambda data: self.assertEqual(data["hints"]["strategy"], generic["strategy"])),
            "comparaciones": ({"hints": {**hints, "location": "Si x < a o x > b, el punto queda fuera."}},
                              lambda data: self.assertEqual(data["hints"]["location"], "Si x menor que a o x mayor que b, el punto queda fuera.")),
        }
        for name, (change, check) in cases.items():
            with self.subTest(name):
                FakeModel.requests, FakeModel.queue = [], []
                FakeModel.body = model_reply(json.dumps({**SUGGESTION, **change}))
                status, data, _ = self.suggest()
                self.assertEqual(status, 200)
                check(data)
                self.assertEqual(len(FakeModel.requests), 1)

    def test_real_outputs_that_were_rejected_are_now_served_or_retried_with_a_reason(self):
        for name in ("CENSO_CORTADO", "MOCHILA_CORTADA_CON_PISTAS_REPETIDAS", "MOCHILA_CONCEPTO_SIN_NOMBRE", "ZONA_PISTA_DE_359_CARACTERES",
                     "MOCHILA_PISTAS_IGUALES"):
            with self.subTest(name):
                FakeModel.requests, FakeModel.queue = [], []
                FakeModel.body = model_reply(REAL_OUTPUTS[name], tokens=260, finish="length")
                status, data, _ = self.suggest()
                self.assertEqual(status, 200)
                self.assertTrue(data["concepts"])
                self.assertEqual(len(FakeModel.requests), 1)
        # Lo que no se puede aprovechar (concepts como lista de cadenas) se reintenta y el segundo intento sí sirve.
        FakeModel.requests = []
        FakeModel.queue = [model_reply(REAL_OUTPUTS["RELOJES_CONCEPTOS_COMO_CADENAS"]), model_reply(REAL_OUTPUTS["CENSO_CORTADO"])]
        self.assertEqual(self.suggest()[0], 200)
        self.assertEqual(len(FakeModel.requests), 2)

    def test_every_rejected_proposal_is_logged_with_its_reason_and_a_short_excerpt(self):
        junk = "x" * 1000
        FakeModel.queue = [model_reply(junk, tokens=260, finish="length"), model_reply(REAL_OUTPUTS["RELOJES_CONCEPTOS_COMO_CADENAS"], tokens=115)]
        with self.assertLogs("tutor_engine", "WARNING") as logs:
            self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
        first, second, summary = (record.getMessage() for record in logs.records)
        self.assertIn("intento=1 motivo=json fin=length tokens=260", first)
        self.assertIn("intento=2 motivo=no-concepts fin=stop tokens=115", second)
        self.assertIn("sin propuesta válida: intentos=2", summary)
        self.assertEqual({record.levelname for record in logs.records}, {"WARNING"})
        # Un recorte de la salida, nunca el texto completo ni el enunciado.
        self.assertIn("x" * server.LOG_EXCERPT, first)
        self.assertNotIn("x" * (server.LOG_EXCERPT + 1), first)
        self.assertNotIn(PROBLEM["description"], "\n".join(record.getMessage() for record in logs.records))
        self.assertLess(len(second), 400)

    def test_an_accepted_proposal_is_not_a_warning_and_a_sanitized_one_is_noted_at_info(self):
        with self.assertNoLogs("tutor_engine", "WARNING"):
            self.assertEqual(self.suggest()[0], 200)
        hints = SUGGESTION["hints"]
        FakeModel.body = model_reply(json.dumps({**SUGGESTION, "hints": {"concept": hints["concept"], "location": hints["location"]}}))
        with self.assertLogs("tutor_engine", "INFO") as logs:
            self.assertEqual(self.suggest()[0], 200)
        self.assertEqual([record.levelname for record in logs.records], ["INFO"])
        self.assertIn("pista strategy: missing", logs.records[0].getMessage())

    def test_a_model_failure_is_logged_with_the_error_type(self):
        FakeModel.delay = 2.5
        server.SUGGEST_TIMEOUT_S = 1
        with self.assertLogs("tutor_engine", "WARNING") as logs:
            self.assertEqual(self.suggest()[0], 503)
        self.assertIn("sin respuesta del modelo: intento=1 error=", logs.records[0].getMessage())

    def test_a_request_that_fails_unexpectedly_is_logged_with_its_route_and_error_type(self):
        request = urllib.request.Request("http://127.0.0.1:%d/suggest" % self.engine.server_address[1], b"no es JSON",
                                         {"Content-Type": "application/json"})
        with self.assertLogs("tutor_engine", "WARNING") as logs, self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(logs.records[0].getMessage(), "petición /suggest no atendida: JSONDecodeError")

    def test_the_retry_asks_only_for_the_tokens_that_fit_in_the_time_left(self):
        # Primer intento: 20 tokens en ~1 s (20 tokens/s). Con ~9 s restantes caben (9 - margen) * 20 tokens, menos que el tope.
        FakeModel.delay = 1.0
        server.SUGGEST_TIMEOUT_S = 10
        FakeModel.queue = [model_reply("no es JSON", tokens=20), model_reply(json.dumps(SUGGESTION), tokens=20)]
        self.assertEqual(self.suggest()[:2], (200, SUGGESTION))
        retry = FakeModel.requests[1]["max_tokens"]
        self.assertLess(retry, server.SUGGEST_RETRY_MAX_TOKENS)
        self.assertGreaterEqual(retry, server.SUGGEST_RETRY_MIN_TOKENS)

    def test_the_retry_is_skipped_when_it_could_not_produce_a_proposal_in_the_time_left(self):
        # 10 tokens/s y ~6 s restantes: solo caben unos 30 tokens, menos que un concepto y tres pistas.
        FakeModel.delay = 1.0
        server.SUGGEST_TIMEOUT_S = 7
        FakeModel.body = model_reply("no es JSON", tokens=10)
        with self.assertLogs("tutor_engine", "WARNING") as logs:
            self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
        self.assertEqual(len(FakeModel.requests), 1)
        self.assertIn("intentos=1", logs.records[-1].getMessage())

    def test_malformed_requests_are_rejected_without_calling_the_model(self):
        cases = [[], {}, {"problem": []}, {"problem": {**PROBLEM, "extra": 1}}, {"problem": {**PROBLEM, "title": 3}},
                 {"problem": {key: value for key, value in PROBLEM.items() if key != "samples"}},
                 {"problem": {**PROBLEM, "samples": [{"input": "1"}]}}, {"problem": {**PROBLEM, "samples": [{"input": 1, "output": "2"}]}},
                 {"problem": {**PROBLEM, "samples": [PROBLEM["samples"][0]] * 4}}, {"problem": PROBLEM, "otro": 1}]
        for data in cases:
            with self.subTest(data=data):
                self.assertEqual(self.post("/suggest", data)[:2], (400, {"error": "schema"}))
        self.assertEqual(FakeModel.requests, [])

    def test_model_down_and_unknown_routes(self):
        self.assertEqual(self.post("/suggest/otra", {"problem": PROBLEM})[:2], (404, {"error": "not-found"}))
        server.MODEL_URL = "http://127.0.0.1:1"
        self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))

    def test_generation_over_budget_is_rejected(self):
        FakeModel.delay = 2.5
        server.SUGGEST_TIMEOUT_S = 1.5
        status, _, elapsed = self.suggest()
        self.assertEqual(status, 503)
        self.assertLess(elapsed, 2.3)
        self.assertEqual(len(FakeModel.requests), 1)

    def test_retry_is_skipped_when_the_shared_budget_is_spent(self):
        FakeModel.delay = 0.8
        server.SUGGEST_TIMEOUT_S = 1.2
        FakeModel.body = model_reply("no es JSON")
        self.assertEqual(self.suggest()[0], 503)
        self.assertEqual(len(FakeModel.requests), 1)

    def test_suggestion_has_its_own_budget_longer_than_the_observation_one(self):
        FakeModel.delay = 1.5
        server.MODEL_TIMEOUT_S = 1
        server.SUGGEST_TIMEOUT_S = 4
        self.assertEqual(self.suggest()[:2], (200, SUGGESTION))
        status, data, elapsed = self.feedback()
        self.assertEqual((status, data), (503, {"error": "unavailable"}))
        self.assertLess(elapsed, 1.4)

    def test_retry_is_shorter_and_needs_time_left(self):
        FakeModel.queue = [model_reply("no es JSON"), model_reply(json.dumps(SUGGESTION))]
        self.assertEqual(self.suggest()[:2], (200, SUGGESTION))
        self.assertEqual([item["max_tokens"] for item in FakeModel.requests], [260, 200])
        # Tras 1 s de generación quedan unos 2 s: menos que el mínimo exigido para un segundo intento.
        FakeModel.requests, FakeModel.queue, FakeModel.delay = [], [model_reply("no es JSON")], 1.0
        server.SUGGEST_TIMEOUT_S, server.SUGGEST_RETRY_MIN_S = 3, 2.5
        self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
        self.assertEqual(len(FakeModel.requests), 1)

    def test_one_suggestion_at_a_time_leaves_a_slot_for_observations(self):
        FakeModel.delay = 1.0
        long_one = []
        worker = threading.Thread(target=lambda: long_one.append(self.suggest()))
        worker.start()
        waited = time.monotonic()
        while not FakeModel.requests and time.monotonic() - waited < 3:
            time.sleep(0.02)
        FakeModel.queue = [model_reply(json.dumps({"content": "Revisa cómo cambia el acumulador en cada iteración.", "uncertainty": ""}))]
        self.assertEqual(self.suggest()[:2], (429, {"error": "busy"}))
        self.assertEqual(self.feedback()[0], 200)
        worker.join(5)
        self.assertEqual(long_one[0][:2], (200, SUGGESTION))
        self.assertEqual(self.suggest()[0], 200)

    def test_suggestion_slot_is_released_after_a_timeout(self):
        FakeModel.delay = 2.5
        server.SUGGEST_TIMEOUT_S = 1
        self.assertEqual(self.suggest()[:2], (503, {"error": "unavailable"}))
        FakeModel.delay = 0.0
        server.SUGGEST_TIMEOUT_S = 5
        self.assertEqual(self.suggest()[:2], (200, SUGGESTION))


if __name__ == "__main__":
    unittest.main()
