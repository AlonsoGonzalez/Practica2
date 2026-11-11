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

## Instalador y producción

**Cada tienda corre el sistema en su propia computadora: no hace falta dominio, hosting ni internet.**
La licencia también se valida sin conexión.

- `servidor.py` es lo que ejecuta el instalador: sirve la app con waitress en `http://localhost:5000`
  (si el puerto está ocupado usa el siguiente) y abre el navegador. `POS_LAN=1` la expone en la red local
  para usar la caja desde una tablet o celular de la tienda (ver advertencia de seguridad abajo).
- Los datos viven en `%APPDATA%\PuntoVentaAbarrotes\` (Windows), fuera de la carpeta del programa:
  actualizar o desinstalar **no** borra la base de datos. Cada día que se abre la app se guarda una copia en
  `respaldos\` (se conservan las últimas 14). Pide al cliente copiar esa carpeta a una USB de vez en cuando.
- La versión instalada **siempre exige licencia** y necesita `pos/clave_publica.pem` al compilar.

### Compilar el instalador de Windows
1. Genera tus llaves y copia `pos/clave_publica.pem` (ver sección Licencias) y súbela al repo.
2. `git tag v1.0.0 && git push --tags`: la acción de GitHub (`.github/workflows/instalador.yml`) compila con
   PyInstaller + Inno Setup y deja `PuntoDeVenta-Setup-1.0.0.exe` como artefacto de la ejecución.
   También se puede lanzar a mano desde la pestaña Actions.
3. Localmente (en Windows): `pip install -r requirements-build.txt`, `pyinstaller --noconfirm instalador/pos.spec`,
   `iscc /DVersion=1.0.0 instalador\pos.iss`.

### Entregar una venta
1. El cliente instala, abre el programa y te manda el **ID de instalación** que aparece en pantalla.
2. Emites su clave (`tools/licencias.py emitir ...`) y se la envías; la pega y queda activado.

### Actualizar a un cliente
Basta con que ejecute el instalador de la versión nueva encima: conserva sus datos y su licencia.
Recuerda subir `FECHA_VERSION` en `pos/__init__.py` en cada versión.

### Usuarios y acceso desde tablet
- La primera vez que se abre, el sistema pide crear la cuenta del **dueño**. Después hay dos roles:
  **dueño** (todo) y **cajero** (cobrar, fiado/abonos y recibir envases; no ve costos, utilidades ni inventario).
  El dueño administra usuarios en la pestaña *Usuarios*; cada venta queda registrada con quién la hizo.
- Contraseñas con hash (scrypt), bloqueo tras 5 intentos fallidos, sesión de 12 h y cookie `HttpOnly`/`SameSite=Lax`.
  Desactivar a un usuario o cambiarle la contraseña cierra sus sesiones abiertas al instante.
- **Tablet/celular:** abrir el programa con el acceso directo *"Punto de Venta (con acceso desde tablet)"*
  (o `python servidor.py --lan`). La pestaña *Usuarios* muestra la dirección (ej. `http://192.168.1.50:5000`) que se
  escribe en el navegador de la tablet, conectada al mismo Wi-Fi. La computadora debe estar encendida con el programa abierto.
  Conviene reservar una IP fija para esa computadora en el router para que la dirección no cambie.
- El tráfico dentro del Wi-Fi va por HTTP sin cifrar: usa una red privada con contraseña, nunca un Wi-Fi público,
  y no expongas el puerto a internet.
