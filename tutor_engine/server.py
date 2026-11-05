"""Motor interno: requiere artefactos revisados y verifica sus checksums al arrancar."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
from pathlib import Path
import threading
import urllib.request

from guard import validate_output
from classifier_runtime import predict
from bounded_http import post_json
from tutor_prompt import build_messages

ROOT = Path("/models").resolve()
UNCERTAINTY = "Observación generada automáticamente; puede no identificar la causa exacta."
# Respuestas que no deben llegar a un estudiante aunque superen el guard sintáctico.
UNHELPFUL = re.compile(
    r"(?i)aqu[ií] tienes|soluci[oó]n (completa|correcta|final)|c[oó]digo (correcto|corregido)|"
    r"(es|est[aá]) correcto|no hay (necesidad|nada que)|\b(the|your|should|please)\b")
MODEL_URL = os.environ.get("MODEL_URL", "http://oj-model:8080")
SLOTS = threading.BoundedSemaphore(2)
ARTIFACTS = None
# Presupuesto total (conexión + generación + lectura) por petición al modelo.
MODEL_TIMEOUT_S = 8.0


def model_timeout():
    """Lee MODEL_TIMEOUT_S del entorno (1-30 s); falla cerrado si no es válido."""
    raw = os.environ.get("MODEL_TIMEOUT_S", "8")
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("model-timeout") from None
    if not math.isfinite(value) or not 1 <= value <= 30:
        raise ValueError("model-timeout")
    return value


def checked_file(entry):
    path = (ROOT / entry["file"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("artifact")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != entry["sha256"]:
        raise ValueError("checksum")
    return path


def load_artifacts(technical_demo=False):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    demonstration = manifest.get("scope") == "technical-demo"
    if demonstration:
        if not technical_demo or manifest["decision"] != "demonstration" or manifest.get("human_review") != "not-performed":
            raise ValueError("technical-demo")
    elif manifest["decision"] != "integrate" or not manifest["reviewer"] or manifest["reviewer"] == manifest["trained_by"] or not manifest["reviewed_at"]:
        raise ValueError("review")
    if not manifest["license"] or not manifest["model_revision"]:
        raise ValueError("provenance")
    model_path = checked_file(manifest["generator"])
    if model_path != ROOT / "model.gguf":
        raise ValueError("generator-name")
    classifier = json.loads(checked_file(manifest["classifier"]).read_text())
    if (classifier.get("scope") == "technical-demo") != demonstration:
        raise ValueError("classifier-scope")
    if classifier["dataset_version"] != manifest["dataset_version"]:
        raise ValueError("dataset-version")
    return manifest, classifier


def useful(content):
    """Descarta observaciones demasiado breves, que ofrecen soluciones o no están en español."""
    text = content.strip()
    return len(text) >= 40 and len(text.split()) >= 7 and not UNHELPFUL.search(text)


def ready():
    if ARTIFACTS is None:
        return False
    try:
        with urllib.request.urlopen(MODEL_URL + "/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # No registrar código, contexto ni URLs de usuarios.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, status, data):
        payload = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "not-found"})
        healthy = ready()
        self.reply(200 if healthy else 503, {"ready": healthy})

    def do_POST(self):
        if self.path != "/v1/feedback":
            return self.reply(404, {"error": "not-found"})
        if not SLOTS.acquire(blocking=False):
            return self.reply(429, {"error": "busy"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 64000 or self.headers.get("Transfer-Encoding"):
                return self.reply(413, {"error": "size"})
            context = json.loads(self.rfile.read(size))
            allowed = {"schema_version", "action", "level", "concept", "problem", "code", "language", "diagnostic", "concepts", "history", "config_version"}
            if set(context) != allowed or context["action"] not in {"explain", "hint", "concept"} or type(context["level"]) is not int or not 0 <= context["level"] <= 3:
                return self.reply(400, {"error": "schema"})
            if not ready():
                return self.reply(503, {"error": "unavailable"})
            manifest, classifier = ARTIFACTS
            diagnostic = context["diagnostic"]
            category, confidence = predict(classifier, {"language": context["language"], "verdict": diagnostic.get("verdict", 5),
                                                        "faulty_code": context["code"], "evidence": [diagnostic.get("evidence", "")]})
            payload = {"messages": build_messages(context, {"category": category, "confidence": confidence}),
                       "max_tokens": 200, "temperature": 0, "seed": 2026, "response_format": {"type": "json_object"}}
            result = post_json(MODEL_URL + "/v1/chat/completions", json.dumps(payload).encode(), MODEL_TIMEOUT_S)
            raw = json.loads(result["choices"][0]["message"]["content"])
            # El modelo a veces añade claves aprendidas (history); solo se conserva el texto.
            generated = {"content": str(raw.get("content", "")), "uncertainty": str(raw.get("uncertainty", "")),
                         "model_version": manifest["model_revision"]}
            if manifest.get("scope") == "technical-demo":
                validate_output(generated)
                generated["model_version"] = "demo-" + manifest["model_revision"]
                generated["uncertainty"] = "Demostración técnica con datos sintéticos, sin validación pedagógica. " + str(generated.get("uncertainty", ""))[:350]
            else:
                # El ajuste aprendió una incertidumbre de demostración; se sustituye por una fija.
                generated["uncertainty"] = UNCERTAINTY
            if not useful(str(generated.get("content", ""))):
                return self.reply(503, {"error": "unavailable"})
            self.reply(200, validate_output(generated))
        except Exception:
            self.reply(503, {"error": "unavailable"})
        finally:
            SLOTS.release()


if __name__ == "__main__":
    try:
        MODEL_TIMEOUT_S = model_timeout()
        demo = os.environ.get("TUTOR_TECHNICAL_DEMO", "0") == "1"
        if demo and os.environ.get("OJ_VERIFICATION_ONLY") != "1":
            raise ValueError("demo-only-in-verification")
        ARTIFACTS = load_artifacts(technical_demo=demo)
    except (OSError, ValueError, KeyError, TypeError) as error:
        if str(error) == "model-timeout":
            print("MODEL_TIMEOUT_S debe ser un número entre 1 y 30; readiness desactivada.", flush=True)
        else:
            print("Motor sin artefactos aprobados compatibles; readiness desactivada.", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.daemon_threads = True
    server.serve_forever()
