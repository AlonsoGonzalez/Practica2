import pytest

from pos import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "a.db"))


def nuevo(app):
    return app.test_client()


def configurar(c, usuario="dueno", password="secreto1"):
    return c.post("/api/auth/configurar", json={"nombre": "Dueña", "usuario": usuario, "password": password})


def login(c, usuario, password):
    return c.post("/api/auth/login", json={"usuario": usuario, "password": password})


@pytest.fixture
def duenio_y_cajero(app):
    d = nuevo(app)
    configurar(d)
    r = d.post("/api/usuarios", json={"nombre": "Luis", "usuario": "luis", "password": "caja123", "rol": "cajero"})
    assert r.status_code == 201
    c = nuevo(app)
    assert login(c, "luis", "caja123").status_code == 200
    assert d.post("/api/turno/abrir", json={"fondo": 0}).status_code == 201
    assert c.post("/api/turno/abrir", json={"fondo": 100}).status_code == 201
    return d, c


def test_primer_uso_configura_al_dueno_una_sola_vez(app):
    c = nuevo(app)
    assert c.get("/api/auth/yo").get_json() == {"configurado": False, "usuario": None}
    assert configurar(c, password="corta").status_code == 400
    assert configurar(c).status_code == 201
    assert c.get("/api/auth/yo").get_json()["usuario"]["rol"] == "dueno"  # queda con sesion iniciada
    assert configurar(nuevo(app), "otro").status_code == 409  # nadie mas puede auto-nombrarse dueno


def test_api_exige_sesion(app):
    c = nuevo(app)
    configurar(c)
    anonimo = nuevo(app)
    for ruta in ("/api/productos", "/api/corte", "/api/clientes", "/api/usuarios", "/api/sugerencia-pedido"):
        r = anonimo.get(ruta)
        assert r.status_code == 401 and r.get_json()["estado"] == "sin_sesion", ruta
    assert anonimo.post("/api/ventas", json={"items": []}).status_code == 401
    assert anonimo.get("/").status_code == 200  # la pantalla de login si carga


def test_login_logout_y_credenciales_incorrectas(app):
    c = nuevo(app)
    configurar(c)
    c2 = nuevo(app)
    assert login(c2, "dueno", "mala").status_code == 401
    assert login(c2, "nadie", "secreto1").status_code == 401
    assert login(c2, "DUENO", "secreto1").status_code == 200  # usuario no distingue mayusculas
    assert c2.get("/api/productos").status_code == 200
    c2.post("/api/auth/logout")
    assert c2.get("/api/productos").status_code == 401


def test_bloqueo_por_intentos_fallidos(app):
    c = nuevo(app)
    configurar(c)
    c2 = nuevo(app)
    for _ in range(5):
        assert login(c2, "dueno", "mala").status_code == 401
    assert login(c2, "dueno", "secreto1").status_code == 429  # ni con la buena mientras dure el bloqueo


def test_cajero_solo_cobra_y_no_ve_costos(duenio_y_cajero):
    d, c = duenio_y_cajero
    prods = c.get("/api/productos").get_json()
    assert prods and all("costo" not in p for p in prods)
    assert "costo" in d.get("/api/productos").get_json()[0]
    p = next(x for x in prods if x["stock"] > 2)
    assert c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 1}]}).status_code == 201
    # clientes/fiado y devolucion de envases si; lo demas no
    assert c.get("/api/clientes").status_code == 200
    assert c.post("/api/clientes", json={"nombre": "Ana"}).status_code == 201
    prohibido = [
        ("get", "/api/corte"), ("get", "/api/usuarios"), ("get", "/api/sugerencia-pedido"),
        ("get", "/api/reportes/stock-bajo"), ("get", "/api/reportes/envases"), ("get", "/api/red"),
    ]
    for _, ruta in prohibido:
        assert c.get(ruta).status_code == 403, ruta
    assert c.post("/api/productos", json={"codigo": "z", "nombre": "z", "precio": 1}).status_code == 403
    assert c.put(f"/api/productos/{p['id']}", json={"precio": 1}).status_code == 403
    assert c.delete(f"/api/productos/{p['id']}").status_code == 403
    assert c.post(f"/api/productos/{p['id']}/ajuste", json={"cantidad": 5}).status_code == 403
    assert c.post("/api/usuarios", json={"nombre": "x", "usuario": "x", "password": "123456"}).status_code == 403


