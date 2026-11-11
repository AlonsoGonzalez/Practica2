# Punto de Venta - Tienda de Abarrotes

Punto de venta web (Flask + SQLite) para una tienda de abarrotes con catálogo de
productos Coca-Cola (refrescos, agua, jugos, Powerade) y abarrotes generales.

## Funciones
- **Venta y cobro**: búsqueda / lector de código de barras, ticket, cambio, descuento automático de stock.
- **Inventario**: alta, edición, baja, entradas y mermas, alerta de stock bajo.
- **Corte de caja**: ventas del día, total, utilidad, ticket promedio, más vendidos, efectivo real en caja.
- **Fiado**: clientes con límite de crédito, venta a fiado, abonos y total por cobrar.
- **Retornables con casco**: se cobra el depósito por envase salvo que el cliente entregue uno vacío; devolución con reembolso de casco, canje de vacíos con el proveedor y control de envases en calle.
- **Sugerencia de pedido**: calcula cuánto pedir según lo vendido en los últimos N días y los días a cubrir, con costo estimado.

Los montos se guardan en centavos (enteros) para evitar errores de redondeo.

## Uso
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py          # http://localhost:5000
pytest                 # pruebas
```
La base de datos `pos.db` se crea sola con productos de ejemplo.
