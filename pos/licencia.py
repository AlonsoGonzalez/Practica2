"""Licencias firmadas con Ed25519.

Formato de la clave:  POS1.<payload base64url>.<firma base64url>

* El payload es un JSON con los datos de la licencia.
* La firma se calcula con la llave PRIVADA del vendedor (nunca va en este repo).
* La app solo conoce la llave PUBLICA, asi que puede validar licencias sin internet
  pero no puede fabricarlas.

Campos del payload:
  v                    version del formato (1)
  tienda               nombre del negocio
  tipo                 "vitalicia" | "prueba"
  instalacion          id de la instalacion a la que esta ligada (opcional)
  emitida              fecha de emision (AAAA-MM-DD)
  actualizaciones_hasta  la licencia cubre versiones publicadas hasta esa fecha (opcional)
  expira               fecha limite de uso, p. ej. para pruebas (opcional)
"""
import base64
import json
import uuid
from datetime import date

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key

PREFIJO = "POS1"

ACTIVA = "activa"
SIN_LICENCIA = "sin_licencia"
INVALIDA = "invalida"
EXPIRADA = "expirada"
VERSION_NO_CUBIERTA = "version_no_cubierta"
OTRA_INSTALACION = "otra_instalacion"
DESARROLLO = "desarrollo"  # no hay llave publica configurada: no se exige licencia

MENSAJES = {
    SIN_LICENCIA: "Esta instalacion no tiene licencia. Ingresa tu clave para activarla.",
    INVALIDA: "La clave de licencia no es valida.",
    EXPIRADA: "La licencia expiro.",
    VERSION_NO_CUBIERTA: "Tu licencia no cubre esta version. Renueva las actualizaciones.",
    OTRA_INSTALACION: "Esta clave fue emitida para otra instalacion.",
}


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def nuevo_id_instalacion() -> str:
    h = uuid.uuid4().hex[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def cargar_llave_publica(pem):
    if not pem:
        return None
    return load_pem_public_key(pem if isinstance(pem, bytes) else pem.encode())


def normalizar(clave: str) -> str:
    return "".join((clave or "").split())  # quita espacios y saltos de linea


def decodificar(clave: str, llave_publica):
    """Devuelve el payload (dict) si la firma es valida; si no, None."""
    try:
        prefijo, cuerpo, firma = normalizar(clave).split(".")
        if prefijo != PREFIJO:
            return None
        payload_bytes = b64d(cuerpo)
        llave_publica.verify(b64d(firma), payload_bytes)
        payload = json.loads(payload_bytes)
        return payload if isinstance(payload, dict) and payload.get("v") == 1 else None
    except (ValueError, InvalidSignature, TypeError):
        return None


def evaluar(clave, llave_publica, instalacion_id, fecha_version, hoy=None):
    """Devuelve (estado, payload|None)."""
    if llave_publica is None:
        return DESARROLLO, None
    if not clave:
        return SIN_LICENCIA, None
    payload = decodificar(clave, llave_publica)
    if payload is None:
        return INVALIDA, None
    # Una clave bien firmada pero con campos de tipo raro se considera invalida (nunca un error 500).
    try:
        for campo in ("tienda", "tipo", "instalacion"):
            if payload.get(campo) is not None and not isinstance(payload[campo], str):
                raise ValueError(campo)
        for campo in ("expira", "actualizaciones_hasta"):
            if payload.get(campo) is not None:
                date.fromisoformat(payload[campo])  # TypeError/ValueError si no es una fecha AAAA-MM-DD
    except (TypeError, ValueError):
        return INVALIDA, None
    hoy = (hoy or date.today()).isoformat()
    if payload.get("instalacion") and payload["instalacion"] != instalacion_id:
        return OTRA_INSTALACION, payload
    if payload.get("expira") and hoy > payload["expira"]:
        return EXPIRADA, payload
    if payload.get("actualizaciones_hasta") and fecha_version > payload["actualizaciones_hasta"]:
        return VERSION_NO_CUBIERTA, payload
    return ACTIVA, payload
