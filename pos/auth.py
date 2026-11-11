"""Usuarios, sesiones y permisos.

Roles:
  dueno   acceso total (inventario, costos, corte, pedidos, usuarios).
  cajero  solo cobrar, consultar productos (sin costos), fiado/abonos y devolucion de envases.
"""
import secrets
import time

from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .validar import datos as cuerpo

bp = Blueprint("auth", __name__)

ROLES = ("dueno", "cajero")
MIN_PASSWORD = 6
MAX_PASSWORD = 200
INTENTOS, VENTANA = 5, 300  # 5 fallos por usuario+IP cada 5 minutos

CAJERO_PERMITIDO = {
    "pos.listar_productos", "pos.crear_venta", "pos.ver_venta",
    "pos.listar_clientes", "pos.crear_cliente", "pos.ver_cliente", "pos.abonar",
    "pos.devolucion_envases",
    "caja.turno_actual", "caja.abrir_turno", "caja.movimiento", "caja.cerrar_turno",
}
HASH_FALSO = generate_password_hash("sin-usuario")  # iguala el tiempo de respuesta si el usuario no existe


def err(msg, code=400, **extra):
    return jsonify(error=msg, **extra), code


def publico(u):
    return {"id": u["id"], "nombre": u["nombre"], "usuario": u["usuario"], "rol": u["rol"]}


def hay_usuarios():
    return get_db().execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0


def clave_secreta():
    """Clave de firma de cookies, generada una vez y guardada en la base."""
    db = get_db()
    row = db.execute("SELECT valor FROM ajustes WHERE clave='secret_key'").fetchone()
    if row:
        return row["valor"]
    nueva = secrets.token_hex(32)
    db.execute("INSERT INTO ajustes (clave,valor) VALUES ('secret_key',?)", (nueva,))
    db.commit()
    return nueva


def _iniciar_sesion(u):
    session.clear()
    session.permanent = True
    session["uid"], session["sv"] = u["id"], u["sesion_version"]


def exigir_login():
    """before_request (despues de la licencia): identifica al usuario y aplica permisos por rol."""
    g.usuario = None
    path = request.path
    if not path.startswith("/api/") or path.startswith(("/api/licencia", "/api/auth/")):
        return None
    uid = session.get("uid")
    if uid:
        u = get_db().execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (uid,)).fetchone()
        if u and u["sesion_version"] == session.get("sv"):
            g.usuario = u
    if g.usuario is None:
        return err("Inicia sesion para continuar", 401, estado="sin_sesion")
    if g.usuario["rol"] != "dueno" and request.endpoint not in CAJERO_PERMITIDO:
        return err("No tienes permiso para esta accion", 403)
    return None


def _cargar_usuario_para_auth():
    uid = session.get("uid")
    if not uid:
        return None
    u = get_db().execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (uid,)).fetchone()
    return u if u and u["sesion_version"] == session.get("sv") else None


def _validar_alta(d):
    nombre = str(d.get("nombre") or "").strip()
    usuario = str(d.get("usuario") or "").strip()
    password = str(d.get("password") or "")
    if not nombre or not usuario or " " in usuario or len(nombre) > 60 or len(usuario) > 40:
        return None, "Nombre y usuario son obligatorios (el usuario no lleva espacios, maximo 40 caracteres)"
    if len(password) < MIN_PASSWORD or len(password) > MAX_PASSWORD:
        return None, f"La contrasena debe tener entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres"
    return (nombre, usuario, password), None


# ---------- sesion ----------
@bp.get("/api/auth/yo")
def yo():
    u = _cargar_usuario_para_auth()
    return jsonify(configurado=hay_usuarios(), usuario=publico(u) if u else None)


@bp.post("/api/auth/configurar")
def configurar():
    """Primer uso: crea la cuenta del dueno. Despues de eso queda cerrado."""
    if hay_usuarios():
        return err("El sistema ya esta configurado", 409)
    datos, error = _validar_alta(cuerpo())
    if error:
        return err(error)
    nombre, usuario, password = datos
    db = get_db()
    cur = db.execute(
        "INSERT INTO usuarios (nombre,usuario,hash,rol) VALUES (?,?,?, 'dueno')",
        (nombre, usuario, generate_password_hash(password)),
    )
    db.commit()
    u = db.execute("SELECT * FROM usuarios WHERE id=?", (cur.lastrowid,)).fetchone()
    _iniciar_sesion(u)
    return jsonify(usuario=publico(u)), 201


