import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from datetime import timedelta

from . import db, licencia, paths
from .caja import bp as caja_bp
from .auth import bp as auth_bp, clave_secreta, exigir_login
from .licencia_routes import bp as licencia_bp, exigir_licencia
from .routes import bp

# Fecha de publicacion de esta version. Una licencia con `actualizaciones_hasta`
# solo cubre versiones publicadas en o antes de esa fecha.
VERSION = "1.0.0"
FECHA_VERSION = "2026-11-11"

LLAVE_PUBLICA_PATH = paths.recurso("pos", "clave_publica.pem")


def _leer_llave_publica(pem):
    if pem is None and os.path.exists(LLAVE_PUBLICA_PATH):
        with open(LLAVE_PUBLICA_PATH, "rb") as f:
            pem = f.read()
    return licencia.cargar_llave_publica(pem)


def create_app(db_path=None, public_key_pem=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.environ.get(
        "POS_DB", os.path.join(paths.datos_dir(), "pos.db"))
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    app.config["FECHA_VERSION"] = FECHA_VERSION
    app.config["LICENSE_PUBLIC_KEY"] = _leer_llave_publica(public_key_pem)
    # La version instalada siempre exige licencia; en desarrollo es opcional.
    exigir = os.environ.get("POS_REQUIRE_LICENSE") == "1" or paths.empaquetada()
    if exigir and app.config["LICENSE_PUBLIC_KEY"] is None:
        raise RuntimeError("POS_REQUIRE_LICENSE=1 pero falta pos/clave_publica.pem (la version instalada debe incluirla)")
    db.init_app(app)
    app.permanent_session_lifetime = timedelta(hours=12)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.before_request(exigir_licencia)  # 1o licencia, 2o sesion y permisos
    app.before_request(exigir_login)
    @app.get("/api/ping")
    def ping():
        return jsonify(app="punto-de-venta", version=VERSION)

    app.register_blueprint(licencia_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(caja_bp)
    app.register_blueprint(bp)
    @app.errorhandler(HTTPException)
    def _error_http(e):
        if request.path.startswith("/api/"):
            return jsonify(error=e.description or e.name), e.code
        return e

    @app.errorhandler(Exception)
    def _error_inesperado(e):
        app.logger.exception("Error inesperado")
        if request.path.startswith("/api/"):
            return jsonify(error="Error interno del servidor"), 500
        return "Error interno del servidor", 500

    with app.app_context():
        db.init_db()
        app.secret_key = clave_secreta()
    return app
