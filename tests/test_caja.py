"""Turno de caja: apertura, movimientos, cierre con conteo ciego y diferencias."""
import pytest

from pos import create_app


def entrar(app, usuario, password, rol="cajero"):
    c = app.test_client()
    if usuario == "dueno":
        c.post("/api/auth/configurar", json={"nombre": "Dueña", "usuario": "dueno", "password": password})
    r = c.post("/api/auth/login", json={"usuario": usuario, "password": password})
    assert r.status_code == 200, r.get_json()
    return c


@pytest.fixture
def app(tmp_path):
    a = create_app(str(tmp_path / "caja.db"))
    d = a.test_client()
    d.post("/api/auth/configurar", json={"nombre": "Dueña", "usuario": "dueno", "password": "secreto1"})
    for u in ("luis", "ana"):
        d.post("/api/usuarios", json={"nombre": u.title(), "usuario": u, "password": "caja123", "rol": "cajero"})
    return a


@pytest.fixture
def dueno(app):
    return entrar(app, "dueno", "secreto1")


@pytest.fixture
def luis(app):
    return entrar(app, "luis", "caja123")


def prod(c, nombre="Coca-Cola 600 ml"):
    return next(p for p in c.get("/api/productos").get_json() if p["nombre"] == nombre)


def vender(c, p, cant, **extra):
    return c.post("/api/ventas", json={"items": [{"producto_id": p["id"], "cantidad": cant}], **extra})


def test_no_se_puede_cobrar_sin_turno_abierto(luis):
    p = prod(luis)
    r = vender(luis, p, 1)
    assert r.status_code == 409 and r.get_json()["estado"] == "sin_turno"
    assert luis.get("/api/turno").get_json() == {"abierto": False, "turno": None}


def test_abonos_y_devolucion_de_envases_tambien_exigen_turno(dueno, luis):
    dueno.post("/api/turno/abrir", json={"fondo": 0})
    cid = dueno.post("/api/clientes", json={"nombre": "Ana"}).get_json()["id"]
    p = prod(dueno)
    vender(dueno, p, 1, metodo="fiado", cliente_id=cid)
    assert luis.post(f"/api/clientes/{cid}/abono", json={"monto": 1}).status_code == 409
    r = prod(dueno, "Coca-Cola Retornable 600 ml")
    assert luis.post(f"/api/productos/{r['id']}/devolucion", json={"cantidad": 1}).status_code == 409


def test_abrir_turno_valida_fondo_y_no_permite_dos(luis):
    for fondo in (-1, "abc", None, float("inf"), 10**15, [], True):
        assert luis.post("/api/turno/abrir", json={"fondo": fondo}).status_code == 400, fondo
    assert luis.post("/api/turno/abrir", json={"fondo": 200}).status_code == 201
    assert luis.post("/api/turno/abrir", json={"fondo": 200}).status_code == 409
    t = luis.get("/api/turno").get_json()
    assert t["abierto"] and t["turno"]["fondo"] == 20000


