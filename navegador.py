"""Abrir el sistema en el navegador, aun si Windows no tiene uno predeterminado
(si no lo tiene, Windows pregunta «¿con que aplicacion quieres abrir este enlace?»)."""
import subprocess
import sys
import webbrowser


def hay_navegador_predeterminado():
    if sys.platform != "win32":
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as k:
            return bool(winreg.QueryValueEx(k, "ProgId")[0])
    except OSError:
        return False


def abrir(url):
    """Abre `url` en el navegador predeterminado; si no hay, en Microsoft Edge (viene con Windows 10 y 11)."""
    if not hay_navegador_predeterminado():
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "msedge", url], creationflags=0x08000000)
            return "edge"
        except OSError:
            pass
    webbrowser.open(url)
    return "predeterminado"
