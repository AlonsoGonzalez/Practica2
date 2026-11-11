"""Respaldos de la base de datos.

Nombre: pos-AAAA-MM-DD_HH-MM-SS-<motivo>.db   (motivo: inicio, auto, cierre-turno, al-cerrar, manual, antes-de-restaurar)
Se hacen: al abrir el sistema, cada pocas horas, al cerrar un turno, al cerrar el sistema y a mano.
Se conservan: todo lo de las ultimas 24 h + el ultimo de cada dia de los ultimos 30 dias.
"""
import glob
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta

PATRON = re.compile(r"^pos-(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})(?:-([a-z\-]+))?\.db$")
PATRON_VIEJO = re.compile(r"^pos-(\d{4}-\d{2}-\d{2})\.db$")   # respaldos de versiones anteriores
HORAS_COMPLETAS, DIAS_HISTORIAL = 24, 30
TABLAS_ESPERADAS = {"productos", "ventas", "usuarios", "turnos"}


def _fecha_de(nombre):
    """(datetime, motivo) del nombre de un respaldo, o None si no es uno de los nuestros."""
    m = PATRON.match(nombre)
    if m:
        return datetime.strptime(f"{m[1]} {m[2]}", "%Y-%m-%d %H-%M-%S"), m[3] or ""
    m = PATRON_VIEJO.match(nombre)
    if m:
        return datetime.strptime(m[1], "%Y-%m-%d"), "antiguo"
    return None


def listar(destino):
    """Respaldos disponibles, el mas reciente primero."""
    out = []
    for ruta in glob.glob(os.path.join(destino, "pos-*.db")):
        nombre = os.path.basename(ruta)
        parsed = _fecha_de(nombre)
        if parsed:
            out.append({"archivo": nombre, "fecha": parsed[0].strftime("%Y-%m-%d %H:%M:%S"),
                        "motivo": parsed[1], "bytes": os.path.getsize(ruta)})
    return sorted(out, key=lambda r: r["fecha"], reverse=True)


def rotar(destino, ahora=None):
    ahora = ahora or datetime.now()
    limite_completo = ahora - timedelta(hours=HORAS_COMPLETAS)
    limite_historial = (ahora - timedelta(days=DIAS_HISTORIAL)).date()
    conservar, vistos = set(), set()
    for r in listar(destino):                       # del mas nuevo al mas viejo
        f = datetime.strptime(r["fecha"], "%Y-%m-%d %H:%M:%S")
        if f >= limite_completo:
            conservar.add(r["archivo"])
        elif f.date() >= limite_historial and f.date() not in vistos:
            conservar.add(r["archivo"])             # el ultimo respaldo de ese dia
        vistos.add(f.date())
    for r in listar(destino):
        if r["archivo"] not in conservar:
            os.remove(os.path.join(destino, r["archivo"]))


def respaldar(db_path, destino, motivo="auto", ahora=None, limpiar=True):
    """Copia consistente de la base (API de respaldo de SQLite). Devuelve la ruta del archivo o None."""
    if not os.path.exists(db_path):
        return None
    if not re.fullmatch(r"[a-z\-]*", motivo):
        raise ValueError("motivo invalido")
    os.makedirs(destino, exist_ok=True)
    ahora = ahora or datetime.now()
    archivo = os.path.join(destino, f"pos-{ahora:%Y-%m-%d_%H-%M-%S}" + (f"-{motivo}" if motivo else "") + ".db")
    if not os.path.exists(archivo):
        temporal = archivo + ".tmp"                 # nunca queda un respaldo a medias con nombre valido
        origen, copia = sqlite3.connect(db_path), sqlite3.connect(temporal)
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
        os.replace(temporal, archivo)
    if limpiar:
        rotar(destino, ahora)
    return archivo


def respaldar_seguro(db_path, destino, motivo="auto"):
    """Como respaldar(), pero un fallo (disco lleno, carpeta sin permiso, base danada)
    se registra y NO impide trabajar."""
    try:
        return respaldar(db_path, destino, motivo)
    except (OSError, sqlite3.Error, ValueError) as e:
        logging.getLogger("pos").warning("No se pudo respaldar la base: %s", e)
        return None


def validar(ruta):
    """Lanza ValueError si el archivo no es un respaldo sano de esta aplicacion."""
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("El respaldo esta danado")
            tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except sqlite3.Error:
        raise ValueError("El archivo no es una base de datos valida")
    if not TABLAS_ESPERADAS <= tablas:
        raise ValueError("El archivo no es un respaldo de este sistema")


def restaurar(db_path, destino, archivo):
    """Reemplaza el contenido de la base por el del respaldo `archivo` (solo el nombre, sin rutas).
    Antes guarda una copia de lo actual ('antes-de-restaurar')."""
    if os.path.basename(archivo) != archivo or not _fecha_de(archivo):
        raise ValueError("Nombre de respaldo invalido")
    ruta = os.path.join(destino, archivo)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(archivo)
    validar(ruta)
    respaldar(db_path, destino, "antes-de-restaurar", limpiar=False)   # restaurar nunca limpia respaldos: no se borra el elegido
    origen, vivo = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True), sqlite3.connect(db_path, timeout=30)
    try:
        origen.backup(vivo)
    finally:
        vivo.close()
        origen.close()
