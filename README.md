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

## Licencias (venta con licencia vitalicia)

Las licencias se firman con Ed25519. La app solo trae la llave **pública** y valida sin internet;
solo quien tiene la llave **privada** puede emitir claves.

**Una sola vez (tú, el vendedor):**
```bash
python tools/licencias.py generar-llaves --salida ~/llaves-pos   # fuera del repo
cp ~/llaves-pos/publica.pem pos/clave_publica.pem                # y súbela al repo
```
Respalda `privada.pem`: si la pierdes no podrás emitir más licencias, y si se filtra cualquiera podrá fabricarlas.

**Por cada cliente:**
1. El cliente instala la app; la pantalla de activación muestra su **ID de instalación**.
2. Tú emites la clave:
   ```bash
   python tools/licencias.py emitir --privada ~/llaves-pos/privada.pem \
       --tienda "Abarrotes Doña Mary" --instalacion ABCD-1234-EF56-7890 \
       --actualizaciones-hasta 2027-11-11
   ```
   Opciones: `--tipo prueba --expira AAAA-MM-DD` para demos; sin `--instalacion` la clave sirve en cualquier equipo.
3. El cliente la pega en la pantalla de activación.

`--actualizaciones-hasta` implementa "vitalicia + actualizaciones por 1 año": la licencia sigue funcionando
para siempre en las versiones publicadas hasta esa fecha (`FECHA_VERSION` en `pos/__init__.py`); una
versión posterior pide renovar. Verifica una clave con `python tools/licencias.py verificar --publica pos/clave_publica.pem CLAVE`.

Sin `pos/clave_publica.pem` la app corre en **modo desarrollo** (sin licencia). En producción
define `POS_REQUIRE_LICENSE=1` para que no arranque sin llave pública.
