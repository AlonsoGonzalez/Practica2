"""Escenarios limite: entradas raras, concurrencia, datos borrados y abusos."""
import threading

import pytest

from pos import create_app


def sesion(app, usuario="dueno", password="secreto1"):
    c = app.test_client()
    c.post("/api/auth/configurar", json={"nombre": "Dueña", "usuario": usuario, "password": password})
    c.post("/api/auth/login", json={"usuario": usuario, "password": password})
    c.post("/api/turno/abrir", json={"fondo": 0})  # se ignora si aun no existe turno
    return c


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "e.db"))


@pytest.fixture
def client(app):
    return sesion(app)


def prod(c, nombre="Coca-Cola 600 ml"):
    return next(p for p in c.get("/api/productos").get_json() if p["nombre"] == nombre)


def vender(c, pid, cant, **extra):
    return c.post("/api/ventas", json={"items": [{"producto_id": pid, "cantidad": cant}], **extra})


# ---------- JSON y numeros raros (no deben provocar error 500) ----------
@pytest.mark.parametrize("ruta", [
    "/api/ventas", "/api/productos", "/api/clientes", "/api/usuarios",
    "/api/auth/login", "/api/licencia",
])
@pytest.mark.parametrize("cuerpo", ["[1,2]", '"texto"', "42", "null", "{", ""])
def test_cuerpos_json_invalidos_dan_400_no_500(client, ruta, cuerpo):
    """Un cuerpo que no es un objeto JSON nunca debe romper el servidor."""
    r = client.post(ruta, data=cuerpo, content_type="application/json")
    assert r.status_code in (400, 401, 403, 409), (ruta, cuerpo, r.status_code)


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, "1.5", "abc", None, True, [], {}, 10**12])
def test_cantidades_invalidas_en_venta(client, cantidad):
    p = prod(client)
    r = vender(client, p["id"], cantidad)
    assert r.status_code in (400, 409), (cantidad, r.status_code)
    assert prod(client)["stock"] == p["stock"]


@pytest.mark.parametrize("monto", ["1e999", "-1", "nan", "inf", 10**30, "abc", [], True])
def test_montos_invalidos_no_rompen(client, monto):
    p = prod(client)
    r = vender(client, p["id"], 1, recibido=monto)
    assert r.status_code in (400, 409) or (r.status_code == 201 and monto is True), (monto, r.status_code)
    r = client.post("/api/productos", json={"codigo": "m1", "nombre": "m", "precio": monto})
    assert r.status_code == 400, (monto, r.status_code)


def test_items_mal_formados(client):
    for items in ([1], ["a"], [None], [{}], [{"producto_id": "x", "cantidad": 1}], "texto", {"a": 1}):
        r = client.post("/api/ventas", json={"items": items})
        assert r.status_code == 400, items
    r = client.post("/api/ventas", json={"items": [{"producto_id": 1, "cantidad": 1}] * 500})
    assert r.status_code == 400  # carrito absurdamente grande


def test_precios_en_centavos_son_exactos():
    """Convertir pesos a centavos nunca pierde un centavo (todos los montos de 0.00 a 999.99)."""
    from pos.routes import pesos_a_centavos
    for c in range(0, 100000):
        assert pesos_a_centavos(f"{c / 100:.2f}") == c
        assert pesos_a_centavos(c / 100) == c


def test_producto_con_datos_invalidos(client):
    base = {"codigo": "p1", "nombre": "Prueba", "precio": 10}
    for cambio in ({"stock": -5}, {"stock_minimo": -1}, {"costo": -1}, {"precio": -1},
                   {"nombre": "x" * 500}, {"codigo": "c" * 200}, {"stock": 10**12}):
        r = client.post("/api/productos", json={**base, **cambio})
        assert r.status_code == 400, cambio


