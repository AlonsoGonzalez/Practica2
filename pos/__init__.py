import os

from flask import Flask

from . import db, licencia
from .licencia_routes import bp as licencia_bp, exigir_licencia
from .routes import bp

# Fecha de publicacion de esta version. Una licencia con `actualizaciones_hasta`
# solo cubre versiones publicadas en o antes de esa fecha.
VERSION = "1.0.0"
FECHA_VERSION = "2026-11-11"

RAIZ = os.path.dirname(os.path.dirname(__file__))
LLAVE_PUBLICA_PATH = os.path.join(os.path.dirname(__file__), "clave_publica.pem")


def _leer_llave_publica(pem):
    if pem is None and os.path.exists(LLAVE_PUBLICA_PATH):
        with open(LLAVE_PUBLICA_PATH, "rb") as f:
            pem = f.read()
    return licencia.cargar_llave_publica(pem)


def create_app(db_path=None, public_key_pem=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.environ.get("POS_DB", os.path.join(RAIZ, "pos.db"))
    app.config["FECHA_VERSION"] = FECHA_VERSION
    app.config["LICENSE_PUBLIC_KEY"] = _leer_llave_publica(public_key_pem)
    if os.environ.get("POS_REQUIRE_LICENSE") == "1" and app.config["LICENSE_PUBLIC_KEY"] is None:
        raise RuntimeError("POS_REQUIRE_LICENSE=1 pero falta pos/clave_publica.pem")
    db.init_app(app)
    app.before_request(exigir_licencia)
    app.register_blueprint(licencia_bp)
    app.register_blueprint(bp)
    with app.app_context():
        db.init_db()
    return app
