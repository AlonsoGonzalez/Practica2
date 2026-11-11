"""Validacion estricta de entradas: nada de excepciones 500 por datos raros."""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import request

MAX_CENTAVOS = 10**10      # 100 millones de pesos
MAX_ENTERO = 10**7
MAX_CANTIDAD = 10**5
MAX_LINEAS = 200

_ENTERO = re.compile(r"^[+-]?\d{1,15}$")


def datos():
    """Cuerpo JSON como dict; cualquier otra cosa (lista, texto, vacio...) se trata como {}."""
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def opcional(d, clave, por_defecto):
    """Campo opcional de un formulario: ausente, null o "" significan "usar el valor por defecto"."""
    v = d.get(clave)
    return por_defecto if v is None or (isinstance(v, str) and not v.strip()) else v


def entero(valor, minimo=None, maximo=None):
    """Entero estricto: acepta 3, 3.0 y "3"; rechaza 1.5, True, None, "abc", listas..."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError("Numero invalido")
    if isinstance(valor, int):
        n = valor
    elif isinstance(valor, float) and valor.is_integer():
        n = int(valor)
    elif isinstance(valor, str) and _ENTERO.match(valor.strip()):
        n = int(valor)
    else:
        raise ValueError("Numero invalido")
    if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
        raise ValueError("Numero fuera de rango")
    return n


def centavos(valor):
    """Pesos (18.5, "18.50", 18) -> centavos exactos. Rechaza NaN, infinito, bool, None y montos absurdos."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError("Monto invalido")
    try:
        d = Decimal(str(valor).strip())
    except InvalidOperation:
        raise ValueError("Monto invalido")
    if not d.is_finite():
        raise ValueError("Monto invalido")
    if abs(d) > Decimal(MAX_CENTAVOS) / 100:  # antes de operar: evita desbordar la precision de Decimal
        raise ValueError("Monto fuera de rango")
    return int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def texto(valor, maximo, obligatorio=False):
    t = "" if valor is None else str(valor).strip()
    if len(t) > maximo or (obligatorio and not t):
        raise ValueError("Texto invalido")
    return t