def test_cierre_cuadra_con_ventas_abonos_retiros_y_cascos(dueno, luis):
    """esperado = fondo + efectivo + abonos + ingresos - retiros - casco reembolsado (el fiado no cuenta)."""
    luis.post("/api/turno/abrir", json={"fondo": 500})                 # 500.00
    p = prod(luis)
    vender(luis, p, 2)                                                  # efectivo: 2 x 18 = 36.00
    cid = luis.post("/api/clientes", json={"nombre": "Doña Mary"}).get_json()["id"]
    vender(luis, p, 1, metodo="fiado", cliente_id=cid)                  # fiado 18.00: NO entra a caja
    assert luis.post(f"/api/clientes/{cid}/abono", json={"monto": 10}).status_code == 200   # +10.00
    ret = prod(luis, "Coca-Cola Retornable 600 ml")
    vender(luis, ret, 2)                                                # 2 x 13 + 2 cascos de 8 = 42.00
    assert luis.post(f"/api/productos/{ret['id']}/devolucion", json={"cantidad": 1}).status_code == 200  # -8.00
    assert luis.post("/api/turno/movimiento", json={"tipo": "ingreso", "monto": 50, "motivo": "cambio"}).status_code == 201  # +50
    assert luis.post("/api/turno/movimiento", json={"tipo": "retiro", "monto": 100, "motivo": "pago a proveedor"}).status_code == 201  # -100
    esperado = 500 + 36 + 10 + 42 - 8 + 50 - 100                        # = 530.00
    r = luis.post("/api/turno/cerrar", json={"contado": esperado - 5, "notas": "faltaron 5"})
    d = r.get_json()
    assert r.status_code == 200
    assert d["esperado"] == esperado * 100 and d["contado"] == (esperado - 5) * 100 and d["diferencia"] == -500
    assert d["resumen"]["ventas_fiado"] == 1800 and d["resumen"]["abonos"] == 1000
    # ya cerrado: no se puede volver a cobrar ni cerrar
    assert vender(luis, p, 1).status_code == 409
    assert luis.post("/api/turno/cerrar", json={"contado": 0}).status_code == 409


def test_conteo_ciego_el_cajero_no_ve_el_esperado_pero_el_dueno_si(dueno, luis):
    luis.post("/api/turno/abrir", json={"fondo": 100})
    vender(luis, prod(luis), 1)
    vista = luis.get("/api/turno").get_json()["turno"]["resumen"]
    assert set(vista) == {"fondo", "num_ventas"}                        # sin esperado ni totales
    assert "esperado" not in str(luis.get("/api/turno").get_json())
    dueno.post("/api/turno/abrir", json={"fondo": 0})
    lista = dueno.get("/api/turnos").get_json()
    luis_turno = next(t for t in lista if t["cajero"] == "Luis")
    assert luis_turno["resumen"]["esperado"] == 10000 + 1800


def test_sobrante_y_cierre_exacto(luis):
    luis.post("/api/turno/abrir", json={"fondo": 100})
    d = luis.post("/api/turno/cerrar", json={"contado": 105.5}).get_json()
    assert d["esperado"] == 10000 and d["diferencia"] == 550
    luis.post("/api/turno/abrir", json={"fondo": 0})
    assert luis.post("/api/turno/cerrar", json={"contado": 0}).get_json()["diferencia"] == 0


def test_cierre_invalido_no_cierra_el_turno(luis):
    luis.post("/api/turno/abrir", json={"fondo": 0})
    for contado in (-1, "abc", None, float("inf"), True, []):
        assert luis.post("/api/turno/cerrar", json={"contado": contado}).status_code == 400, contado
    assert luis.get("/api/turno").get_json()["abierto"] is True


def test_retiros_validos_e_invalidos(luis):
    luis.post("/api/turno/abrir", json={"fondo": 100})
    mov = lambda **kw: luis.post("/api/turno/movimiento", json=kw).status_code
    assert mov(tipo="retiro", monto=100.01, motivo="x") == 409          # mas de lo que hay
    assert mov(tipo="retiro", monto=100, motivo="") == 400              # sin motivo
    assert mov(tipo="retiro", monto=0, motivo="x") == 400
    assert mov(tipo="retiro", monto=-5, motivo="x") == 400
    assert mov(tipo="robo", monto=5, motivo="x") == 400
    assert mov(tipo="retiro", monto="abc", motivo="x") == 400
    assert mov(tipo="retiro", monto=100, motivo="retiro total") == 201  # exactamente lo que hay
    assert mov(tipo="retiro", monto=0.01, motivo="otro") == 409         # caja vacia


def test_movimiento_sin_turno(luis):
    assert luis.post("/api/turno/movimiento", json={"tipo": "ingreso", "monto": 5, "motivo": "x"}).status_code == 409


