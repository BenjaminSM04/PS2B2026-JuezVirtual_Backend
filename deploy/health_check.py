"""Comprueba procesos y disponibilidad real de Django, PostgreSQL y Redis."""
import socket
import sys
import urllib.request
import xmlrpc.client

socket.setdefaulttimeout(3)
try:
    with xmlrpc.client.ServerProxy("http://127.0.0.1:9005/RPC2") as supervisor:
        processes = supervisor.supervisor.getAllProcessInfo()
        if len(processes) != 3 or any(process["state"] != 20 for process in processes):
            raise RuntimeError("Hay procesos detenidos")
    with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=4) as response:
        if response.status != 200:
            raise RuntimeError("La aplicación no está preparada")
except Exception:
    print("Comprobación de salud fallida; revisar los logs del servicio.", file=sys.stderr)
    sys.exit(1)
