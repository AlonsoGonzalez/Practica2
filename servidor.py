"""Punto de entrada de produccion: lo que ejecuta el instalador (doble clic, sin terminal).

Arranca el servidor en esta computadora, abre el navegador y muestra una ventanita de control.
Si ya estaba abierto, solo vuelve a abrir el navegador (nunca levanta dos copias).

Opciones (solo para soporte tecnico):
  --lan          permitir acceso desde tablets/celulares (tambien se activa desde la ventana)
  --sin-ventana  modo consola, sin ventana (servidores, pruebas)
  --apagar-tablet  desactiva el acceso desde tablets/celulares y termina (lo usa el instalador)
  --permitir-firewall  crea la regla del Firewall de Windows para redes privadas y termina
  POS_PORT       puerto preferido (por defecto 5000)
  POS_NO_BROWSER=1  no abrir el navegador
"""
import argparse
import http.client
import json
import logging
import os
import socket
import sys
import threading
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from waitress import create_server

import navegador
from pos import config, create_app, paths
from pos.respaldos import respaldar_seguro

PUERTO_INICIAL = 5000
INTERVALO_RESPALDO_HORAS = 4


def puerto_libre(host, inicial):
    for puerto in range(inicial, inicial + 20):
        with socket.socket() as s:
            s.settimeout(1)  # en Windows conectar a un puerto cerrado puede tardar varios segundos
            if s.connect_ex(("127.0.0.1", puerto)) != 0:  # nadie escucha: esta libre
                return puerto
    raise RuntimeError("No hay un puerto libre entre %d y %d" % (inicial, inicial + 19))


def _es_nuestra_app(puerto):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/ping", timeout=1.5) as r:
            return json.load(r).get("app") == "punto-de-venta"
    except (OSError, ValueError, AttributeError, http.client.HTTPException):
        # HTTPException: p. ej. una "autoconexion" TCP (el puerto se conecto consigo mismo y devolvio la propia peticion)
        return False


def ya_corriendo(inicial=PUERTO_INICIAL):
    """Puerto de un Punto de Venta que ya esta abierto en esta computadora (o None).
    Revisa los puertos en paralelo: asi tarda ~1 s aunque Windows sea lento con puertos cerrados."""
    puertos = list(range(inicial, inicial + 20))
    with ThreadPoolExecutor(max_workers=len(puertos)) as pool:
        for puerto, es_nuestra in zip(puertos, pool.map(_es_nuestra_app, puertos)):
            if es_nuestra:
                return puerto
    return None


def urls_lan(puerto):
    """Direcciones con las que otro dispositivo de la red puede entrar a esta computadora."""
    urls = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no envia nada: solo elige la interfaz de red
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                urls.append(f"http://{ip}:{puerto}")
    except OSError:
        pass
    urls.append(f"http://{socket.gethostname()}:{puerto}")
    return urls


class Servidor:
    """Servidor waitress en un hilo, que se puede detener y reiniciar (para activar/desactivar la tablet)."""

    def __init__(self, app, lan=False, puerto_inicial=PUERTO_INICIAL):
        self.app, self.lan, self.puerto_inicial = app, lan, puerto_inicial
        self.puerto, self._server, self._hilo = None, None, None

    @property
    def url(self):
        return f"http://localhost:{self.puerto}"

    def urls_lan(self):
        return urls_lan(self.puerto) if self.lan else []

    def iniciar(self):
        host = "0.0.0.0" if self.lan else "127.0.0.1"
        self.puerto = puerto_libre(host, self.puerto_inicial)
        self._server = create_server(self.app, host=host, port=self.puerto, threads=4)
        self.app.config["LAN_URLS"] = self.urls_lan()
        self._hilo = threading.Thread(target=self._server.run, daemon=True)
        self._hilo.start()

    def detener(self):
        if self._server:
            self._server.close()
            self._hilo.join(10)
            self._server = None

    def reiniciar(self, lan):
        """Cambia el modo de red conservando el mismo puerto; si falla, vuelve a como estaba."""
        anterior, puerto = self.lan, self.puerto
        self.detener()
        self.lan, self.puerto_inicial = lan, puerto
        try:
            self.iniciar()
        except OSError:
            self.lan = anterior
            self.iniciar()
            raise


