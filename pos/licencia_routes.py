from datetime import date

from flask import Blueprint, current_app, jsonify, request

from . import licencia as lic
from .db import get_db
from .validar import datos

bp = Blueprint("licencia", __name__)


def instalacion_id():
    db = get_db()
    row = db.execute("SELECT valor FROM ajustes WHERE clave='instalacion_id'").fetchone()
    if row:
        return row["valor"]
    nuevo = lic.nuevo_id_instalacion()
    db.execute("INSERT INTO ajustes (clave,valor) VALUES ('instalacion_id',?)", (nuevo,))
    db.commit()
    return nuevo


def fecha_efectiva():
    """Hoy, pero nunca anterior a la fecha mas reciente que la app ya vio.
    Asi, regresar el reloj de la computadora no revive una licencia de prueba vencida."""
    db = get_db()
    hoy = date.today()
    row = db.execute("SELECT valor FROM ajustes WHERE clave='fecha_max'").fetchone()
    try:
        maxima = date.fromisoformat(row["valor"]) if row else hoy
    except ValueError:
        maxima = hoy
    if hoy > maxima or row is None:
        db.execute("INSERT OR REPLACE INTO ajustes (clave,valor) VALUES ('fecha_max',?)", (hoy.isoformat(),))
        db.commit()
        maxima = max(hoy, maxima)
    return max(hoy, maxima)


def estado_actual():
    row = get_db().execute("SELECT clave FROM licencia WHERE id=1").fetchone()
    return lic.evaluar(
        row["clave"] if row else None,
        current_app.config["LICENSE_PUBLIC_KEY"],
        instalacion_id(),
        current_app.config["FECHA_VERSION"],
        hoy=fecha_efectiva(),
    )


def describir(estado, payload):
    return {
        "estado": estado,
        "activa": estado in (lic.ACTIVA, lic.DESARROLLO),
        "mensaje": lic.MENSAJES.get(estado, ""),
        "instalacion": instalacion_id(),
        "tienda": (payload or {}).get("tienda"),
        "tipo": (payload or {}).get("tipo"),
        "actualizaciones_hasta": (payload or {}).get("actualizaciones_hasta"),
        "expira": (payload or {}).get("expira"),
    }


@bp.get("/api/licencia")
def ver_licencia():
    return jsonify(describir(*estado_actual()))


@bp.post("/api/licencia")
def activar_licencia():
    clave = lic.normalizar(datos().get("clave"))
    llave = current_app.config["LICENSE_PUBLIC_KEY"]
    if llave is None:
        return jsonify(error="Modo desarrollo: no hay llave publica configurada"), 400
    estado, payload = lic.evaluar(
        clave, llave, instalacion_id(), current_app.config["FECHA_VERSION"]
    )
    if estado != lic.ACTIVA:
        return jsonify(error=lic.MENSAJES.get(estado, "Licencia no valida"), estado=estado), 400
    db = get_db()
    db.execute(
        "INSERT INTO licencia (id,clave) VALUES (1,?)"
        " ON CONFLICT(id) DO UPDATE SET clave=excluded.clave, activada=datetime('now','localtime')",
        (clave,),
    )
    db.commit()
    return jsonify(describir(estado, payload))


def exigir_licencia():
    """before_request: bloquea la API si la licencia no esta activa."""
    path = request.path
    if not path.startswith("/api/") or path.startswith(("/api/licencia", "/api/ping")):
        return None
    estado, payload = estado_actual()
    if estado in (lic.ACTIVA, lic.DESARROLLO):
        return None
    return jsonify(error=lic.MENSAJES.get(estado, "Licencia no valida"), estado=estado), 402
