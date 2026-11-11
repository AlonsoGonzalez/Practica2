"""Turnos de caja: fondo inicial, retiros/ingresos, cierre con conteo ciego y diferencia.

efectivo esperado = fondo + ventas en efectivo + abonos cobrados + ingresos
                    - retiros - casco reembolsado
Las ventas a fiado no entran: ahi no se recibe dinero.
"""
from flask import Blueprint, current_app, g, jsonify

from .db import begin, get_db
from .respaldos import respaldar_seguro
from .validar import centavos, datos, texto

bp = Blueprint("caja", __name__)


def err(msg, code=400, **extra):
    return jsonify(error=msg, **extra), code


def turno_abierto(db, usuario_id):
    return db.execute(
        "SELECT * FROM turnos WHERE usuario_id=? AND cerrado IS NULL", (usuario_id,)
    ).fetchone()


def requiere_turno(db):
    """Devuelve (turno, None) o (None, respuesta_de_error) para el usuario en sesion."""
    t = turno_abierto(db, g.usuario["id"])
    if t:
        return t, None
    return None, err("Tu turno de caja está cerrado. Ábrelo en la pestaña Caja para poder cobrar.", 409, estado="sin_turno")


def _suma(db, sql, tid):
    return db.execute(sql, (tid,)).fetchone()[0] or 0


def resumen(db, t):
    tid = t["id"]
    r = {
        "fondo": t["fondo"],
        "ventas_efectivo": _suma(db, "SELECT SUM(total) FROM ventas WHERE turno_id=? AND metodo='efectivo'", tid),
        "ventas_fiado": _suma(db, "SELECT SUM(total) FROM ventas WHERE turno_id=? AND metodo='fiado'", tid),
        "num_ventas": _suma(db, "SELECT COUNT(*) FROM ventas WHERE turno_id=?", tid),
        "abonos": _suma(db, "SELECT SUM(monto) FROM abonos WHERE turno_id=?", tid),
        "cascos_reembolsados": -_suma(db, "SELECT SUM(monto) FROM casco_mov WHERE turno_id=? AND monto<0", tid),
        "ingresos": _suma(db, "SELECT SUM(monto) FROM caja_mov WHERE turno_id=? AND tipo='ingreso'", tid),
        "retiros": _suma(db, "SELECT SUM(monto) FROM caja_mov WHERE turno_id=? AND tipo='retiro'", tid),
    }
    r["esperado"] = (r["fondo"] + r["ventas_efectivo"] + r["abonos"] + r["ingresos"]
                     - r["retiros"] - r["cascos_reembolsados"])
    return r


def _turno_json(db, t, ver_todo):
    out = {k: t[k] for k in ("id", "usuario_id", "abierto", "cerrado", "fondo", "notas")}
    out["cajero"] = db.execute("SELECT nombre FROM usuarios WHERE id=?", (t["usuario_id"],)).fetchone()["nombre"]
    res = resumen(db, t)
    if t["cerrado"]:
        out.update(contado=t["contado"], esperado=t["esperado"], diferencia=t["diferencia"], resumen=res)
    elif ver_todo:
        out["resumen"] = res
    else:  # conteo ciego: el cajero no ve cuanto "deberia" haber
        out["resumen"] = {"fondo": res["fondo"], "num_ventas": res["num_ventas"]}
    return out


@bp.get("/api/turno")
def turno_actual():
    db = get_db()
    t = turno_abierto(db, g.usuario["id"])
    return jsonify(abierto=bool(t), turno=_turno_json(db, t, g.usuario["rol"] == "dueno") if t else None)


