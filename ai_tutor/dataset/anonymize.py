"""Anonimización de entregas históricas para el dataset del tutor (PB-05).

Las funciones son puras y no consultan la base de datos: reciben instancias de
`Submission` y `Problem` (o sustitutos con los mismos atributos) y devuelven
registros conformes al contrato 1.0 de `ai_tutor.dataset.schema`.

Reglas aplicadas:
- Nunca se copian `user_id`, `username`, `ip`, `info`, ni el identificador
  interno de la entrega; los pseudónimos se generan con `rand_str`.
- La evidencia usa solo campos permitidos de `statistic_info`
  (time_cost, memory_cost, err_info, score). Nunca se lee `info`, que puede
  contener casos privados o salidas esperadas.
- El detector de información prohibida cubre los casos previstos (nombre de
  usuario de origen, correo, IP puntual, credenciales tipo clave) usando
  valores señuelo, pero no garantiza anonimización perfecta: un nombre con
  variaciones no previstas o un identificador codificado en el código pueden
  pasar y requieren revisión humana adicional (PB-07).
"""

import html
import re
from datetime import datetime, timezone

from judge.languages import languages
from submission.models import JudgeStatus
from utils.shortcuts import rand_str

SCHEMA_VERSION = "1.0"

# Contrato PB-04: veredictos -2, -1, 1, 2, 3, 4, 5 y 8. Los resultados 0, 6 y 7
# (aceptado, pendiente, evaluando) no son ejemplos de error.
EXPORTABLE_RESULTS = frozenset({
    JudgeStatus.COMPILE_ERROR, JudgeStatus.WRONG_ANSWER, JudgeStatus.CPU_TIME_LIMIT_EXCEEDED,
    JudgeStatus.REAL_TIME_LIMIT_EXCEEDED, JudgeStatus.MEMORY_LIMIT_EXCEEDED, JudgeStatus.RUNTIME_ERROR,
    JudgeStatus.SYSTEM_ERROR, JudgeStatus.PARTIALLY_ACCEPTED})
SUPPORTED_LANGUAGES = frozenset(item["name"] for item in languages)

VERDICT_TEXT = {
    JudgeStatus.COMPILE_ERROR: "Error de compilación",
    JudgeStatus.WRONG_ANSWER: "Respuesta incorrecta",
    JudgeStatus.CPU_TIME_LIMIT_EXCEEDED: "Tiempo de CPU excedido",
    JudgeStatus.REAL_TIME_LIMIT_EXCEEDED: "Tiempo real excedido",
    JudgeStatus.MEMORY_LIMIT_EXCEEDED: "Memoria excedida",
    JudgeStatus.RUNTIME_ERROR: "Error en tiempo de ejecución",
    JudgeStatus.SYSTEM_ERROR: "Error del sistema",
    JudgeStatus.PARTIALLY_ACCEPTED: "Aceptación parcial",
}

# Etiquetado automático conservador por veredicto. Solo -2 y 4 tienen causa
# factual directa; el resto queda como unknown (alternativas, confianza <= 0.5)
# y espera el diagnóstico humano de PB-07.
AUTO_DIAGNOSIS = {
    JudgeStatus.COMPILE_ERROR: ("compilation", 0.5, [], "compilation"),
    JudgeStatus.RUNTIME_ERROR: ("runtime", 0.5, [], "runtime"),
    JudgeStatus.SYSTEM_ERROR: ("unknown", 0.4, ["Fallo de infraestructura"], "infrastructure"),
    JudgeStatus.CPU_TIME_LIMIT_EXCEEDED: ("unknown", 0.4, ["Complejidad", "Fallo en ejecución"], "cost"),
    JudgeStatus.REAL_TIME_LIMIT_EXCEEDED: ("unknown", 0.4, ["Complejidad", "Fallo en ejecución"], "cost"),
    JudgeStatus.MEMORY_LIMIT_EXCEEDED: ("unknown", 0.4, ["Complejidad", "Fallo en ejecución"], "cost"),
    JudgeStatus.WRONG_ANSWER: ("unknown", 0.4, ["Lógica", "Concepto", "Formato de salida"], "answer"),
    JudgeStatus.PARTIALLY_ACCEPTED: ("unknown", 0.4, ["Lógica", "Concepto", "Formato de salida"], "answer"),
}

