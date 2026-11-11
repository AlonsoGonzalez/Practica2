"""Recorrido de punta a punta en un navegador real. Se omite si no hay node + playwright."""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _node_path():
    node, npm = shutil.which("node"), shutil.which("npm")   # rutas completas: en Windows npm es un .cmd
    if not node or not npm:
        return None
    try:
        ruta = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
        ok = subprocess.run([node, "-e", "require('playwright')"], env={**os.environ, "NODE_PATH": ruta},
                            capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None
    return ruta if ok else None


def test_recorrido_completo_en_navegador(tmp_path):
    """Licencia -> cuenta del dueño -> turno -> XSS -> venta -> cajero -> cierre con faltante -> corte."""
    node_path = _node_path()
    if node_path is None:
        pytest.skip("requiere node y playwright (npm i -g playwright)")
    llaves = tmp_path / "llaves"
    subprocess.run([sys.executable, "tools/licencias.py", "generar-llaves", "--salida", str(llaves)],
                   cwd=RAIZ, check=True, capture_output=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]
    servidor = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from pos import create_app;"
         f"create_app(sys.argv[1], public_key_pem=open(sys.argv[2],'rb').read()).run(port={puerto})",
         str(tmp_path / "e2e.db"), str(llaves / "publica.pem")],
        cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://localhost:{puerto}/api/licencia", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        r = subprocess.run(["node", "tests/e2e/flujo.js", str(puerto), str(llaves), sys.executable],
                           cwd=RAIZ, env={**os.environ, "NODE_PATH": node_path}, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        servidor.terminate()
