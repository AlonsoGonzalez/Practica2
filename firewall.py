"""Regla del Firewall de Windows para el acceso desde tablet o celular.

Cuando Windows pregunta por el Firewall, la casilla de «Redes privadas» a veces no se marca y la tablet no puede conectarse.
Esta regla permite el programa en redes PRIVADAS y de dominio (nunca en redes publicas, como un cafe o un aeropuerto).
Crearla requiere permisos de administrador: si el programa no los tiene, Windows muestra su aviso de permiso (UAC).
"""
import subprocess
import sys
import time

NOMBRE = "Punto de Venta (acceso desde tablet)"


def es_windows():
    return sys.platform == "win32"


def argumentos_agregar(exe, nombre=NOMBRE):
    return ["advfirewall", "firewall", "add", "rule", f"name={nombre}", "dir=in", "action=allow",
            f"program={exe}", "enable=yes", "profile=private,domain", "protocol=TCP"]


def argumentos_quitar(nombre=NOMBRE):
    return ["advfirewall", "firewall", "delete", "rule", f"name={nombre}"]


def existe(nombre=NOMBRE):
    if not es_windows():
        return False
    r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={nombre}"],
                       capture_output=True, creationflags=0x08000000)   # sin ventana de consola
    return r.returncode == 0


def es_administrador():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def agregar(exe=None, elevar=True, espera=20):
    """Crea la regla. Devuelve True si quedo creada. Sin permisos de administrador pide el aviso de Windows (UAC)."""
    if not es_windows():
        return False
    exe = exe or sys.executable
    if existe():
        subprocess.run(["netsh", *argumentos_quitar()], capture_output=True, creationflags=0x08000000)
    if es_administrador():
        r = subprocess.run(["netsh", *argumentos_agregar(exe)], capture_output=True, creationflags=0x08000000)
        return r.returncode == 0
    if not elevar:
        return False
    import ctypes
    codigo = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", subprocess.list2cmdline(argumentos_agregar(exe)), None, 0)
    if codigo <= 32:      # el usuario dijo que no en el aviso de permisos
        return False
    for _ in range(int(espera * 2)):
        if existe():
            return True
        time.sleep(0.5)
    return False
