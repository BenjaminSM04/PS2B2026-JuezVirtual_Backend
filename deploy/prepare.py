"""Prepara únicamente el almacenamiento montado; nunca modifica datos existentes."""
import os
import secrets
import shutil
from pathlib import Path

data = Path(os.environ.get("OJ_DATA_DIR", "/data"))
for directory in ("config", "log", "test_case", "tmp", "public/upload", "public/avatar", "public/website"):
    (data / directory).mkdir(parents=True, exist_ok=True)

key = data / "config/secret.key"
try:
    with key.open("x") as stream:
        stream.write(secrets.token_urlsafe(64))
    key.chmod(0o600)
except FileExistsError:
    pass

for relative in ("avatar/default.png", "website/favicon.ico"):
    destination = data / "public" / relative
    if not destination.exists():
        shutil.copyfile(Path("/app/data/public") / relative, destination)
