#!/usr/bin/env python3
"""Herramienta del VENDEDOR para generar llaves y emitir licencias.

NO se distribuye con la app. La llave privada debe guardarse fuera del repo
(y respaldarse: si la pierdes no podras emitir mas licencias).

  python tools/licencias.py generar-llaves --salida ~/llaves-pos
  python tools/licencias.py emitir --privada ~/llaves-pos/privada.pem \
      --tienda "Abarrotes Dona Mary" --instalacion ABCD-1234-EF56-7890 \
      --actualizaciones-hasta 2027-11-11
  python tools/licencias.py verificar --publica pos/clave_publica.pem CLAVE
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from pos import licencia as lic  # noqa: E402


def generar_llaves(a):
    os.makedirs(a.salida, exist_ok=True)
    priv_path, pub_path = (os.path.join(a.salida, n) for n in ("privada.pem", "publica.pem"))
    if os.path.exists(priv_path):
        sys.exit(f"Ya existe {priv_path}; no se sobrescribe.")
    priv = Ed25519PrivateKey.generate()
    fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    with open(pub_path, "wb") as f:
        f.write(priv.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Llave privada (SECRETA, respaldala): {priv_path}")
    print(f"Llave publica: {pub_path}\nCopiala a pos/clave_publica.pem y publica la app.")


def emitir(a):
    with open(a.privada, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    payload = {"v": 1, "tienda": a.tienda, "tipo": a.tipo, "emitida": date.today().isoformat()}
    for campo, valor in (("instalacion", a.instalacion), ("actualizaciones_hasta", a.actualizaciones_hasta),
                         ("expira", a.expira)):
        if valor:
            if campo != "instalacion":
                date.fromisoformat(valor)  # valida el formato AAAA-MM-DD
            payload[campo] = valor
    if a.tipo == "prueba" and "expira" not in payload:
        sys.exit("Una licencia de prueba necesita --expira AAAA-MM-DD")
    cuerpo = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(f"{lic.PREFIJO}.{lic.b64e(cuerpo)}.{lic.b64e(priv.sign(cuerpo))}")


def verificar(a):
    with open(a.publica, "rb") as f:
        llave = lic.cargar_llave_publica(f.read())
    payload = lic.decodificar(a.clave, llave)
    print(json.dumps(payload, indent=2, ensure_ascii=False) if payload else "CLAVE INVALIDA")
    sys.exit(0 if payload else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar-llaves"); g.add_argument("--salida", required=True); g.set_defaults(f=generar_llaves)
    e = sub.add_parser("emitir"); e.set_defaults(f=emitir)
    e.add_argument("--privada", required=True); e.add_argument("--tienda", required=True)
    e.add_argument("--tipo", choices=["vitalicia", "prueba"], default="vitalicia")
    e.add_argument("--instalacion", help="ID que muestra la app en la pantalla de activacion")
    e.add_argument("--actualizaciones-hasta"); e.add_argument("--expira")
    v = sub.add_parser("verificar"); v.set_defaults(f=verificar)
    v.add_argument("--publica", required=True); v.add_argument("clave")
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