# Pistas genéricas por grupo de causa. Orientan sin indicar una corrección ni
# entregar una solución completa; el revisor las reescribe por registro.
GENERIC_HINTS = {
    "compilation": ("¿Qué regla sintáctica exige el lenguaje en el punto señalado?",
                    "Localiza el primer diagnóstico del compilador y obsérvalo por sí mismo.",
                    "Corrige esa regla, recompila y compara el diagnóstico siguiente."),
    "runtime": ("¿Qué operación del fragmento puede fallar durante la ejecución?",
                "Aísla la instrucción previa al estado que precede al fallo reportado.",
                "Reduce el programa a un caso mínimo que reproduzca la excepción."),
    "cost": ("¿Qué evidencia del juez separa la lentitud del fallo de acceso?",
             "Compara el tiempo o la memoria reportados con los límites del problema.",
             "Mide entradas de tamaños distintos y registra el comportamiento por escala."),
    "answer": ("¿Qué condición del enunciado podría no cumplirse?",
               "Recorre las salidas exigidas por el enunciado y busca dónde divergen.",
               "Construye un contraejemplo pequeño y compara la traza paso a paso."),
    "infrastructure": ("¿El resultado refleja el programa o el entorno de ejecución?",
                       "Comprueba si el mismo programa produce el mismo resultado al reenviarlo.",
                       "Anota el entorno y repite el envío antes de imputar la causa al código."),
}

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b")
_CREDENTIAL_RE = re.compile(r"(?i)\b(api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*[\"']?[^\s\"']{8,}")


class ForbiddenFieldsError(Exception):
    """La detección de información prohibida aborta toda la exportación."""

    def __init__(self, findings):
        self.findings = findings
        super().__init__("Campos prohibidos detectados: " + "; ".join(findings))


def html_to_text(value):
    """Reduce un campo HTML (RichTextField) a texto plano sin etiquetas."""
    if not value:
        return ""
    text = _TAG_RE.sub(" ", str(value))
    text = html.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def problem_context(problem, limit=1900):
    """Enunciado autosuficiente solo con campos públicos del problema."""
    title = html_to_text(problem.title)
    body = html_to_text(problem.description)
    if title and body:
        text = f"{title}. {body}"
    else:
        text = title or body
    if not text:
        text = f"Actividad {problem.pk}"
    remaining = limit - len(text) - 2
    if remaining > 30:
        io_text = html_to_text(problem.input_description)
        out_text = html_to_text(problem.output_description)
        pieces = []
        if io_text:
            pieces.append(f"Entrada: {io_text}")
        if out_text:
            pieces.append(f"Salida: {out_text}")
        if pieces:
            extra = " " + " ".join(pieces)
            if len(extra) <= remaining:
                text += extra
    return text[:limit].rstrip()


def build_evidence(submission):
    """Evidencia solo desde statistic_info (time_cost, memory_cost, err_info, score)."""
    evidence = [f"Veredicto reportado por el juez: {VERDICT_TEXT[submission.result]}."]
    statistic = submission.statistic_info if isinstance(submission.statistic_info, dict) else {}
    if submission.result in (JudgeStatus.CPU_TIME_LIMIT_EXCEEDED, JudgeStatus.REAL_TIME_LIMIT_EXCEEDED,
                             JudgeStatus.MEMORY_LIMIT_EXCEEDED):
        for field in ("time_cost", "memory_cost"):
            if field in statistic and _is_number(statistic[field]):
                evidence.append(f"Costo reportado por el juez (statistic_info.{field}): {statistic[field]}.")
    if submission.result == JudgeStatus.PARTIALLY_ACCEPTED and "score" in statistic and _is_number(statistic["score"]):
        score = statistic["score"]
        evidence.append(f"Puntaje parcial reportado por el juez: {score}.")
    err = statistic.get("err_info")
    if submission.result in (JudgeStatus.COMPILE_ERROR, JudgeStatus.RUNTIME_ERROR) and isinstance(err, str) and err.strip():
        evidence.append("Diagnóstico del juez (statistic_info.err_info, recortado, campos permitidos): "
                        f"{err.strip()[:1900]}")
    return evidence


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def diagnosis(submission):
    """Devuelve (category, confidence, alternatives, grupo de pistas)."""
    return AUTO_DIAGNOSIS[submission.result]


