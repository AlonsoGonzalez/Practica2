"""Arranque de la aplicacion instalada: instancia unica, servidor, configuracion y registro de errores."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from pos import config, create_app, licencia
from servidor import Servidor, main, ya_corriendo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def puerto_cualquiera():
    """Puerto libre FUERA del rango temporal del sistema (32768+ en Linux, 49152+ en Windows): ahi un puerto cerrado
    puede "conectarse consigo mismo" y confundir a quien lo revisa."""
    import random
    for _ in range(200):
        p = random.randrange(20000, 30000)
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no hay puertos libres")


def escucha(puerto):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.load(r)


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_DATA_DIR", str(tmp_path / "datos"))
    monkeypatch.setenv("POS_NO_BROWSER", "1")
    monkeypatch.setenv("POS_DB", str(tmp_path / "datos" / "pos.db"))
    return tmp_path / "datos"


def test_ping_es_publico_aun_exigiendo_licencia_y_sesion(tmp_path):
    from tests.test_licencia import par_de_llaves
    _, pub = par_de_llaves()
    c = create_app(str(tmp_path / "p.db"), public_key_pem=pub).test_client()
    assert c.get("/api/productos").status_code == 402
    r = c.get("/api/ping")
    assert r.status_code == 200 and r.get_json()["app"] == "punto-de-venta"


def test_servidor_arranca_responde_y_se_detiene(tmp_path):
    srv = Servidor(create_app(str(tmp_path / "s.db")), puerto_inicial=puerto_cualquiera())
    srv.iniciar()
    try:
        assert get(f"{srv.url}/api/ping")["app"] == "punto-de-venta"
    finally:
        srv.detener()
    assert not escucha(srv.puerto)   # el puerto queda libre para volver a abrir


def test_activar_y_desactivar_la_tablet_conserva_el_puerto(tmp_path):
    app = create_app(str(tmp_path / "s.db"))
    srv = Servidor(app, puerto_inicial=puerto_cualquiera())
    srv.iniciar()
    try:
        puerto = srv.puerto
        assert app.config["LAN_URLS"] == [] and srv.urls_lan() == []
        srv.reiniciar(True)
        assert srv.lan and srv.puerto == puerto and get(f"{srv.url}/api/ping")["app"] == "punto-de-venta"
        assert app.config["LAN_URLS"] and all(u.endswith(f":{puerto}") for u in app.config["LAN_URLS"])
        srv.reiniciar(False)
        assert not srv.lan and app.config["LAN_URLS"] == [] and get(f"{srv.url}/api/ping")
    finally:
        srv.detener()


def test_ya_corriendo_distingue_nuestra_app_de_otros_programas(tmp_path):
    ajeno = socket.socket(); ajeno.bind(("127.0.0.1", 0)); ajeno.listen()   # algo escucha pero no habla HTTP
    p_ajeno = ajeno.getsockname()[1]
    try:
        assert ya_corriendo(p_ajeno) is None
        srv = Servidor(create_app(str(tmp_path / "s.db")), puerto_inicial=puerto_cualquiera())
        srv.iniciar()
        try:
            assert ya_corriendo(srv.puerto) == srv.puerto
        finally:
            srv.detener()
        assert ya_corriendo(srv.puerto) is None
    finally:
        ajeno.close()


def test_segundo_doble_clic_no_levanta_otra_copia(datos, tmp_path, monkeypatch):
    puerto = puerto_cualquiera()
    srv = Servidor(create_app(str(datos / "pos.db")), puerto_inicial=puerto)
    srv.iniciar()
    try:
        monkeypatch.setenv("POS_PORT", str(puerto))
        assert main(["--sin-ventana"]) == 0           # regresa de inmediato
        assert not escucha(puerto + 1)                 # y no abrio un segundo servidor
    finally:
        srv.detener()


def test_configuracion_persistente_y_a_prueba_de_archivos_danados(datos):
    assert config.cargar() == {"lan": False}
    config.guardar({"lan": True, "otra_cosa": 1})
    assert config.cargar() == {"lan": True}
    for contenido in ("{ no es json", "[1,2,3]", '"texto"', ""):
        (datos / "config.json").write_text(contenido)
        assert config.cargar() == {"lan": False}, contenido


def test_main_devuelve_error_y_deja_registro_si_no_puede_arrancar(datos, monkeypatch):
    os.makedirs(datos / "pos.db")                      # una carpeta donde deberia ir la base
    monkeypatch.setenv("POS_PORT", str(puerto_cualquiera()))
    assert main(["--sin-ventana"]) == 1
    assert "no pudo arrancar" in (datos / "logs" / "pos.log").read_text()


def test_programa_completo_como_proceso_aparte(tmp_path):
    """Lo mismo que hace el doble clic: arranca, atiende, un segundo lanzamiento no duplica y se apaga."""
    puerto = puerto_cualquiera()
    env = {**os.environ, "POS_DATA_DIR": str(tmp_path / "d"), "POS_NO_BROWSER": "1", "POS_PORT": str(puerto),
           "POS_DB": str(tmp_path / "d" / "pos.db"), "PYTHONPATH": RAIZ, "POS_SIN_DIALOGOS": "1"}
    salida = open(tmp_path / "salida.txt", "w+")
    p = subprocess.Popen([sys.executable, "servidor.py", "--sin-ventana"], cwd=RAIZ, env=env,
                         stdout=salida, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            if escucha(puerto) or p.poll() is not None:
                break
            time.sleep(0.25)
        if not escucha(puerto):
            salida.flush(); salida.seek(0)
            log = tmp_path / "d" / "logs" / "pos.log"
            pytest.fail(f"el programa no escucha (codigo de salida: {p.poll()})\n--- salida ---\n{salida.read()}"
                        f"\n--- pos.log ---\n{log.read_text() if log.exists() else '(sin registro)'}")
        assert get(f"http://localhost:{puerto}/api/ping")["app"] == "punto-de-venta"
        segundo = subprocess.run([sys.executable, "servidor.py", "--sin-ventana"], cwd=RAIZ, env=env, timeout=30)
        assert segundo.returncode == 0 and not escucha(puerto + 1)
        assert os.path.exists(tmp_path / "d" / "respaldos")     # el respaldo diario se hizo al abrir
    finally:
        p.terminate()
        p.wait(10)


def test_apagar_tablet_desactiva_el_acceso_y_termina_sin_abrir_nada(datos):
    """Lo ejecuta el instalador: una instalacion nueva nunca deja el sistema visible en la red."""
    config.guardar({"lan": True})
    assert config.cargar()["lan"] is True
    assert main(["--apagar-tablet"]) == 0
    assert config.cargar()["lan"] is False
    assert not (datos / "logs").exists()      # no arranco el programa: solo cambio la preferencia


@pytest.mark.skipif(os.name == "nt", reason="Windows no puede mandar Ctrl+C a un proceso hijo")
def test_respaldos_al_abrir_periodicos_y_al_cerrar(tmp_path):
    """Antes el respaldo era solo uno al abrir; el del dia no tenia ninguna venta. Ahora: abrir + cada X horas + cerrar."""
    import signal
    from pos.respaldos import listar
    puerto = puerto_cualquiera()
    env = {**os.environ, "POS_DATA_DIR": str(tmp_path / "d"), "POS_NO_BROWSER": "1", "POS_PORT": str(puerto),
           "POS_DB": str(tmp_path / "d" / "pos.db"), "PYTHONPATH": RAIZ, "POS_SIN_DIALOGOS": "1",
           "POS_RESPALDO_HORAS": "0.0006"}                    # ~2 segundos, para la prueba
    p = subprocess.Popen([sys.executable, "servidor.py", "--sin-ventana"], cwd=RAIZ, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    carpeta = str(tmp_path / "d" / "respaldos")
    try:
        for _ in range(60):
            if escucha(puerto):
                break
            time.sleep(0.25)
        for _ in range(60):                                   # espera al menos un respaldo periodico
            if any(r["motivo"] == "auto" for r in listar(carpeta)):
                break
            time.sleep(0.25)
        motivos = {r["motivo"] for r in listar(carpeta)}
        assert {"inicio", "auto"} <= motivos, motivos
        p.send_signal(signal.SIGINT)                           # como cerrar la ventana de la consola
        p.wait(15)
    finally:
        if p.poll() is None:
            p.kill()
    assert "al-cerrar" in {r["motivo"] for r in listar(carpeta)}


def test_regla_de_firewall_solo_para_redes_privadas_y_de_dominio():
    import firewall
    args = firewall.argumentos_agregar(r"C:\Programas\PuntoDeVenta\PuntoDeVenta.exe")
    assert "profile=private,domain" in args and "action=allow" in args and "dir=in" in args
    assert not any("public" in a.lower() for a in args)          # nunca en redes publicas
    assert args[-1] == "protocol=TCP" and any(a.startswith("program=") for a in args)
    assert firewall.argumentos_quitar()[-1] == f"name={firewall.NOMBRE}"
    if not firewall.es_windows():                                  # fuera de Windows no hace nada ni falla
        assert firewall.existe() is False and firewall.agregar() is False


def test_navegador_cae_a_edge_si_windows_no_tiene_uno_predeterminado(monkeypatch):
    import navegador
    abiertos, lanzados = [], []
    monkeypatch.setattr(navegador.webbrowser, "open", lambda u: abiertos.append(u))
    monkeypatch.setattr(navegador.subprocess, "Popen", lambda cmd, **kw: lanzados.append(cmd))
    monkeypatch.setattr(navegador, "hay_navegador_predeterminado", lambda: True)
    assert navegador.abrir("http://localhost:5000") == "predeterminado" and abiertos == ["http://localhost:5000"] and not lanzados
    monkeypatch.setattr(navegador, "hay_navegador_predeterminado", lambda: False)
    assert navegador.abrir("http://localhost:5000") == "edge"
    assert lanzados and "msedge" in lanzados[0] and lanzados[0][-1] == "http://localhost:5000"
    # si Edge tampoco se puede lanzar, lo intenta con el predeterminado en vez de fallar
    def falla(*a, **k): raise OSError("no hay edge")
    monkeypatch.setattr(navegador.subprocess, "Popen", falla)
    abiertos.clear()
    assert navegador.abrir("http://localhost:5001") == "predeterminado" and abiertos == ["http://localhost:5001"]


def test_una_autoconexion_tcp_no_se_toma_por_nuestra_app(monkeypatch):
    """En Windows un puerto cerrado puede conectarse consigo mismo y devolver la propia peticion como respuesta."""
    import http.client
    import servidor
    def autoconexion(*a, **k):
        raise http.client.BadStatusLine("GET /api/ping HTTP/1.1")
    monkeypatch.setattr(servidor.urllib.request, "urlopen", autoconexion)
    assert servidor._es_nuestra_app(5000) is False
    assert servidor.ya_corriendo(5000) is None
