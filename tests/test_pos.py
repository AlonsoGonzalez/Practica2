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
