from pathlib import PurePosixPath
from utils.api import APIError


def validate_archive(archive):
    entries = archive.infolist()
    if len(entries) > 20000 or sum(item.file_size for item in entries) > 512 * 1024 * 1024:
        raise APIError("El ZIP supera el límite de archivos o de tamaño descomprimido.")
    names = set()
    for item in entries:
        path = PurePosixPath(item.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in item.filename or item.filename in names:
            raise APIError("El ZIP contiene rutas inseguras o nombres duplicados.")
        names.add(item.filename)
        if item.flag_bits & 1 or (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise APIError("No se admiten entradas cifradas ni enlaces simbólicos.")
        if item.file_size > 64 * 1024 * 1024 or item.file_size > max(1, item.compress_size) * 1000:
            raise APIError("El ZIP contiene una entrada demasiado grande o una compresión excesiva.")