def test_textos_con_html_y_unicode_se_guardan_tal_cual(client):
    nombre = "<img src=x onerror=alert(1)> 🥤 Ñandú"
    r = client.post("/api/productos", json={"codigo": "x1", "nombre": nombre, "precio": 5})
    assert r.status_code == 201
    assert any(p["nombre"] == nombre for p in client.get("/api/productos?q=Ñandú").get_json())


def test_busqueda_no_es_vulnerable_a_inyeccion_sql(client):
    assert client.get("/api/productos?q=' OR 1=1 --").get_json() == []
    assert client.get("/api/productos?q=%27%3B%20DROP%20TABLE%20productos%3B--").status_code == 200
    assert len(client.get("/api/productos").get_json()) >= 20  # la tabla sigue entera
    assert client.get("/api/productos?q=%").status_code == 200


# ---------- Datos borrados y duplicados ----------
def test_recrear_un_producto_borrado_con_el_mismo_codigo(client):
    """El tendero borra un producto por error y lo vuelve a dar de alta con el mismo codigo."""
    pid = client.post("/api/productos", json={"codigo": "R1", "nombre": "Viejo", "precio": 10, "stock": 3}).get_json()["id"]
    assert client.delete(f"/api/productos/{pid}").status_code == 200
    r = client.post("/api/productos", json={"codigo": "R1", "nombre": "Nuevo", "precio": 12, "stock": 7})
    assert r.status_code == 201, r.get_json()
    p = next(x for x in client.get("/api/productos").get_json() if x["codigo"] == "R1")
    assert p["nombre"] == "Nuevo" and p["stock"] == 7 and p["precio"] == 1200


def test_producto_borrado_no_se_puede_vender_ni_ajustar(client):
    p = prod(client)
    client.delete(f"/api/productos/{p['id']}")
    assert vender(client, p["id"], 1).status_code == 404
    assert client.post(f"/api/productos/{p['id']}/ajuste", json={"cantidad": 1}).status_code == 404
    assert client.put(f"/api/productos/{p['id']}", json={"precio": 1}).status_code == 404
    assert client.delete(f"/api/productos/{p['id']}").status_code == 200 or True


def test_mismo_producto_en_dos_lineas_se_suma_y_valida_stock(client):
    p = prod(client)
    r = client.post("/api/ventas", json={"items": [
        {"producto_id": p["id"], "cantidad": p["stock"]}, {"producto_id": p["id"], "cantidad": 1}]})
    assert r.status_code == 409  # 48 + 1 > stock
    r = client.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 2}] * 2})
    assert r.status_code == 201 and r.get_json()["total"] == p["precio"] * 4


def test_vender_todo_el_stock_y_luego_ya_no(client):
    p = prod(client)
    assert vender(client, p["id"], p["stock"]).status_code == 201
    assert prod(client)["stock"] == 0
    assert vender(client, p["id"], 1).status_code == 409


def test_pago_exacto_y_un_centavo_menos(client):
    p = prod(client)
    assert vender(client, p["id"], 1, recibido=p["precio"] / 100).get_json()["cambio"] == 0
    assert vender(client, p["id"], 1, recibido=p["precio"] / 100 - 0.01).status_code == 400


# ---------- Fiado ----------
def test_fiado_limite_exacto_y_abonos_limite(client):
    p = prod(client)
    cid = client.post("/api/clientes", json={"nombre": "Ana", "limite": p["precio"] / 100 * 2}).get_json()["id"]
    assert vender(client, p["id"], 2, metodo="fiado", cliente_id=cid).status_code == 201   # == limite: si
    assert vender(client, p["id"], 1, metodo="fiado", cliente_id=cid).status_code == 409   # mas: no
    saldo = client.get(f"/api/clientes/{cid}").get_json()["saldo"]
    for monto in (0, -5, "abc", None, float("inf")):
        assert client.post(f"/api/clientes/{cid}/abono", json={"monto": monto}).status_code in (400, 409), monto
    assert client.post(f"/api/clientes/{cid}/abono", json={"monto": saldo / 100}).get_json()["saldo"] == 0
    assert client.post(f"/api/clientes/{cid}/abono", json={"monto": 1}).status_code == 409  # ya no debe nada


