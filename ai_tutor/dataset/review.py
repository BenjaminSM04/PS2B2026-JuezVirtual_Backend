"""Lógica compartida por los comandos que registran decisiones humanas de revisión."""
from django.utils import timezone

CLOSED_STATUSES = ("approved", "rejected")
DECISIONS = ("review", "approved", "rejected")

# Columnas de contenido de la planilla: solo lectura para la persona que revisa.
CONTENT_COLUMNS = ("example_id", "language", "category", "verdict", "concept", "problem", "faulty_code",
                   "evidence", "explanation", "hint_concept", "hint_location", "hint_strategy", "author")
# Columnas que llena la persona que revisa.
HUMAN_COLUMNS = ("decision", "reviewer", "notes")
SHEET_COLUMNS = CONTENT_COLUMNS + HUMAN_COLUMNS


def is_closed(item):
    return item["review"]["status"] in CLOSED_STATUSES


def record_decision(item, reviewer, decision, notes, now=None):
    """Actualiza review con una decisión humana explícita; el llamador valida con el serializer."""
    now = now or timezone.now().isoformat()
    item["review"].update(reviewer=reviewer, reviewed_at=now, status=decision,
                          approved_at=now if decision == "approved" else None, notes=notes)


def sheet_content(item):
    """Valores de las columnas de contenido tal como se exportan y se comparan."""
    return {"example_id": item["example_id"], "language": item["language"], "category": item["category"],
            "verdict": str(item["verdict"]), "concept": item["concept"], "problem": item["problem"],
            "faulty_code": item["faulty_code"], "evidence": "\n".join(item["evidence"]),
            "explanation": item["explanation"], "hint_concept": item["hints"]["concept"],
            "hint_location": item["hints"]["location"], "hint_strategy": item["hints"]["strategy"],
            "author": item["review"]["author"]}


def normalize_cell(value):
    """Tolera los saltos de línea y espacios finales que añaden Excel y LibreOffice."""
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
