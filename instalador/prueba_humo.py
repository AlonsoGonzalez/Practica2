#!/usr/bin/env python3
"""Prueba de humo del programa YA EMPAQUETADO (el .exe real): arranca, activa licencia, vende y cierra caja.

    python instalador/prueba_humo.py RUTA_AL_EJECUTABLE [--llaves CARPETA_CON_privada.pem] [--sin-ventana]

Sale con codigo 1 si algo falla. Se usa en el flujo de GitHub Actions sobre Windows.
"""
import argparse
import http.client
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUERTOS = range(5000, 5020)


def paso(msg):
    print(f"  OK  {msg}", flush=True)


def falla(msg):
    print(f"  FALLO  {msg}", flush=True)
    raise SystemExit(1)


def _vivo(p):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=1.5) as r:
            return json.load(r).get("app") == "punto-de-venta"
    except (OSError, ValueError, http.client.HTTPException):
        return False


def puertos_activos():
    puertos = list(PUERTOS)
    with ThreadPoolExecutor(max_workers=len(puertos)) as pool:   # en paralelo: Windows tarda en rechazar puertos cerrados
        return [p for p, vivo in zip(puertos, pool.map(_vivo, puertos)) if vivo]


class Cliente:
    def __init__(self, base):
        self.base = base
        self.abre = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())).open

    def pedir(self, metodo, ruta, cuerpo=None):
        req = urllib.request.Request(self.base + ruta, method=metodo,
                                     data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with self.abre(req, timeout=15) as r:
                return r.status, self._leer(r.read())
        except urllib.error.HTTPError as e:
            return e.code, self._leer(e.read())

    @staticmethod
    def _leer(cuerpo):
        try:
            return json.loads(cuerpo or b"null")
        except ValueError:
            return cuerpo.decode("utf-8", "replace")  # p. ej. la pagina HTML principal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--llaves", help="carpeta con privada.pem (permite probar activacion, venta y cierre)")
    ap.add_argument("--sin-ventana", action="store_true")
    ap.add_argument("--datos", help="carpeta de datos propia (POS_DATA_DIR); sin ella usa la de la instalacion real")
    a = ap.parse_args()
    env = {**os.environ, "POS_NO_BROWSER": "1", "POS_SIN_DIALOGOS": "1"}
    if a.datos:
        env["POS_DATA_DIR"] = os.path.abspath(a.datos)
    args = [a.exe] + (["--sin-ventana"] if a.sin_ventana else [])
    print(f"Probando {a.exe} {'(sin ventana)' if a.sin_ventana else '(con ventana)'}")
    if puertos_activos():
        falla("ya hay un Punto de Venta corriendo en esta maquina; cierralo antes de la prueba")
    proc = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            vivos = puertos_activos()
            if vivos:
                break
            if proc.poll() is not None:
                falla(f"el programa se cerro solo (codigo {proc.returncode})")
            time.sleep(0.5)
        else:
            falla("el programa no respondio en 60 segundos")
        c = Cliente(f"http://127.0.0.1:{vivos[0]}")
        paso(f"arranco y responde en el puerto {vivos[0]}")

        status, _ = c.pedir("GET", "/")
        status == 200 or falla(f"la pantalla principal respondio {status}")
        paso("la pantalla principal carga")

        status, lic = c.pedir("GET", "/api/licencia")
        (status == 200 and lic["estado"] == "sin_licencia") or falla(f"debia exigir licencia y dijo {lic}")
        status, _ = c.pedir("GET", "/api/productos")
        status == 402 or falla(f"sin licencia la API debia dar 402 y dio {status}")
        paso("sin licencia exige activarla (402)")

        if a.llaves:
            clave = subprocess.run(
                [sys.executable, os.path.join(RAIZ, "tools", "licencias.py"), "emitir", "--privada",
                 os.path.join(a.llaves, "privada.pem"), "--tienda", "Tienda de prueba", "--instalacion", lic["instalacion"]],
                check=True, capture_output=True, text=True).stdout.strip()
            status, r = c.pedir("POST", "/api/licencia", {"clave": clave})
            status == 200 or falla(f"no activo la licencia: {r}")
            paso("activa una licencia firmada")
            status, r = c.pedir("POST", "/api/auth/configurar", {"nombre": "Dueña", "usuario": "dueno", "password": "secreto1"})
            status == 201 or falla(f"no creo la cuenta del dueño: {r}")
            status, r = c.pedir("POST", "/api/turno/abrir", {"fondo": 100})
            status == 201 or falla(f"no abrio turno: {r}")
            status, prods = c.pedir("GET", "/api/productos")
            (status == 200 and len(prods) >= 20) or falla("el catalogo de ejemplo no cargo")
            p = prods[0]
            status, v = c.pedir("POST", "/api/ventas", {"items": [{"producto_id": p["id"], "cantidad": 1}]})
            status == 201 or falla(f"no pudo vender: {v}")
            status, cierre = c.pedir("POST", "/api/turno/cerrar", {"contado": (100 * 100 + v["total"]) / 100})
            (status == 200 and cierre["diferencia"] == 0) or falla(f"la caja no cuadro: {cierre}")
            paso("cuenta, turno, venta y cierre de caja cuadran")

        segundo = subprocess.run(args, env=env, timeout=40)
        segundo.returncode == 0 or falla(f"el segundo lanzamiento devolvio {segundo.returncode}")
        puertos_activos() == vivos or falla(f"el segundo lanzamiento abrio otra copia: {puertos_activos()}")
        paso("abrirlo otra vez no levanta una segunda copia")
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("PRUEBA DE HUMO COMPLETA")


if __name__ == "__main__":
    main()