def test_ventas_registran_al_cajero_y_corte_las_separa(duenio_y_cajero):
    d, c = duenio_y_cajero
    p = c.get("/api/productos").get_json()[0]
    c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 1}]})
    d.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 1}]})
    por = {u["nombre"]: u["ventas"] for u in d.get("/api/corte").get_json()["por_usuario"]}
    assert por == {"Luis": 1, "Dueña": 1}


def test_administrar_usuarios(app, duenio_y_cajero):
    d, c = duenio_y_cajero
    luis = next(u for u in d.get("/api/usuarios").get_json() if u["usuario"] == "luis")
    yo = d.get("/api/auth/yo").get_json()["usuario"]
    assert d.post("/api/usuarios", json={"nombre": "X", "usuario": "LUIS", "password": "123456"}).status_code == 409
    assert d.post("/api/usuarios", json={"nombre": "X", "usuario": "x", "password": "123456", "rol": "root"}).status_code == 400
    assert d.put(f"/api/usuarios/{yo['id']}", json={"activo": False}).status_code == 409  # no se auto-bloquea
    assert d.put(f"/api/usuarios/{yo['id']}", json={"rol": "cajero"}).status_code == 409
    # desactivar al cajero lo saca de inmediato aunque tenga sesion abierta
    assert c.get("/api/productos").status_code == 200
    assert d.put(f"/api/usuarios/{luis['id']}", json={"activo": False}).status_code == 200
    assert c.get("/api/productos").status_code == 401
    assert login(nuevo(app), "luis", "caja123").status_code == 401
    d.put(f"/api/usuarios/{luis['id']}", json={"activo": True, "password": "nueva456"})
    assert login(nuevo(app), "luis", "caja123").status_code == 401
    assert login(nuevo(app), "luis", "nueva456").status_code == 200


def test_cambiar_password_cierra_otras_sesiones(app):
    a = nuevo(app)
    configurar(a)
    b = nuevo(app)
    login(b, "dueno", "secreto1")
    assert a.post("/api/auth/password", json={"actual": "mala", "nueva": "nuevapass"}).status_code == 403
    assert a.post("/api/auth/password", json={"actual": "secreto1", "nueva": "123"}).status_code == 400
    assert a.post("/api/auth/password", json={"actual": "secreto1", "nueva": "nuevapass"}).status_code == 200
    assert a.get("/api/productos").status_code == 200   # esta sesion sigue
    assert b.get("/api/productos").status_code == 401   # la otra se cerro
    assert login(nuevo(app), "dueno", "nuevapass").status_code == 200


def test_sesion_sobrevive_reinicio_y_cookie_segura(tmp_path):
    ruta = str(tmp_path / "r.db")
    c = create_app(ruta).test_client()
    configurar(c)
    c2 = create_app(ruta).test_client()  # "reinicio": mismo archivo, nueva app
    c2.set_cookie("session", c.get_cookie("session").value)
    assert c2.get("/api/productos").status_code == 200  # la clave de firma persiste en la base
    cabecera = c.post("/api/auth/login", json={"usuario": "dueno", "password": "secreto1"}).headers["Set-Cookie"]
    assert "HttpOnly" in cabecera and "SameSite=Lax" in cabecera


def test_licencia_se_revisa_antes_que_la_sesion(tmp_path):
    from tests.test_licencia import par_de_llaves
    _, pub = par_de_llaves()
    c = create_app(str(tmp_path / "l.db"), public_key_pem=pub).test_client()
    assert configurar(c).status_code == 402  # sin licencia no se puede ni crear la cuenta
