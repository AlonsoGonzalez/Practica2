import json
import subprocess
import sys
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pos import create_app, licencia as lic


def par_de_llaves():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def emitir(priv, **campos):
    payload = {"v": 1, "tienda": "Abarrotes Prueba", "tipo": "vitalicia", **campos}
    cuerpo = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"POS1.{lic.b64e(cuerpo)}.{lic.b64e(priv.sign(cuerpo))}"


@pytest.fixture
def ctx(tmp_path):
    priv, pub = par_de_llaves()
    client = create_app(str(tmp_path / "l.db"), public_key_pem=pub).test_client()
    return priv, client


def entrar(client):
    """Crea el dueno (si falta) e inicia sesion."""
    client.post("/api/auth/configurar", json={"nombre": "D", "usuario": "dueno", "password": "secreto1"})
    client.post("/api/auth/login", json={"usuario": "dueno", "password": "secreto1"})


def instalacion(client):
    return client.get("/api/licencia").get_json()["instalacion"]


def test_sin_licencia_bloquea_api_pero_no_la_pantalla(ctx):
    _, c = ctx
    r = c.get("/api/productos")
    assert r.status_code == 402 and r.get_json()["estado"] == "sin_licencia"
    assert c.get("/").status_code == 200
    assert c.get("/api/licencia").get_json()["activa"] is False


def test_activar_licencia_valida(ctx):
    priv, c = ctx
    clave = emitir(priv, instalacion=instalacion(c))
    r = c.post("/api/licencia", json={"clave": "\n".join([clave[:30], clave[30:]])})  # tolera saltos
    assert r.status_code == 200 and r.get_json()["tienda"] == "Abarrotes Prueba"
    entrar(c)
    assert c.get("/api/productos").status_code == 200
    assert c.get("/api/licencia").get_json()["estado"] == "activa"


def test_clave_manipulada_o_de_otra_llave_se_rechaza(ctx):
    priv, c = ctx
    inst = instalacion(c)
    clave = emitir(priv, instalacion=inst)
    pref, cuerpo, firma = clave.split(".")
    falso = json.loads(lic.b64d(cuerpo)); falso["tipo"] = "otra"
    manipulada = f"{pref}.{lic.b64e(json.dumps(falso).encode())}.{firma}"
    ajena = emitir(Ed25519PrivateKey.generate(), instalacion=inst)
    for mala in (manipulada, ajena, "basura", "POS1.a.b", ""):
        assert c.post("/api/licencia", json={"clave": mala}).status_code == 400
    assert c.get("/api/productos").status_code == 402


def test_licencia_ligada_a_otra_instalacion(ctx):
    priv, c = ctx
    r = c.post("/api/licencia", json={"clave": emitir(priv, instalacion="AAAA-BBBB-CCCC-DDDD")})
    assert r.status_code == 400 and r.get_json()["estado"] == "otra_instalacion"


def test_expiracion_y_cobertura_de_version(ctx):
    priv, c = ctx
    inst = instalacion(c)
    ayer = (date.today() - timedelta(days=1)).isoformat()
    r = c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst, tipo="prueba", expira=ayer)})
    assert r.get_json()["estado"] == "expirada"
    r = c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst, actualizaciones_hasta="2020-01-01")})
    assert r.get_json()["estado"] == "version_no_cubierta"
    ok = emitir(priv, instalacion=inst, actualizaciones_hasta="2099-01-01")
    assert c.post("/api/licencia", json={"clave": ok}).status_code == 200


def test_licencia_activada_se_revalida_en_cada_peticion(tmp_path):
    priv, pub = par_de_llaves()
    ruta = str(tmp_path / "l.db")
    c = create_app(ruta, public_key_pem=pub).test_client()
    c.post("/api/licencia", json={"clave": emitir(priv, instalacion=instalacion(c))})
    entrar(c)
    assert c.get("/api/productos").status_code == 200
    # la misma base abierta con OTRA llave publica ya no es valida
    _, otra_pub = par_de_llaves()
    c2 = create_app(ruta, public_key_pem=otra_pub).test_client()
    assert c2.get("/api/productos").status_code == 402


def test_modo_desarrollo_sin_llave_publica(tmp_path):
    c = create_app(str(tmp_path / "d.db")).test_client()
    assert c.get("/api/licencia").get_json()["estado"] == "desarrollo"
    entrar(c)
    assert c.get("/api/productos").status_code == 200
    assert c.post("/api/licencia", json={"clave": "x"}).status_code == 400


def test_id_de_instalacion_es_estable(ctx):
    _, c = ctx
    assert instalacion(c) == instalacion(c) and len(instalacion(c)) == 19