def test_cada_cajero_tiene_su_propio_turno(app, luis):
    ana = entrar(app, "ana", "caja123")
    luis.post("/api/turno/abrir", json={"fondo": 100})
    ana.post("/api/turno/abrir", json={"fondo": 300})
    p = prod(luis)
    vender(luis, p, 1)
    vender(ana, p, 2)
    cierre_l = luis.post("/api/turno/cerrar", json={"contado": 118}).get_json()
    cierre_a = ana.post("/api/turno/cerrar", json={"contado": 336}).get_json()
    assert cierre_l["diferencia"] == 0 and cierre_a["diferencia"] == 0
    assert (cierre_l["esperado"], cierre_a["esperado"]) == (11800, 33600)


def test_dueno_cierra_el_turno_olvidado_de_un_cajero_desactivado(app, dueno, luis):
    luis.post("/api/turno/abrir", json={"fondo": 100})
    vender(luis, prod(luis), 1)
    uid = next(u["id"] for u in dueno.get("/api/usuarios").get_json() if u["usuario"] == "luis")
    dueno.put(f"/api/usuarios/{uid}", json={"activo": False})
    assert luis.get("/api/turno").status_code == 401                    # ya no puede entrar
    tid = next(t["id"] for t in dueno.get("/api/turnos").get_json() if t["cerrado"] is None)
    assert dueno.post(f"/api/turnos/{tid}/cerrar", json={"contado": "x"}).status_code == 400
    r = dueno.post(f"/api/turnos/{tid}/cerrar", json={"contado": 118, "notas": "cierre por el dueño"})
    assert r.status_code == 200 and r.get_json()["diferencia"] == 0
    assert dueno.post(f"/api/turnos/{tid}/cerrar", json={"contado": 1}).status_code == 409
    assert dueno.post("/api/turnos/9999/cerrar", json={"contado": 1}).status_code == 404
    # al reactivarlo puede abrir un turno nuevo
    dueno.put(f"/api/usuarios/{uid}", json={"activo": True})
    assert entrar(app, "luis", "caja123").post("/api/turno/abrir", json={"fondo": 0}).status_code == 201


def test_el_cajero_no_puede_ver_ni_cerrar_turnos_ajenos(dueno, luis):
    dueno.post("/api/turno/abrir", json={"fondo": 0})
    tid = dueno.get("/api/turnos").get_json()[0]["id"]
    assert luis.get("/api/turnos").status_code == 403
    assert luis.get(f"/api/turnos/{tid}").status_code == 403
    assert luis.post(f"/api/turnos/{tid}/cerrar", json={"contado": 0}).status_code == 403


def test_corte_del_dia_lista_los_turnos_con_su_diferencia(dueno, luis):
    luis.post("/api/turno/abrir", json={"fondo": 100})
    vender(luis, prod(luis), 1)
    luis.post("/api/turno/cerrar", json={"contado": 100})   # faltan 18.00
    c = dueno.get("/api/corte").get_json()
    assert [(t["cajero"], t["diferencia"]) for t in c["turnos"]] == [("Luis", -1800)]
    assert dueno.get("/api/turnos?fecha=hoy").status_code == 400


def test_dos_aperturas_simultaneas_solo_crean_un_turno(app):
    import threading
    clientes = [entrar(app, "luis", "caja123") for _ in range(6)]
    barrera, codigos = threading.Barrier(6), []

    def abre(c):
        barrera.wait()
        codigos.append(c.post("/api/turno/abrir", json={"fondo": 0}).status_code)

    hilos = [threading.Thread(target=abre, args=(c,)) for c in clientes]
    [h.start() for h in hilos]; [h.join() for h in hilos]
    assert sorted(codigos) == [201] + [409] * 5


def test_ventas_quedan_ligadas_al_turno_y_el_historial_sobrevive(dueno):
    dueno.post("/api/turno/abrir", json={"fondo": 0})
    vender(dueno, prod(dueno), 1)
    dueno.post("/api/turno/cerrar", json={"contado": 18})
    dueno.post("/api/turno/abrir", json={"fondo": 0})   # segundo turno del mismo usuario
    t = dueno.get("/api/turnos").get_json()
    assert len(t) == 2 and sum(x["resumen"]["num_ventas"] for x in t) == 1
