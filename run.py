"""Servidor de DESARROLLO (recarga solo con cada cambio). Para usar el sistema en la tienda
ejecuta `python servidor.py`, que es el modo de produccion."""
from pos import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)  # solo local: el modo debug nunca debe quedar expuesto a la red
