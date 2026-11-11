"""Preferencias del usuario (config.json en la carpeta de datos). Un archivo danado nunca impide abrir la app."""
import json
import os

from . import paths

POR_DEFECTO = {"lan": False}


def _ruta():
    return os.path.join(paths.datos_dir(), "config.json")


def cargar():
    try:
        with open(_ruta(), encoding="utf-8") as f:
            guardado = json.load(f)
        return {**POR_DEFECTO, **{k: v for k, v in guardado.items() if k in POR_DEFECTO}} if isinstance(guardado, dict) else dict(POR_DEFECTO)
    except (OSError, ValueError):
        return dict(POR_DEFECTO)


def guardar(cfg):
    with open(_ruta(), "w", encoding="utf-8") as f:
        json.dump({k: cfg[k] for k in POR_DEFECTO if k in cfg}, f)
