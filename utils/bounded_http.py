"""POST interno con plazo compartido por conexión, cabeceras y cuerpo, sin reintentos."""
import http.client
import io
import json
import math
import time
from urllib.parse import urlsplit


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("deadline")
    return value


class DeadlineReader(io.RawIOBase):
    def __init__(self, transport, deadline):
        super().__init__()
        self.transport, self.deadline = transport, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        # Se aplica en cada recv, incluso dentro de readline de las cabeceras.
        self.transport.settimeout(remaining(self.deadline))
        return self.transport.recv_into(buffer)


class DeadlineSocket:
    def __init__(self, transport, deadline):
        self.transport, self.deadline = transport, deadline

    def sendall(self, body):
        self.transport.settimeout(remaining(self.deadline))
        self.transport.sendall(body)

    def makefile(self, mode):
        if mode != "rb":
            raise ValueError("socket-mode")
        return io.BufferedReader(DeadlineReader(self.transport, self.deadline))

    def close(self):
        # HTTPConnection puede cerrar su referencia al recibir HTTP/1.0 antes
        # de leer el cuerpo. post_json conserva y cierra el transporte al final.
        pass


def post_json(url, body, timeout, max_bytes=16000):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("deadline")
    target = urlsplit(url)
    if target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password or target.fragment:
        raise ValueError("url")
    deadline = time.monotonic() + timeout
    factory = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    connection = factory(target.hostname, target.port, timeout=min(1, timeout))
    transport = None
    try:
        connection.connect()
        transport = connection.sock
        connection.sock = DeadlineSocket(transport, deadline)
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        with connection.getresponse() as response:
            if response.status != 200:
                raise ValueError("http-status")
            raw = response.read(max_bytes + 1)
        if time.monotonic() >= deadline:
            raise ValueError("deadline")
        if len(raw) > max_bytes:
            raise ValueError("size")
        return json.loads(raw)
    finally:
        connection.close()
        if transport is not None:
            transport.close()
