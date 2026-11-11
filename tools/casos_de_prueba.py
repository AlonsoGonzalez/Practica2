#!/usr/bin/env python3
"""Genera docs/CASOS_DE_PRUEBA.md a partir de las pruebas reales (nombre, docstring y recorrido de navegador).

    python tools/casos_de_prueba.py
"""
import ast
import os
import re
import subprocess
import sys
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AREAS = {
    "test_pos.py": "Ventas, inventario, fiado, envases y sugerencia de pedido (flujo base)",
    "test_escenarios.py": "Escenarios límite: entradas raras, concurrencia, datos borrados, abusos",
    "test_auth.py": "Usuarios, roles, sesiones y permisos",
    "test_caja.py": "Turno de caja: apertura, movimientos, cierre y diferencias",
    "test_licencia.py": "Licencias firmadas, expiración, instalación y manipulación",
    "test_operacion.py": "Respaldos, arranque, rutas de datos y migración de bases viejas",
    "test_arranque.py": "Arranque de la app instalada: instancia única, servidor, configuración y errores",
    "test_e2e.py": "Recorrido completo en navegador real",
}


def humanizar(nombre):
    t = nombre.removeprefix("test_").replace("_", " ")
    return t[0].upper() + t[1:]


def casos_de(ruta):
    arbol = ast.parse(open(ruta, encoding="utf-8").read())
    for n in arbol.body:
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
            yield n.name, (ast.get_docstring(n) or "").split("\n")[0] or humanizar(n.name)


def ejecuciones_por_funcion():
    """Cuantas veces corre cada prueba (las parametrizadas se expanden)."""
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=RAIZ,
                         capture_output=True, text=True).stdout
    return Counter(re.match(r"tests/(\S+?)::(\w+)", l).groups() for l in out.splitlines() if re.match(r"tests/\S+::\w+", l))


def main():
    veces = ejecuciones_por_funcion()
    total = sum(veces.values())
    lineas = ["# Casos de prueba", "",
              f"Generado con `python tools/casos_de_prueba.py`. **{len(veces)} pruebas, {total} ejecuciones** "
              "(las parametrizadas corren varias veces). Se ejecutan con `pytest`.", ""]
    for archivo, titulo in AREAS.items():
        ruta = os.path.join(RAIZ, "tests", archivo)
        casos = list(casos_de(ruta))
        n = sum(veces[(archivo, nombre)] for nombre, _ in casos)
        lineas += [f"## {titulo}", f"`tests/{archivo}` · {len(casos)} pruebas · {n} ejecuciones", ""]
        lineas += [f"- {desc}" + (f" _(×{veces[(archivo, nombre)]})_" if veces[(archivo, nombre)] > 1 else "")
                   for nombre, desc in casos]
        lineas.append("")
    flujo = open(os.path.join(RAIZ, "tests", "e2e", "flujo.js"), encoding="utf-8").read()
    pasos = re.findall(r"console\.log\('(OK \d[^']*)'\)", flujo)
    lineas += ["## Pasos del recorrido en navegador (`tests/e2e/flujo.js`)", ""] + [f"- {p}" for p in pasos] + [""]
    out = os.path.join(RAIZ, "docs", "CASOS_DE_PRUEBA.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(lineas))
    print(f"{out}: {len(veces)} pruebas, {total} ejecuciones")


if __name__ == "__main__":
    main()
