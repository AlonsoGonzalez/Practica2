"""Punto de entrada de produccion: lo que ejecuta el instalador.

Sirve la app con waitress en esta misma computadora y abre el navegador.
Opciones:
  --lan      (o POS_LAN=1) permite entrar desde una tablet/celular de la misma red Wi-Fi
  POS_PORT   puerto (por defecto 5000; si esta ocupado prueba los siguientes)
"""
import argparse
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


def main():
    ap = argparse.ArgumentParser(description="Punto de Venta")
    ap.add_argument("--lan", action="store_true", help="permitir acceso desde otros dispositivos de la red")
    args = ap.parse_args()
    app = create_app()
    respaldar(app.config["DATABASE"], os.path.join(paths.datos_dir(), "respaldos"))
    lan = args.lan or os.environ.get("POS_LAN") == "1"
    host = "0.0.0.0" if lan else "127.0.0.1"
    puerto = puerto_libre(host, int(os.environ.get("POS_PORT", 5000)))
    url = f"http://localhost:{puerto}"
    print(f"Punto de Venta listo en {url}  (datos en {paths.datos_dir()})")
    if lan:
        app.config["LAN_URLS"] = urls_lan(puerto)
        print("Desde la tablet o el celular (mismo Wi-Fi) abre:")
        for u in app.config["LAN_URLS"]:
            print("   ", u)
        print("Si Windows pregunta por el Firewall, permite el acceso en redes privadas.")
    print("Deja esta ventana abierta mientras uses el sistema. Cierrala para apagarlo.")
    if os.environ.get("POS_NO_BROWSER") != "1":
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    serve(app, host=host, port=puerto, threads=4)


if __name__ == "__main__":
    main()