@bp.post("/api/turno/abrir")
def abrir_turno():
    d = datos()
    try:
        fondo = centavos(d.get("fondo", 0))
    except ValueError:
        return err("El fondo inicial no es válido.")
    if fondo < 0:
        return err("El fondo inicial no puede ser negativo.")
    db = get_db()
    begin()
    if turno_abierto(db, g.usuario["id"]):
        return err("Ya tienes un turno abierto.", 409)
    cur = db.execute("INSERT INTO turnos (usuario_id,fondo) VALUES (?,?)", (g.usuario["id"], fondo))
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@bp.post("/api/turno/movimiento")
def movimiento():
    d = datos()
    try:
        monto = centavos(d.get("monto"))
        motivo = texto(d.get("motivo"), 120, True)
    except ValueError:
        return err("Escribe un monto válido y el motivo del movimiento.")
    tipo = d.get("tipo")
    if tipo not in ("retiro", "ingreso") or monto <= 0:
        return err("El tipo o el monto del movimiento no son válidos.")
    db = get_db()
    begin()
    t, falla = requiere_turno(db)
    if falla:
        return falla
    if tipo == "retiro" and monto > resumen(db, t)["esperado"]:
        return err("No hay tanto efectivo en la caja para retirar esa cantidad.", 409)
    db.execute("INSERT INTO caja_mov (turno_id,tipo,monto,motivo) VALUES (?,?,?,?)", (t["id"], tipo, monto, motivo))
    db.commit()
    return jsonify(ok=True), 201


def _cerrar(db, t, d, cerrado_por):
    try:
        contado = centavos(d.get("contado"))
        notas = texto(d.get("notas"), 300)
    except ValueError:
        return err("Escribe el efectivo que contaste (un monto válido).")
    if contado < 0:
        return err("El efectivo contado no puede ser negativo.")
    esperado = resumen(db, t)["esperado"]
    db.execute(
        "UPDATE turnos SET cerrado=datetime('now','localtime'), contado=?, esperado=?, diferencia=?,"
        " notas=?, cerrado_por=? WHERE id=?",
        (contado, esperado, contado - esperado, notas, cerrado_por, t["id"]),
    )
    db.commit()
    # el cierre de turno es el mejor momento para respaldar: ya quedaron registradas las ventas del turno
    respaldar_seguro(current_app.config["DATABASE"], current_app.config["RESPALDOS_DIR"], "cierre-turno")
    cerrado = db.execute("SELECT * FROM turnos WHERE id=?", (t["id"],)).fetchone()
    return jsonify(_turno_json(db, cerrado, True))


@bp.post("/api/turno/cerrar")
def cerrar_turno():
    db = get_db()
    begin()
    t = turno_abierto(db, g.usuario["id"])
    if not t:
        return err("No tienes un turno abierto.", 409, estado="sin_turno")
    return _cerrar(db, t, datos(), g.usuario["id"])


# ---------- solo dueno ----------
@bp.get("/api/turnos")
def listar_turnos():
    from flask import request
    from datetime import date
    fecha = request.args.get("fecha")
    try:
        fecha = date.fromisoformat(fecha).isoformat() if fecha else None
    except ValueError:
        return err("La fecha no es válida. Usa el formato AAAA-MM-DD.")
    db = get_db()
    sql, params = "SELECT * FROM turnos", ()
    if fecha:
        sql, params = sql + " WHERE date(abierto)=?", (fecha,)
    rows = db.execute(sql + " ORDER BY id DESC LIMIT 200", params).fetchall()
    return jsonify([_turno_json(db, t, True) for t in rows])


@bp.get("/api/turnos/<int:tid>")
def ver_turno(tid):
    db = get_db()
    t = db.execute("SELECT * FROM turnos WHERE id=?", (tid,)).fetchone()
    if not t:
        return err("No se encontró ese turno.", 404)
    out = _turno_json(db, t, True)
    out["movimientos"] = [dict(m) for m in db.execute(
        "SELECT fecha,tipo,monto,motivo FROM caja_mov WHERE turno_id=? ORDER BY id", (tid,))]
    return jsonify(out)


@bp.post("/api/turnos/<int:tid>/cerrar")
def cerrar_turno_ajeno(tid):
    """El dueno cierra un turno que quedo abierto (p. ej. cajero desactivado o que se fue)."""
    db = get_db()
    begin()
    t = db.execute("SELECT * FROM turnos WHERE id=?", (tid,)).fetchone()
    if not t:
        return err("No se encontró ese turno.", 404)
    if t["cerrado"]:
        return err("Ese turno ya está cerrado.", 409)
    return _cerrar(db, t, datos(), g.usuario["id"])
