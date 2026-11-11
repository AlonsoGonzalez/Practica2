import pytest
from pos import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "t.db"))
    return app.test_client()


def prod(client, nombre="Coca-Cola 600 ml"):
    return next(p for p in client.get("/api/productos").get_json() if p["nombre"] == nombre)


def test_catalogo_semilla(client):
    assert len(client.get("/api/productos").get_json()) >= 10
    assert len(client.get("/api/productos?q=coca").get_json()) >= 3


def test_venta_descuenta_stock_y_calcula_cambio(client):
    p = prod(client)
    r = client.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 3}], "recibido": 100})
    assert r.status_code == 201
    d = r.get_json()
    assert d["total"] == p["precio"] * 3 and d["cambio"] == 10000 - d["total"]
    assert prod(client)["stock"] == p["stock"] - 3


def test_venta_rechaza_stock_insuficiente_y_pago_corto(client):
    p = prod(client)
    r = client.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 9999}]})
    assert r.status_code == 409
    r = client.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 2}], "recibido": 1})
    assert r.status_code == 400
    assert prod(client)["stock"] == p["stock"]
    assert client.post("/api/ventas", json={"items": []}).status_code == 400


def test_inventario_crud_y_ajuste(client):
    r = client.post("/api/productos", json={"codigo": "X1", "nombre": "Prueba", "precio": "12.50", "costo": 8, "stock": 5})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    assert client.post("/api/productos", json={"codigo": "X1", "nombre": "Dup", "precio": 1}).status_code == 409
    assert client.post(f"/api/productos/{pid}/ajuste", json={"cantidad": 10}).get_json()["stock"] == 15
    assert client.post(f"/api/productos/{pid}/ajuste", json={"cantidad": -99}).status_code == 400
    assert client.put(f"/api/productos/{pid}", json={"precio": 15}).status_code == 200
    assert client.delete(f"/api/productos/{pid}").status_code == 200
    assert all(p["id"] != pid for p in client.get("/api/productos").get_json())


def test_corte_de_caja(client):
    p = prod(client)
    client.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": 2}]})
    c = client.get("/api/corte").get_json()
    assert c["num_ventas"] == 1 and c["total"] == p["precio"] * 2
    assert c["utilidad"] == (p["precio"] - p["costo"]) * 2
    assert c["top_productos"][0]["unidades"] == 2


def test_stock_bajo(client):
    p = prod(client, "Pan Bimbo Blanco Grande")
    client.post(f"/api/productos/{p['id']}/ajuste", json={"cantidad": -p["stock"]})
    assert any(x["id"] == p["id"] for x in client.get("/api/reportes/stock-bajo").get_json())


def venta(client, pid, cant, **extra):
    return client.post("/api/ventas", json={"items": [{"producto_id": pid, "cantidad": cant,
                       **extra.pop("item", {})}], **extra})


def test_fiado_saldo_limite_y_abonos(client):
    p = prod(client)
    cid = client.post("/api/clientes", json={"nombre": "Doña Mary", "limite": 50}).get_json()["id"]
    assert venta(client, p["id"], 1, metodo="fiado").status_code == 400  # sin cliente
    r = venta(client, p["id"], 2, metodo="fiado", cliente_id=cid)
    assert r.status_code == 201 and r.get_json()["cambio"] == 0
    saldo = p["precio"] * 2
    assert client.get(f"/api/clientes/{cid}").get_json()["saldo"] == saldo
    assert venta(client, p["id"], 20, metodo="fiado", cliente_id=cid).status_code == 409  # excede limite
    assert client.post(f"/api/clientes/{cid}/abono", json={"monto": 9999}).status_code == 409
    assert client.post(f"/api/clientes/{cid}/abono", json={"monto": 10}).get_json()["saldo"] == saldo - 1000
    c = client.get("/api/corte").get_json()
    assert c["fiado"] == saldo and c["abonos"] == 1000
    assert c["efectivo_en_caja"] == 1000  # solo el abono entra a caja


def test_retornables_casco(client):
    p = prod(client, "Coca-Cola Retornable 600 ml")
    assert p["retornable"] and p["casco"] == 800
    # 3 botellas, regresa 1 vacia -> paga 2 cascos
    r = venta(client, p["id"], 3, item={"envases_devueltos": 1}).get_json()
    assert r["casco"] == 1600 and r["total"] == p["precio"] * 3 + 1600
    e = client.get("/api/reportes/envases").get_json()
    e = next(x for x in e if x["id"] == p["id"])
    assert (e["vacios"], e["en_calle"], e["casco_en_calle"]) == (1, 2, 1600)
    # el cliente regresa 2 envases -> reembolso de casco
    assert client.post(f"/api/productos/{p['id']}/devolucion", json={"cantidad": 3}).status_code == 409
    assert client.post(f"/api/productos/{p['id']}/devolucion", json={"cantidad": 2}).get_json()["reembolso"] == 1600
    c = client.get("/api/corte").get_json()
    assert c["cascos_cobrados"] == 1600 and c["cascos_reembolsados"] == 1600
    # canje con proveedor: 3 vacios -> 3 llenos
    stock = prod(client, "Coca-Cola Retornable 600 ml")["stock"]
    assert client.post(f"/api/productos/{p['id']}/canje-proveedor", json={"cantidad": 4}).status_code == 409
    assert client.post(f"/api/productos/{p['id']}/canje-proveedor", json={"cantidad": 3}).status_code == 200
    assert prod(client, "Coca-Cola Retornable 600 ml")["stock"] == stock + 3


def test_envases_devueltos_solo_en_retornables(client):
    p = prod(client)  # no retornable
    assert venta(client, p["id"], 1, item={"envases_devueltos": 1}).status_code == 400
    assert venta(client, p["id"], 1, item={"envases_devueltos": -1}).status_code == 400


def test_sugerencia_pedido(client):
    p = prod(client)
    venta(client, p["id"], 14)  # 14 vendidos en 14 dias -> 1 por dia
    d = client.get("/api/sugerencia-pedido?historial=14&cobertura=7").get_json()
    s = next(i for i in d["items"] if i["id"] == p["id"]) if any(i["id"] == p["id"] for i in d["items"]) else None
    # stock 34, objetivo = 7 + 12 = 19 -> no hace falta pedir
    assert s is None
    venta(client, p["id"], 30)
    d = client.get("/api/sugerencia-pedido?historial=14&cobertura=7").get_json()
    s = next(i for i in d["items"] if i["id"] == p["id"])
    assert s["stock"] == 4 and s["pedir"] == (-(-44 * 7 // 14)) + 12 - 4
    assert d["total_estimado"] >= s["costo_estimado"]
    assert client.get("/api/sugerencia-pedido?historial=x").status_code == 400
