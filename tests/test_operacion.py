"""Respaldos, arranque, rutas de datos y migracion de bases viejas."""
import os
import socket
import sqlite3
import sys
from datetime import date

import pytest

from pos import create_app, paths
from pos.respaldos import respaldar


def test_respaldo_con_nombre_con_hora_y_motivo(tmp_path):
    from datetime import datetime
    db = tmp_path / "pos.db"
    create_app(str(db))
    ahora = datetime(2026, 11, 11, 15, 30, 5)
    a = respaldar(str(db), str(tmp_path / "r"), "cierre-turno", ahora=ahora)
    assert os.path.basename(a) == "pos-2026-11-11_15-30-05-cierre-turno.db"
    assert respaldar(str(db), str(tmp_path / "r"), "cierre-turno", ahora=ahora) == a   # mismo segundo: no duplica
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path / "r"))
    with pytest.raises(ValueError):
        respaldar(str(db), str(tmp_path / "r"), "../../malo")


def test_rotacion_conserva_24h_completas_y_el_ultimo_de_cada_dia(tmp_path):
    from datetime import datetime, timedelta
    from pos.respaldos import listar
    db = tmp_path / "pos.db"
    create_app(str(db))
    dest = str(tmp_path / "r")
    ahora = datetime(2026, 11, 20, 12, 0, 0)
    # 3 respaldos el dia 10 (viejo), 2 el dia 19 (fuera de las 24 h), 3 en las ultimas horas, 1 de hace 40 dias
    for f in [ahora - timedelta(days=10, hours=h) for h in (0, 1, 2)] + \
             [ahora - timedelta(days=1, hours=h) for h in (3, 4)] + \
             [ahora - timedelta(hours=h) for h in (1, 5, 9)] + [ahora - timedelta(days=40)]:
        respaldar(str(db), dest, "auto", ahora=f)
    from pos.respaldos import rotar
    rotar(dest, ahora)   # la limpieza se hace "hoy"; cada respaldo se creo con su propia fecha simulada
    nombres = [r["fecha"] for r in listar(dest)]
    assert len(nombres) == 5, nombres          # 3 recientes + 1 del dia 19 + 1 del dia 10; el de hace 40 dias se fue
    assert "2026-11-10 12:00:00" in nombres and "2026-11-10 11:00:00" not in nombres   # solo el ultimo de ese dia
    assert not any(n.startswith("2026-10") for n in nombres)


def test_rotacion_no_borra_archivos_ajenos(tmp_path):
    from datetime import datetime, timedelta
    db = tmp_path / "pos.db"
    create_app(str(db))
    dest = tmp_path / "r"; dest.mkdir()
    for nombre in ("mis-fotos.zip", "pos-notas.txt", "pos-2020-01-01_00-00-00-auto.txt"):
        (dest / nombre).write_text("no tocar")
    respaldar(str(db), str(dest), "auto", ahora=datetime(2026, 1, 1, 10, 0, 0))
    respaldar(str(db), str(dest), "auto", ahora=datetime(2026, 6, 1, 10, 0, 0))     # el de enero ya es muy viejo
    assert sorted(os.listdir(dest)) == ["mis-fotos.zip", "pos-2020-01-01_00-00-00-auto.txt",
                                        "pos-2026-06-01_10-00-00-auto.db", "pos-notas.txt"]


def test_respaldos_de_versiones_anteriores_siguen_apareciendo(tmp_path):
    from pos.respaldos import listar
    dest = tmp_path / "r"; dest.mkdir()
    create_app(str(tmp_path / "pos.db"))
    import shutil
    shutil.copy(tmp_path / "pos.db", dest / "pos-2026-11-11.db")   # formato de la primera version
    assert [(r["archivo"], r["motivo"]) for r in listar(str(dest))] == [("pos-2026-11-11.db", "antiguo")]