def test_herramienta_de_linea_de_comandos(tmp_path):
    cli = [sys.executable, "tools/licencias.py"]
    sal = tmp_path / "llaves"
    subprocess.run(cli + ["generar-llaves", "--salida", str(sal)], check=True, capture_output=True)
    assert (sal / "privada.pem").stat().st_mode & 0o077 == 0  # solo el dueño puede leerla
    assert subprocess.run(cli + ["generar-llaves", "--salida", str(sal)], capture_output=True).returncode != 0
    clave = subprocess.run(
        cli + ["emitir", "--privada", str(sal / "privada.pem"), "--tienda", "Mi Tienda",
               "--instalacion", "AAAA-BBBB-CCCC-DDDD", "--actualizaciones-hasta", "2099-01-01"],
        check=True, capture_output=True, text=True).stdout.strip()
    out = subprocess.run(cli + ["verificar", "--publica", str(sal / "publica.pem"), clave],
                         check=True, capture_output=True, text=True).stdout
    assert json.loads(out)["tienda"] == "Mi Tienda"
    assert subprocess.run(cli + ["verificar", "--publica", str(sal / "publica.pem"), clave[:-4] + "AAAA"],
                          capture_output=True).returncode == 1
    assert subprocess.run(cli + ["emitir", "--privada", str(sal / "privada.pem"), "--tienda", "x",
                                 "--tipo", "prueba"], capture_output=True).returncode != 0
    # y la llave publica generada funciona en la app
    c = create_app(str(tmp_path / "x.db"), public_key_pem=(sal / "publica.pem").read_bytes()).test_client()
    inst_clave = subprocess.run(
        cli + ["emitir", "--privada", str(sal / "privada.pem"), "--tienda", "T", "--instalacion", instalacion(c)],
        check=True, capture_output=True, text=True).stdout.strip()
    assert c.post("/api/licencia", json={"clave": inst_clave}).status_code == 200


# ---------- Escenarios adicionales ----------
def firmar(priv, payload):
    cuerpo = json.dumps(payload, sort_keys=True).encode()
    return f"POS1.{lic.b64e(cuerpo)}.{lic.b64e(priv.sign(cuerpo))}"


def test_payload_con_tipos_raros_es_invalido_no_error_500(ctx):
    priv, c = ctx
    for extra in ({"expira": 12345}, {"actualizaciones_hasta": ["2030-01-01"]}, {"expira": "manana"},
                  {"instalacion": 5}, {"tienda": None, "actualizaciones_hasta": {}}):
        r = c.post("/api/licencia", json={"clave": firmar(priv, {"v": 1, "tienda": "T", "tipo": "vitalicia", **extra})})
        assert r.status_code == 400, extra
        assert c.get("/api/licencia").status_code == 200


def test_version_de_formato_desconocida_y_prefijo_en_minusculas(ctx):
    priv, c = ctx
    assert c.post("/api/licencia", json={"clave": firmar(priv, {"v": 2, "tienda": "T"})}).status_code == 400
    ok = emitir(priv, instalacion=instalacion(c))
    assert c.post("/api/licencia", json={"clave": ok.replace("POS1", "pos1", 1)}).status_code == 400
    assert c.post("/api/licencia", json={"clave": ok + "x"}).status_code == 400


def test_fechas_limite_son_inclusivas(ctx):
    priv, c = ctx
    inst = instalacion(c)
    hoy = date.today().isoformat()
    assert c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst, tipo="prueba", expira=hoy)}).status_code == 200
    from pos import FECHA_VERSION
    assert c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst, actualizaciones_hasta=FECHA_VERSION)}).status_code == 200


def test_renovar_reemplaza_la_licencia_anterior(ctx):
    priv, c = ctx
    inst = instalacion(c)
    c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst, tipo="prueba", expira="2099-01-01", tienda="Demo")})
    assert c.get("/api/licencia").get_json()["tipo"] == "prueba"
    c.post("/api/licencia", json={"clave": emitir(priv, instalacion=inst)})
    assert c.get("/api/licencia").get_json()["tipo"] == "vitalicia"


def test_licencia_guardada_corrupta_pide_reactivar_sin_romper(tmp_path):
    priv, pub = par_de_llaves()
    ruta = str(tmp_path / "x.db")
    app = create_app(ruta, public_key_pem=pub)
    c = app.test_client()
    c.post("/api/licencia", json={"clave": emitir(priv, instalacion=instalacion(c))})
    import sqlite3
    con = sqlite3.connect(ruta); con.execute("UPDATE licencia SET clave='POS1.@@@.###\n\t\u00f1'"); con.commit(); con.close()
    estado = create_app(ruta, public_key_pem=pub).test_client().get("/api/licencia").get_json()
    assert estado["estado"] == "invalida" and estado["activa"] is False


def test_reloj_atrasado_no_revive_una_prueba_vencida(tmp_path):
    """Si alguien regresa la fecha del sistema, la prueba no vuelve a funcionar."""
    import sqlite3
    priv, pub = par_de_llaves()
    ruta = str(tmp_path / "r.db")
    c = create_app(ruta, public_key_pem=pub).test_client()
    manana = (date.today() + timedelta(days=1)).isoformat()
    ok = emitir(priv, instalacion=instalacion(c), tipo="prueba", expira=manana)
    assert c.post("/api/licencia", json={"clave": ok}).status_code == 200
    # la app "ya vio" una fecha dentro de 10 dias (el usuario la uso despues y luego atraso el reloj)
    futuro = (date.today() + timedelta(days=10)).isoformat()
    con = sqlite3.connect(ruta)
    con.execute("INSERT OR REPLACE INTO ajustes (clave,valor) VALUES ('fecha_max',?)", (futuro,))
    con.commit(); con.close()
    assert create_app(ruta, public_key_pem=pub).test_client().get("/api/licencia").get_json()["estado"] == "expirada"
