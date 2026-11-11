#!/usr/bin/env python3
"""Genera instalador/icono.ico (carrito blanco sobre fondo rojo) sin dependencias. Reemplazalo por tu logo si quieres."""
import os
import struct
import zlib

N = 256
ROJO, BLANCO = (216, 0, 29, 255), (255, 255, 255, 255)


def dist_segmento(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def pixel(x, y):
    # fondo: cuadrado rojo redondeado
    cx, cy = min(max(x, 40), N - 41), min(max(y, 40), N - 41)
    if (x - cx) ** 2 + (y - cy) ** 2 > 40 ** 2:
        return (0, 0, 0, 0)
    canasta = 85 <= y <= 160 and (60 + (y - 85) * 0.27) <= x <= (212 - (y - 85) * 0.27)
    asa = dist_segmento(x, y, 36, 62, 66, 62) < 7 or dist_segmento(x, y, 66, 62, 82, 112) < 7
    base = dist_segmento(x, y, 84, 176, 186, 176) < 6
    ruedas = (x - 104) ** 2 + (y - 200) ** 2 < 15 ** 2 or (x - 174) ** 2 + (y - 200) ** 2 < 15 ** 2
    return BLANCO if (canasta or asa or base or ruedas) else ROJO


def png():
    filas = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(N)) for y in range(N))
    def trozo(tipo, datos):
        c = struct.pack(">I", len(datos)) + tipo + datos
        return c + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 6, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(filas, 9)) + trozo(b"IEND", b""))


def main():
    datos = png()
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(datos), 22) + datos
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instalador", "icono.ico")
    open(ruta, "wb").write(ico)
    print(ruta, len(ico), "bytes")


if __name__ == "__main__":
    main()