def test_respaldo_seguro_no_tumba_el_arranque(tmp_path):
    from pos.respaldos import respaldar_seguro
    db = tmp_path / "pos.db"
    create_app(str(db))
    archivo = tmp_path / "soy-un-archivo"; archivo.write_text("x")
    assert respaldar_seguro(str(db), str(archivo / "no-puede-ser-carpeta")) is None   # destino imposible
    corrupta = tmp_path / "mala.db"; corrupta.write_bytes(b"esto no es sqlite" * 100)
    assert respaldar_seguro(str(corrupta), str(tmp_path / "r2")) is None              # base corrupta
    assert respaldar_seguro(str(db), str(tmp_path / "r3")) is not None                # caso normal


def sesion_dueno(tmp_path):
    app = create_app(str(tmp_path / "pos.db"))
    c = app.test_client()
    c.post("/api/auth/configurar", json={"nombre": "D", "usuario": "d", "password": "secreto1"})
    c.post("/api/turno/abrir", json={"fondo": 0})
    return app, c


def vender_uno(c, cant=1):
    p = c.get("/api/productos").get_json()[0]
    return c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": cant}]})


def test_cerrar_turno_genera_un_respaldo_con_las_ventas_del_turno(tmp_path):
    """El caso que fallo en la prueba real: el respaldo del dia no contenia ninguna venta."""
    from pos.respaldos import listar
    app, c = sesion_dueno(tmp_path)
    vender_uno(c, 2)
    assert listar(app.config["RESPALDOS_DIR"]) == []
    assert c.post("/api/turno/cerrar", json={"contado": 36}).status_code == 200
    r = listar(app.config["RESPALDOS_DIR"])
    assert [x["motivo"] for x in r] == ["cierre-turno"]
    ventas = sqlite3.connect(os.path.join(app.config["RESPALDOS_DIR"], r[0]["archivo"])).execute(
        "SELECT COUNT(*) FROM ventas").fetchone()[0]
    assert ventas == 1


def test_respaldar_ahora_y_listar_desde_la_app(tmp_path):
    app, c = sesion_dueno(tmp_path)
    assert c.get("/api/respaldos").get_json() == []
    r = c.post("/api/respaldos")
    assert r.status_code == 201 and "manual" in r.get_json()["archivo"]
    lista = c.get("/api/respaldos").get_json()
    assert len(lista) == 1 and lista[0]["motivo"] == "manual" and lista[0]["bytes"] > 0


def test_restaurar_un_respaldo_devuelve_los_datos_y_guarda_lo_actual(tmp_path):
    """Escenario de desastre: se hizo un respaldo, despues se registraron ventas por error o se perdio info."""
    from pos.respaldos import listar
    app, c = sesion_dueno(tmp_path)
    vender_uno(c, 1)
    archivo = c.post("/api/respaldos").get_json()["archivo"]          # respaldo con 1 venta
    vender_uno(c, 1); vender_uno(c, 1)                                 # ahora hay 3
    assert c.get("/api/corte").get_json()["num_ventas"] == 3
    r = c.post("/api/respaldos/restaurar", json={"archivo": archivo})
    assert r.status_code == 200
    c2 = app.test_client()
    assert c2.post("/api/auth/login", json={"usuario": "d", "password": "secreto1"}).status_code == 200
    assert c2.get("/api/corte").get_json()["num_ventas"] == 1          # volvio a la foto del respaldo
    assert "antes-de-restaurar" in [x["motivo"] for x in listar(app.config["RESPALDOS_DIR"])]   # y no se perdio lo anterior


