# PyInstaller: genera dist/PuntoDeVenta/ (carpeta con el ejecutable y sus dependencias)
# Uso (desde la raiz del repo):  pyinstaller --noconfirm instalador/pos.spec
import os

raiz = os.path.abspath(os.path.join(SPECPATH, ".."))
llave = os.path.join(raiz, "pos", "clave_publica.pem")
if not os.path.exists(llave):
    raise SystemExit("Falta pos/clave_publica.pem: genera tus llaves con tools/licencias.py generar-llaves "
                     "y copia publica.pem ahi. Sin ella el instalador no podria validar licencias.")

a = Analysis(
    [os.path.join(raiz, "servidor.py")],
    pathex=[raiz],
    datas=[
        (os.path.join(raiz, "pos", "templates"), os.path.join("pos", "templates")),
        (os.path.join(raiz, "pos", "static"), os.path.join("pos", "static")),
        (llave, "pos"),
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PuntoDeVenta", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="PuntoDeVenta")