def build_review(actor, generated_at):
    """Revisión inicial honesta: borrador automático que exige diagnóstico humano."""
    author = (actor or "operacion-exportacion").strip() or "operacion-exportacion"
    return {"author": author[:100], "authored_at": generated_at, "reviewer": None, "reviewed_at": None,
            "approved_at": None, "status": "draft",
            "notes": "Registro generado por export_authorized_submissions (PB-05); sin etiquetado ni "
                     "revisión humanas. No usar para entrenar hasta completar PB-07."[:2000]}


def authorization_reference(authorization, generated_at):
    return f"Exportación PB-05 autorización {authorization} generada {generated_at}"[:300]


def build_record(submission, problem, authorization, generated_at, actor=""):
    """Construye un registro conforme al esquema; aborta si hay campos prohibidos."""
    category, confidence, alternatives, hint_group = diagnosis(submission)
    hints = {
        "concept": GENERIC_HINTS[hint_group][0],
        "location": GENERIC_HINTS[hint_group][1],
        "strategy": GENERIC_HINTS[hint_group][2],
    }
    record = {
        "schema_version": SCHEMA_VERSION,
        "example_id": generate_pseudonym(),
        "problem": problem_context(problem),
        "language": submission.language,
        "faulty_code": submission.code,
        "verdict": submission.result,
        "category": category,
        "evidence": build_evidence(submission),
        "concept": "Pendiente de diagnóstico humano",
        "explanation": f"Veredicto {submission.result} ({VERDICT_TEXT[submission.result]}) en {submission.language}. "
                       "Diagnóstico automático provisional.",
        "uncertainty": {"confidence": confidence, "alternatives": list(alternatives),
                        "reason": "Asignación automática por veredicto del juez; sin reproducción manual; "
                                  "requiere revisión humana."},
        "hints": hints,
        "provenance": {"kind": "historical", "authorization": authorization,
                       "reference": authorization_reference(authorization, generated_at)},
        "review": build_review(actor, generated_at),
    }
    return record


def generate_pseudonym():
    """Pseudónimo aleatorio no reversible para identificadores directos."""
    token = rand_str(24, "lower_str")
    return f"hist-{token}"


def generated_now():
    """Marca temporal ISO-8601 UTC de la exportación."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_text(path, text, identities):
    findings = []
    if _EMAIL_RE.search(text):
        findings.append(f"correo en {path}")
    if _IPV4_RE.search(text):
        findings.append(f"dirección IP en {path}")
    if _CREDENTIAL_RE.search(text):
        findings.append(f"credencial en {path}")
    for needle in sorted(identities):
        if not _WHITESPACE_RE.search(needle) and re.search(
                r"(?i)(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])", text):
            findings.append(f"identidad (nombre de usuario o IP de origen) en {path}")
            break
    return findings


def scan_record(record, identities):
    """Recorre cada campo y devuelve hallazgos; se aborta si alguno existe."""
    findings = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, str):
            findings.extend(_scan_text(path, value, identities))

    walk(record, "")
    return findings


def detect_forbidden_fields(record, identities):
    findings = scan_record(record, identities)
    if findings:
        raise ForbiddenFieldsError(findings)
    return findings