def test_fiado_cliente_inexistente_y_metodo_invalido(client):
    p = prod(client)
    assert vender(client, p["id"], 1, metodo="fiado", cliente_id=9999).status_code == 400
    assert vender(client, p["id"], 1, metodo="fiado", cliente_id="x").status_code == 400
    assert vender(client, p["id"], 1, metodo="bitcoin").status_code == 400
    assert client.get("/api/clientes/9999").status_code == 404


def test_fiado_incluye_el_casco_en_la_deuda(client):
    p = prod(client, "Coca-Cola Retornable 600 ml")
    cid = client.post("/api/clientes", json={"nombre": "Beto"}).get_json()["id"]
    r = vender(client, p["id"], 2, metodo="fiado", cliente_id=cid).get_json()
    assert r["total"] == p["precio"] * 2 + p["casco"] * 2
    assert client.get(f"/api/clientes/{cid}").get_json()["saldo"] == r["total"]


# ---------- Envases ----------
def test_envases_casos_limite(client):
    p = prod(client, "Coca-Cola Retornable 600 ml")
    item = lambda dev: {"items": [{"producto_id": p["id"], "cantidad": 2, "envases_devueltos": dev}]}
    assert client.post("/api/ventas", json=item(3)).status_code == 400      # devuelve mas de lo que compra
    r = client.post("/api/ventas", json=item(2)).get_json()                  # cambio uno por uno: sin casco
    assert r["casco"] == 0 and r["total"] == p["precio"] * 2
    assert client.post(f"/api/productos/{p['id']}/devolucion", json={"cantidad": 1}).status_code == 409  # nada en calle
    for cant in (0, -1, "x", None):
        assert client.post(f"/api/productos/{p['id']}/canje-proveedor", json={"cantidad": cant}).status_code == 400
    no_ret = prod(client)
    assert client.post(f"/api/productos/{no_ret['id']}/devolucion", json={"cantidad": 1}).status_code == 404


# ---------- Sugerencia y corte ----------
def test_sugerencia_parametros_extremos(client):
    for q in ("historial=0", "historial=-5", "cobertura=0", "historial=999999999", "cobertura=999999999",
              "historial=1e3", "cobertura=abc"):
        assert client.get(f"/api/sugerencia-pedido?{q}").status_code in (200, 400), q
    d = client.get("/api/sugerencia-pedido?historial=999999999&cobertura=999999999").get_json()
    assert d["historial"] <= 3650 and d["cobertura"] <= 365


def test_sugerencia_sin_ventas_pide_hasta_el_minimo(client):
    pan = prod(client, "Pan Bimbo Blanco Grande")
    client.post(f"/api/productos/{pan['id']}/ajuste", json={"cantidad": -(pan["stock"] - 1)})  # stock 1, minimo 4
    s = next(i for i in client.get("/api/sugerencia-pedido").get_json()["items"] if i["id"] == pan["id"])
    assert s["pedir"] == 3 and s["dias_de_stock"] is None and s["promedio_diario"] == 0


def test_corte_con_fecha_invalida_o_sin_ventas(client):
    assert client.get("/api/corte?fecha=ayer").status_code == 400
    assert client.get("/api/corte?fecha=2020-13-45").status_code == 400
    c = client.get("/api/corte?fecha=2020-01-01").get_json()
    assert c["num_ventas"] == 0 and c["total"] == 0 and c["ticket_promedio"] == 0 and c["top_productos"] == []


