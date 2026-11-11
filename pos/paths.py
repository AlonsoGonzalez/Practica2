"""Rutas de datos. En el instalador los datos viven fuera de la carpeta del programa,
asi que actualizar o desinstalar la app no borra la base de datos de la tienda."""
import os
import sys

NOMBRE_APP = "PuntoVentaAbarrotes"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def empaquetada():
    return bool(getattr(sys, "frozen", False))


def recurso(*partes):
    """Ruta a un archivo incluido con la app (funciona en desarrollo y empaquetada)."""
    base = getattr(sys, "_MEIPASS", RAIZ)
    return os.path.join(base, *partes)


def datos_dir():
    if os.environ.get("POS_DATA_DIR"):
        ruta = os.environ["POS_DATA_DIR"]
    elif not empaquetada():
        ruta = RAIZ
    elif sys.platform == "win32":
        ruta = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), NOMBRE_APP)
    elif sys.platform == "darwin":
        ruta = os.path.expanduser(f"~/Library/Application Support/{NOMBRE_APP}")
    else:
        ruta = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), NOMBRE_APP)
    os.makedirs(ruta, exist_ok=True)
    return ruta
