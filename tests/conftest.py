import pytest


@pytest.fixture(autouse=True)
def sin_dialogos(monkeypatch):
    """Ninguna prueba debe abrir ventanas de aviso (en un servidor de CI nadie les da clic y se quedan esperando)."""
    monkeypatch.setenv("POS_SIN_DIALOGOS", "1")
