"""Respaldos desde la aplicacion: listar, respaldar ahora y restaurar (solo el dueno)."""
from flask import Blueprint, current_app, jsonify

from . import db as basedatos
from . import respaldos
from .validar import datos

bp = Blueprint("sistema", __name__)


def _err(msg, code=400):
    return jsonify(error=msg), code


@bp.get("/api/respaldos")
def listar_respaldos():
    return jsonify(respaldos.listar(current_app.config["RESPALDOS_DIR"]))


@bp.post("/api/respaldos")
def respaldar_ahora():
    ruta = respaldos.respaldar_seguro(current_app.config["DATABASE"], current_app.config["RESPALDOS_DIR"], "manual")
    if not ruta:
        return _err("No se pudo crear el respaldo. Revisa que haya espacio en el disco.", 500)
    return jsonify(archivo=ruta.replace("\\", "/").rsplit("/", 1)[-1]), 201


@bp.post("/api/respaldos/restaurar")
def restaurar_respaldo():
    archivo = datos().get("archivo")
    if not isinstance(archivo, str):
        return _err("Indica cuál respaldo restaurar.")
    try:
        respaldos.restaurar(current_app.config["DATABASE"], current_app.config["RESPALDOS_DIR"], archivo)
    except FileNotFoundError:
        return _err("Ese respaldo ya no existe.", 404)
    except ValueError as e:
        return _err(str(e))
    basedatos.init_db()   # por si el respaldo es de una version anterior: agrega columnas y tablas nuevas
    return jsonify(ok=True)