@bp.post("/api/auth/login")
def login():
    d = cuerpo()
    usuario, password = str(d.get("usuario") or "").strip()[:100], str(d.get("password") or "")[:MAX_PASSWORD + 1]
    fallos = current_app.extensions.setdefault("pos_fallos", {})
    llave = (usuario.lower(), request.remote_addr)
    ahora = time.time()
    recientes = [t for t in fallos.get(llave, []) if ahora - t < VENTANA]
    if len(recientes) >= INTENTOS:
        return err("Demasiados intentos. Espera unos minutos.", 429)
    u = get_db().execute("SELECT * FROM usuarios WHERE usuario=? AND activo=1", (usuario,)).fetchone()
    ok = check_password_hash(u["hash"] if u else HASH_FALSO, password)
    if not (u and ok):
        fallos[llave] = recientes + [ahora]
        return err("Usuario o contrasena incorrectos", 401)
    fallos.pop(llave, None)
    _iniciar_sesion(u)
    return jsonify(usuario=publico(u))


@bp.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post("/api/auth/password")
def cambiar_password():
    u = _cargar_usuario_para_auth()
    if not u:
        return err("Inicia sesion para continuar", 401, estado="sin_sesion")
    d = cuerpo()
    if not check_password_hash(u["hash"], str(d.get("actual") or "")):
        return err("La contrasena actual no es correcta", 403)
    nueva = str(d.get("nueva") or "")
    if not MIN_PASSWORD <= len(nueva) <= MAX_PASSWORD:
        return err(f"La contrasena debe tener entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres")
    db = get_db()
    db.execute("UPDATE usuarios SET hash=?, sesion_version=sesion_version+1 WHERE id=?",
               (generate_password_hash(nueva), u["id"]))
    db.commit()
    _iniciar_sesion(db.execute("SELECT * FROM usuarios WHERE id=?", (u["id"],)).fetchone())
    return jsonify(ok=True)


# ---------- administracion de usuarios (solo dueno) ----------
@bp.get("/api/usuarios")
def listar_usuarios():
    rows = get_db().execute(
        "SELECT id,nombre,usuario,rol,activo FROM usuarios ORDER BY activo DESC, nombre"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/usuarios")
def crear_usuario():
    d = cuerpo()
    datos, error = _validar_alta(d)
    if error:
        return err(error)
    rol = d.get("rol", "cajero")
    if rol not in ROLES:
        return err("Rol invalido")
    nombre, usuario, password = datos
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO usuarios (nombre,usuario,hash,rol) VALUES (?,?,?,?)",
            (nombre, usuario, generate_password_hash(password), rol),
        )
    except Exception:
        return err("Ya existe un usuario con ese nombre de usuario", 409)
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@bp.put("/api/usuarios/<int:uid>")
def editar_usuario(uid):
    d = cuerpo()
    db = get_db()
    u = db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    if not u:
        return err("Usuario no encontrado", 404)
    rol = d.get("rol", u["rol"])
    activo = (1 if d["activo"] else 0) if "activo" in d else u["activo"]
    if rol not in ROLES:
        return err("Rol invalido")
    if uid == g.usuario["id"] and (not activo or rol != "dueno"):
        return err("No puedes desactivarte ni quitarte el rol de dueno a ti mismo", 409)
    sv = u["sesion_version"]
    hash_ = u["hash"]
    if d.get("password"):
        if not MIN_PASSWORD <= len(str(d["password"])) <= MAX_PASSWORD:
            return err(f"La contrasena debe tener entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres")
        hash_, sv = generate_password_hash(str(d["password"])), sv + 1
    nombre = str(d.get("nombre", u["nombre"])).strip()
    if not nombre:
        return err("Nombre invalido")
    db.execute("UPDATE usuarios SET nombre=?,rol=?,activo=?,hash=?,sesion_version=? WHERE id=?",
               (nombre, rol, activo, hash_, sv, uid))
    db.commit()
    return jsonify(ok=True)


@bp.get("/api/red")
def acceso_en_red():
    """Direcciones para entrar desde una tablet o celular (solo si se inicio con --lan)."""
    return jsonify(urls=current_app.config.get("LAN_URLS", []))