def configurar_salida():
    """Sin consola (version instalada) no hay stdout: todo va a un archivo de registro."""
    registro = os.path.join(paths.datos_dir(), "logs")
    os.makedirs(registro, exist_ok=True)
    ruta = os.path.join(registro, "pos.log")
    if sys.stdout is None or sys.stderr is None:
        sys.stdout = sys.stderr = open(ruta, "a", encoding="utf-8", buffering=1)
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    if not any(getattr(h, "baseFilename", None) == os.path.abspath(ruta) for h in raiz.handlers):
        h = logging.FileHandler(ruta, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        raiz.addHandler(h)
    return ruta


def avisar_error(titulo, mensaje):
    if os.environ.get("POS_SIN_DIALOGOS") == "1":  # pruebas automaticas: nadie puede dar clic en una ventana
        print(f"{titulo}: {mensaje}")
        return
    try:
        import tkinter
        from tkinter import messagebox
        raiz = tkinter.Tk(); raiz.withdraw()
        messagebox.showerror(titulo, mensaje)
        raiz.destroy()
    except Exception:  # sin pantalla o sin tkinter: queda en el registro
        print(f"{titulo}: {mensaje}")


def bucle_consola(srv):
    print(f"Punto de Venta listo en {srv.url}  (datos en {paths.datos_dir()})")
    for u in srv.urls_lan():
        print("   Desde la tablet o el celular:", u)
    print("Deja esta ventana abierta mientras uses el sistema. Cierrala para apagarlo.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.detener()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Punto de Venta")
    ap.add_argument("--lan", action="store_true", help="permitir acceso desde otros dispositivos de la red")
    ap.add_argument("--sin-ventana", action="store_true", help="modo consola, sin ventana")
    ap.add_argument("--apagar-tablet", action="store_true", help="desactiva el acceso desde tablets y termina")
    ap.add_argument("--permitir-firewall", action="store_true", help="crea la regla del Firewall (redes privadas) y termina")
    args = ap.parse_args(argv)
    if args.permitir_firewall:
        import firewall
        return 0 if firewall.agregar() else 1
    if args.apagar_tablet:   # el instalador lo ejecuta: una instalacion nueva nunca queda visible en la red sin avisar
        config.guardar({**config.cargar(), "lan": False})
        return 0
    registro = configurar_salida()
    abrir = os.environ.get("POS_NO_BROWSER") != "1"

    existente = ya_corriendo(int(os.environ.get("POS_PORT", PUERTO_INICIAL)))
    if existente:  # doble clic con la app ya abierta: solo se vuelve a abrir el navegador
        if abrir:
            navegador.abrir(f"http://localhost:{existente}")
        return 0
    try:
        app = create_app()
        db_path, carpeta = app.config["DATABASE"], app.config["RESPALDOS_DIR"]
        respaldar_seguro(db_path, carpeta, "inicio")
        parar_respaldos = threading.Event()
        horas = float(os.environ.get("POS_RESPALDO_HORAS", INTERVALO_RESPALDO_HORAS))

        def respaldos_periodicos():   # ademas de abrir y cerrar turno: asi nunca se pierde mas de unas horas
            while not parar_respaldos.wait(horas * 3600):
                respaldar_seguro(db_path, carpeta, "auto")

        threading.Thread(target=respaldos_periodicos, daemon=True).start()
        cfg = config.cargar()
        srv = Servidor(app, lan=args.lan or cfg["lan"], puerto_inicial=int(os.environ.get("POS_PORT", PUERTO_INICIAL)))
        srv.iniciar()
        logging.info("Servidor listo en %s", srv.url)
        abrir_url = lambda: navegador.abrir(srv.url)
        if abrir:
            threading.Timer(1.0, abrir_url).start()
        if not args.sin_ventana:
            try:
                import ventana
                ventana.correr(srv, abrir_url, carpeta, lambda v: config.guardar({**cfg, "lan": v}))
                parar_respaldos.set()
                respaldar_seguro(db_path, carpeta, "al-cerrar")
                return 0
            except ImportError:  # esta instalacion de Python no trae tkinter
                logging.warning("Sin tkinter: modo consola")
            except Exception as e:  # TclError: no hay pantalla
                if e.__class__.__name__ != "TclError":
                    raise
                logging.warning("Sin pantalla: modo consola")
        bucle_consola(srv)
        parar_respaldos.set()
        respaldar_seguro(db_path, carpeta, "al-cerrar")
        return 0
    except Exception:
        logging.exception("El sistema no pudo arrancar")
        avisar_error("Punto de Venta", "El sistema no pudo arrancar.\n\nDetalle técnico guardado en:\n" + registro
                     + "\n\n" + traceback.format_exc().splitlines()[-1])
        return 1


if __name__ == "__main__":
    sys.exit(main())
