import os
from flask import Flask

from . import db
from .routes import bp


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or os.environ.get(
        "POS_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "pos.db")
    )
    db.init_app(app)
    app.register_blueprint(bp)
    with app.app_context():
        db.init_db()
    return app
