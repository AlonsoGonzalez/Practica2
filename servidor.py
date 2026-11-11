"""Punto de entrada de produccion: lo que ejecuta el instalador.

Sirve la app con waitress en esta misma computadora y abre el navegador.
Variables opcionales:
  POS_PORT   puerto (por defecto 5000; si esta ocupado prueba los siguientes)
  POS_LAN=1  escuchar en toda la red local para usar la caja desde una tablet/celular
"""
import os
import socket
import threading
import webbrowser

from waitress import serve

from pos import create_app, paths
from pos.respaldos import respaldar


def puerto_libre(host, inicial):
    for puerto in range(inicial, inicial + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:  # nadie escucha: esta libre
                return puerto
    raise RuntimeError("No hay un puerto libre entre %d y %d" % (inicial, inicial + 19))


def main():
    app = create_app()
    respaldar(app.config["DATABASE"], os.path.join(paths.datos_dir(), "respaldos"))
    lan = os.environ.get("POS_LAN") == "1"
    host = "0.0.0.0" if lan else "127.0.0.1"
    puerto = puerto_libre(host, int(os.environ.get("POS_PORT", 5000)))
    url = f"http://localhost:{puerto}"
    print(f"Punto de Venta listo en {url}  (datos en {paths.datos_dir()})")
    print("Deja esta ventana abierta mientras uses el sistema. Cierrala para apagarlo.")
    if os.environ.get("POS_NO_BROWSER") != "1":
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    serve(app, host=host, port=puerto, threads=4)


if __name__ == "__main__":
    main()
