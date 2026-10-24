"""Contexto explícito: nunca se consultan info, casos, soluciones o SPJ."""
import html
import re

from ai_tutor.services.explainers import diagnostic


def redact(text, limit=4000):
    text = str(text or "")[:limit]
    text = re.sub(r'''(?i)\b(?:password|token|secret|api[_-]?key|username|email|phone)["']?\s*[:=]\s*(?:"[^"\n]*"|'[^'\n]*'|[^\s,;]+)''', "[dato privado omitido]", text)
    text = re.sub(r"\b(?:gh[pousr]_|github_pat_|sk-(?:proj-|svcacct-)?)[A-Za-z0-9_-]{16,}", "[credencial omitida]", text)
    text = re.sub(r"(?:redis|postgres(?:ql)?)://[^\s'\"]+", "[servicio omitido]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\b(?:\d{1,3}\.){3}\d{1,3}\b", "[dato omitido]", text)
    text = re.sub(r"(?:[A-Za-z]:[\\/]|/(?:app|data|tmp|home|etc|var)/)[^\s:'\"]+", "[ruta omitida]", text)
    return text


def public_text(value):
    return redact(html.unescape(re.sub(r"<[^>]*>", " ", value or "")))


def build_context(session, submission, action, level, concept=""):
    problem = session.problem
    return {"schema_version": "1.0", "action": action, "level": level, "concept": concept,
            "problem": {key: public_text(getattr(problem, key)) for key in
                        ("title", "description", "input_description", "output_description")},
            "code": redact(submission.code, 20000) if submission and action != "concept" else "",
            "language": submission.language if submission else "",
            "diagnostic": diagnostic(submission) if submission else {"category": "concept", "evidence": ""},
            "concepts": list(session.config_version.concepts),
            "history": list(session.attempts.order_by("-created_at").values("result", "help_level")[:3]),
            "config_version": session.config_version.version}
