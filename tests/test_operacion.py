"""Respaldos, arranque, rutas de datos y migracion de bases viejas."""
import os
import socket
import sqlite3
import sys
from datetime import date

import pytest

from pos import create_app, paths
from pos.respaldos import respaldar


def test_respaldo_es_idempotente_el_mismo_dia(tmp_path):
    db = tmp_path / "pos.db"
    create_app(str(db))
    a = respaldar(str(db), str(tmp_path / "r"), hoy=date(2026, 1, 1))
    antes = os.path.getmtime(a)
    assert respaldar(str(db), str(tmp_path / "r"), hoy=date(2026, 1, 1)) == a
    assert os.path.getmtime(a) == antes and len(os.listdir(tmp_path / "r")) == 1


def test_rotacion_no_borra_archivos_ajenos(tmp_path):
    db = tmp_path / "pos.db"
    create_app(str(db))
    dest = tmp_path / "r"; dest.mkdir()
    (dest / "mis-fotos.zip").write_text("no tocar")
    (dest / "pos-notas.txt").write_text("no tocar")
    for d in range(1, 6):
        respaldar(str(db), str(dest), conservar=2, hoy=date(2026, 1, d))
    assert sorted(os.listdir(dest)) == ["mis-fotos.zip", "pos-2026-01-04.db", "pos-2026-01-05.db", "pos-notas.txt"]


def test_respaldo_seguro_no_tumba_el_arranque(tmp_path):
    from pos.respaldos import respaldar_seguro
    db = tmp_path / "pos.db"
    create_app(str(db))
    archivo = tmp_path / "soy-un-archivo"; archivo.write_text("x")
    assert respaldar_seguro(str(db), str(archivo / "no-puede-ser-carpeta")) is None   # destino imposible
    corrupta = tmp_path / "mala.db"; corrupta.write_bytes(b"esto no es sqlite" * 100)
    assert respaldar_seguro(str(corrupta), str(tmp_path / "r2")) is None              # base corrupta
    assert respaldar_seguro(str(db), str(tmp_path / "r3")) is not None                # caso normal


def test_respaldo_restaurado_contiene_las_ventas(tmp_path):
    db = tmp_path / "pos.db"
    c = create_app(str(db)).test_client()
    c.post("/api/auth/configurar", json={"nombre": "D", "usuario": "d", "password": "secreto1"})
    c.post("/api/turno/abrir", json={"fondo": 0})
    p = c.get("/api/productos").get_json()[0]
    c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 3}]})
    copia = respaldar(str(db), str(tmp_path / "r"))
    # "desastre": se pierde pos.db y se restaura la copia
    os.remove(db)
    for ext in ("-wal", "-shm"):
        if os.path.exists(str(db) + ext):
            os.remove(str(db) + ext)
    os.replace(copia, db)
    c2 = create_app(str(db)).test_client()
    assert c2.post("/api/auth/login", json={"usuario": "d", "password": "secreto1"}).status_code == 200
    assert c2.get("/api/corte").get_json()["num_ventas"] == 1


def test_puerto_ocupado_usa_el_siguiente():
    from servidor import puerto_libre
    with socket.socket() as ocupado:
        ocupado.bind(("127.0.0.1", 0)); ocupado.listen()
        puerto = ocupado.getsockname()[1]
        assert puerto_libre("127.0.0.1", puerto) == puerto + 1


def test_direcciones_para_la_tablet_incluyen_el_nombre_del_equipo():
    from servidor import urls_lan
    urls = urls_lan(5000)
    assert urls and all(u.startswith("http://") and u.endswith(":5000") for u in urls)
    assert f"http://{socket.gethostname()}:5000" in urls


def test_rutas_de_datos(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_DATA_DIR", str(tmp_path / "nuevo" / "datos"))
    assert paths.datos_dir() == str(tmp_path / "nuevo" / "datos") and os.path.isdir(tmp_path / "nuevo" / "datos")
    monkeypatch.delenv("POS_DATA_DIR")
    assert paths.datos_dir() == paths.RAIZ           # en desarrollo: la carpeta del proyecto
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(sys, "platform", "linux")
    assert paths.datos_dir() == str(tmp_path / "xdg" / paths.NOMBRE_APP)   # instalada: fuera del programa


def test_version_instalada_se_niega_a_arrancar_sin_llave_publica(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("pos.LLAVE_PUBLICA_PATH", str(tmp_path / "no-existe.pem"))
    with pytest.raises(RuntimeError, match="clave_publica"):
        create_app(str(tmp_path / "x.db"))


def test_migracion_de_una_base_de_la_primera_version(tmp_path):
    """Una tienda que ya usaba la version 1 actualiza y conserva sus productos y ventas."""
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
    CREATE TABLE productos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL,
        categoria TEXT NOT NULL DEFAULT 'General', precio INTEGER NOT NULL, costo INTEGER NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0, stock_minimo INTEGER NOT NULL DEFAULT 5, activo INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        total INTEGER NOT NULL, recibido INTEGER NOT NULL, cambio INTEGER NOT NULL, metodo TEXT NOT NULL DEFAULT 'efectivo');
    CREATE TABLE venta_items (id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER NOT NULL, producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL, precio INTEGER NOT NULL, costo INTEGER NOT NULL);
    CREATE TABLE movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        producto_id INTEGER NOT NULL, cantidad INTEGER NOT NULL, motivo TEXT NOT NULL);
    INSERT INTO productos (codigo,nombre,precio,stock) VALUES ('A','Galletas viejas',1500,7);
    INSERT INTO ventas (total,recibido,cambio) VALUES (1500,2000,500);
    """)
    con.commit(); con.close()
    app = create_app(str(ruta))
    c = app.test_client()
    c.post("/api/auth/configurar", json={"nombre": "D", "usuario": "d", "password": "secreto1"})
    c.post("/api/turno/abrir", json={"fondo": 0})
    p = next(x for x in c.get("/api/productos").get_json() if x["codigo"] == "A")
    assert (p["nombre"], p["stock"], p["retornable"]) == ("Galletas viejas", 7, 0)
    assert c.get("/api/corte").get_json()["por_usuario"][0]["nombre"] == "(sin usuario)"   # venta anterior a los usuarios
    assert c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 1}]}).status_code == 201
    create_app(str(ruta))  # abrir otra vez no rompe (migracion idempotente)