def test_restaurar_rechaza_nombres_peligrosos_archivos_ajenos_y_danados(tmp_path):
    app, c = sesion_dueno(tmp_path)
    dest = app.config["RESPALDOS_DIR"]
    os.makedirs(dest, exist_ok=True)
    (open(os.path.join(dest, "pos-2026-01-01_00-00-00-auto.db"), "wb")).write(b"esto no es sqlite" * 50)
    otra = sqlite3.connect(os.path.join(dest, "pos-2026-01-02_00-00-00-auto.db")); otra.execute("CREATE TABLE x(a)"); otra.commit(); otra.close()
    for nombre in ("../pos.db", "..\\pos.db", "C:/Windows/x.db", "pos.db", "cualquier-cosa", "", None, 5, ["a"]):
        assert c.post("/api/respaldos/restaurar", json={"archivo": nombre}).status_code == 400, nombre
    assert c.post("/api/respaldos/restaurar", json={"archivo": "pos-2026-01-01_00-00-00-auto.db"}).status_code == 400   # corrupto
    assert c.post("/api/respaldos/restaurar", json={"archivo": "pos-2026-01-02_00-00-00-auto.db"}).status_code == 400   # otra base
    assert c.post("/api/respaldos/restaurar", json={"archivo": "pos-2030-01-01_00-00-00-auto.db"}).status_code == 404   # no existe
    assert c.get("/api/productos").status_code == 200                                          # la base actual sigue intacta


def test_respaldos_solo_para_el_dueno(tmp_path):
    app, c = sesion_dueno(tmp_path)
    c.post("/api/usuarios", json={"nombre": "L", "usuario": "luis", "password": "caja123", "rol": "cajero"})
    cajero = app.test_client()
    cajero.post("/api/auth/login", json={"usuario": "luis", "password": "caja123"})
    assert cajero.get("/api/respaldos").status_code == 403
    assert cajero.post("/api/respaldos").status_code == 403
    assert cajero.post("/api/respaldos/restaurar", json={"archivo": "x"}).status_code == 403


def test_restaurar_un_respaldo_de_una_version_anterior_agrega_lo_nuevo(tmp_path):
    """Un respaldo viejo (sin tablas de turnos/usuarios nuevas columnas) se actualiza al restaurarlo."""
    app, c = sesion_dueno(tmp_path)
    dest = app.config["RESPALDOS_DIR"]; os.makedirs(dest, exist_ok=True)
    viejo = os.path.join(dest, "pos-2026-01-03_00-00-00-auto.db")
    con = sqlite3.connect(viejo)
    con.executescript("""
      CREATE TABLE productos (id INTEGER PRIMARY KEY, codigo TEXT, nombre TEXT, categoria TEXT DEFAULT 'General', precio INTEGER,
        costo INTEGER DEFAULT 0, stock INTEGER DEFAULT 0, stock_minimo INTEGER DEFAULT 5, activo INTEGER DEFAULT 1);
      CREATE TABLE ventas (id INTEGER PRIMARY KEY, fecha TEXT, total INTEGER, recibido INTEGER, cambio INTEGER, metodo TEXT);
      CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT, usuario TEXT, hash TEXT, rol TEXT, activo INTEGER DEFAULT 1, sesion_version INTEGER DEFAULT 1);
      CREATE TABLE turnos (id INTEGER PRIMARY KEY, usuario_id INTEGER, abierto TEXT, cerrado TEXT, fondo INTEGER);
    """)
    con.commit(); con.close()
    assert c.post("/api/respaldos/restaurar", json={"archivo": "pos-2026-01-03_00-00-00-auto.db"}).status_code == 200
    columnas = {r[1] for r in sqlite3.connect(app.config["DATABASE"]).execute("PRAGMA table_info(productos)")}
    assert {"retornable", "casco", "vacios"} <= columnas   # la migracion corrio despues de restaurar


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


def test_restaurar_no_borra_el_respaldo_elegido_aunque_sea_muy_viejo(tmp_path):
    app, c = sesion_dueno(tmp_path)
    dest = app.config["RESPALDOS_DIR"]
    from pos.respaldos import respaldar
    from datetime import datetime
    viejo = respaldar(app.config["DATABASE"], dest, "manual", ahora=datetime(2025, 1, 1, 8, 0, 0), limpiar=False)
    assert c.post("/api/respaldos/restaurar", json={"archivo": os.path.basename(viejo)}).status_code == 200
    assert os.path.exists(viejo)
