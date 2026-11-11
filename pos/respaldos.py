import glob
import logging
import os
import sqlite3
from datetime import date


def respaldar(db_path, destino, conservar=14, hoy=None):
    """Copia consistente de la base (API de respaldo de SQLite). Uno por dia; conserva los ultimos N."""
    if not os.path.exists(db_path):
        return None
    os.makedirs(destino, exist_ok=True)
    archivo = os.path.join(destino, f"pos-{(hoy or date.today()).isoformat()}.db")
    if not os.path.exists(archivo):
        origen, copia = sqlite3.connect(db_path), sqlite3.connect(archivo)
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
    for viejo in sorted(glob.glob(os.path.join(destino, "pos-*.db")))[:-conservar]:
        os.remove(viejo)
    return archivo


def respaldar_seguro(db_path, destino, conservar=14):
    """Como respaldar(), pero un fallo (disco lleno, carpeta sin permiso, base danada)
    se registra y NO impide que la tienda abra su sistema."""
    try:
        return respaldar(db_path, destino, conservar)
    except (OSError, sqlite3.Error) as e:
        logging.getLogger("pos").warning("No se pudo respaldar la base: %s", e)
        return None
