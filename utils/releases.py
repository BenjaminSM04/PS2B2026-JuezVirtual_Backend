"""Notas del repositorio instalado; sin consultas externas ni HTML ejecutable."""
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/incubadoradesarrollo-source/B-LIZARD-JUDGE"


def release_notes(root=ROOT):
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", version):
        raise ValueError("Versión del repositorio inválida")
    revision = os.environ.get("APP_REVISION", "desarrollo")
    ref = revision if re.fullmatch(r"[a-f0-9]{40}", revision) else "main"
    source = REPOSITORY + "/blob/" + ref + "/CHANGELOG.md"
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if len(text.encode("utf-8")) > 131072:
        raise ValueError("Historial demasiado grande")
    updates = []
    current = None
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            match = re.fullmatch(r"## \[(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)\](?: - (\d{4}-\d{2}-\d{2}))?", line)
            current = None
            section = ""
            if match and len(updates) < 12:
                current = {"version": match[1], "title": "LizardJudge " + match[1],
                           "date": match[2] or "", "details": [], "source_url": source,
                           "is_current": match[1] == version}
                updates.append(current)
        elif line.startswith("### "):
            section = line[4:].strip()
        elif current is not None and line.startswith("- "):
            current["details"].append((section + ": " if section else "") + line[2:].strip())
    return {"local_version": version, "revision": revision, "source_url": source, "update": updates}
