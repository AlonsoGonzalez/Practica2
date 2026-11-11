# Punto de Venta - Tienda de Abarrotes

Punto de venta web (Flask + SQLite) para una tienda de abarrotes con catálogo de
productos Coca-Cola (refrescos, agua, jugos, Powerade) y abarrotes generales.

## Funciones
- **Venta y cobro**: búsqueda / lector de código de barras, ticket, cambio, descuento automático de stock.
- **Inventario**: alta, edición, baja, entradas y mermas, alerta de stock bajo.
- **Corte de caja**: ventas del día, total, utilidad, ticket promedio, más vendidos.

Los montos se guardan en centavos (enteros) para evitar errores de redondeo.

## Uso
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py          # http://localhost:5000
pytest                 # pruebas
```
La base de datos `pos.db` se crea sola con productos de ejemplo.