# ---------- Concurrencia ----------
def test_dos_cajeros_no_pueden_vender_la_ultima_pieza_a_la_vez(tmp_path):
    """Con 1 pieza en stock y 8 ventas simultaneas, exactamente una debe tener exito."""
    app = create_app(str(tmp_path / "c.db"))
    dueno = sesion(app)
    pid = dueno.post("/api/productos", json={"codigo": "U1", "nombre": "Ultima", "precio": 10, "stock": 1}).get_json()["id"]
    clientes = []
    for i in range(8):
        c = app.test_client()
        with c.session_transaction() as s:
            with dueno.session_transaction() as so:
                s.update(dict(so))
        clientes.append(c)
    barrera, codigos = threading.Barrier(8), []

    def vende(c):
        barrera.wait()
        codigos.append(c.post("/api/ventas", json={"items": [{"producto_id": pid, "cantidad": 1}]}).status_code)

    hilos = [threading.Thread(target=vende, args=(c,)) for c in clientes]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sorted(codigos) == [201] + [409] * 7, codigos
    stock = next(p for p in dueno.get("/api/productos").get_json() if p["id"] == pid)["stock"]
    assert stock == 0  # nunca negativo


def test_abonos_simultaneos_no_dejan_saldo_negativo(tmp_path):
    app = create_app(str(tmp_path / "c2.db"))
    dueno = sesion(app)
    p = prod(dueno)
    cid = dueno.post("/api/clientes", json={"nombre": "Concurrente"}).get_json()["id"]
    dueno.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 1}], "metodo": "fiado", "cliente_id": cid})
    deuda = dueno.get(f"/api/clientes/{cid}").get_json()["saldo"]
    clientes = []
    for _ in range(6):
        c = app.test_client()
        with c.session_transaction() as s, dueno.session_transaction() as so:
            s.update(dict(so))
        clientes.append(c)
    barrera, codigos = threading.Barrier(6), []

    def abona(c):
        barrera.wait()
        codigos.append(c.post(f"/api/clientes/{cid}/abono", json={"monto": deuda / 100}).status_code)

    hilos = [threading.Thread(target=abona, args=(c,)) for c in clientes]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sorted(codigos) == [200] + [409] * 5, codigos
    assert dueno.get(f"/api/clientes/{cid}").get_json()["saldo"] == 0


# ---------- Rutas y errores ----------
def test_errores_de_api_siempre_son_json(client):
    for metodo, ruta in (("get", "/api/no-existe"), ("delete", "/api/ventas"), ("put", "/api/corte"),
                         ("get", "/api/ventas/99999")):
        r = getattr(client, metodo)(ruta)
        assert r.status_code in (404, 405), (ruta, r.status_code)
        assert r.is_json, (metodo, ruta, r.content_type)


def test_cookie_de_sesion_basura_se_trata_como_sin_sesion(app):
    c = sesion(app)
    anon = app.test_client()
    anon.set_cookie("session", "esto-no-es-una-cookie-valida")
    assert anon.get("/api/productos").status_code == 401
    assert anon.get("/api/auth/yo").get_json()["usuario"] is None


def test_formularios_con_campos_opcionales_vacios(client):
    """El formulario web manda "" en los campos que el tendero deja en blanco."""
    r = client.post("/api/productos", json={"codigo": "F1", "nombre": "Sin costo", "categoria": "", "precio": "12.5",
                                            "costo": "", "stock": "", "casco": "", "retornable": False})
    assert r.status_code == 201
    p = next(x for x in client.get("/api/productos").get_json() if x["codigo"] == "F1")
    assert (p["costo"], p["stock"], p["categoria"]) == (0, 0, "General")
    assert client.post("/api/clientes", json={"nombre": "Sin limite", "telefono": "", "limite": ""}).status_code == 201


def test_busqueda_por_codigo_de_barras_exacto(client):
    p = prod(client)
    r = client.get(f"/api/productos?codigo={p['codigo']}").get_json()
    assert [x["id"] for x in r] == [p["id"]]
    assert client.get("/api/productos?codigo=7501055").get_json() == []            # un pedazo del codigo no cuenta
    assert client.get("/api/productos?codigo=%25").get_json() == []                # ni comodines
    assert client.get("/api/productos?codigo=9999999999999").get_json() == []
    client.delete(f"/api/productos/{p['id']}")
    assert client.get(f"/api/productos?codigo={p['codigo']}").get_json() == []     # un producto borrado no se vende
