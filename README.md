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
python servidor.py     # http://localhost:5000  (modo produccion; `python run.py` es solo para desarrollo)
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

### Para el cliente final (sin terminal)
1. Doble clic en `PuntoDeVenta-Setup-….exe` y *Siguiente* hasta terminar (opcional: acceso directo en el escritorio
   y abrirlo solo al encender la computadora).
2. Abrir **Punto de Venta** desde el escritorio o el menú Inicio. Aparece una ventanita con el botón
   **Abrir el sistema** y se abre el navegador solo.
3. La primera vez pide activar la licencia (el ID de instalación se muestra en pantalla) y crear la cuenta del dueño.

La ventanita muestra siempre si el **acceso desde tablet o celular** está activado y permite cambiarlo (casilla + dirección que se escribe en la tablet).
Instalar o reinstalar lo deja **apagado**; se enciende solo a propósito. También permite
abrir la carpeta de respaldos y cerrar el sistema. Si se hace doble clic otra vez con el sistema abierto, solo se
vuelve a abrir el navegador (nunca queda una segunda copia). Actualizar = ejecutar el instalador nuevo encima.

- Los datos viven en `%APPDATA%\PuntoVentaAbarrotes\` (base de datos, `respaldos\`, `logs\pos.log`, `config.json`),
  fuera de la carpeta del programa: actualizar o desinstalar **no** los borra.
- **Respaldos** (`respaldos\`): se hacen solos al abrir el sistema, cada 4 horas, **al cerrar cada turno** y al cerrar el
  sistema, y a mano con «Respaldar ahora». Se conserva todo lo de las últimas 24 h y el último de cada día del último mes.
  El dueño los ve y **restaura** desde la pestaña *Respaldos* (antes de restaurar se guarda una copia de lo actual).
  Pide al cliente copiar `respaldos` a una USB de vez en cuando.
- Si algo falla al arrancar, aparece un aviso y el detalle técnico queda en `logs\pos.log`.
- La versión instalada **siempre exige licencia** y necesita `pos/clave_publica.pem` al compilar.

### Cómo se obtiene el instalador (GitHub compila y prueba en Windows)
El flujo `.github/workflows/instalador.yml` corre en un Windows real: ejecuta las pruebas, empaqueta con PyInstaller,
prueba el programa suelto (con y sin ventana), compila con Inno Setup, **lo instala en silencio, vende y cierra caja
con lo instalado, lo desinstala y verifica que los datos se conserven**.
- Cada push que toque el programa lo ejecuta. Sin tu llave genera una de **prueba** (artefacto `…SOLO-PRUEBA`,
  no sirve para vender). Se descarga en GitHub → *Actions* → la ejecución → *Artifacts*.
- Para **vender**: genera tus llaves (sección Licencias), sube `pos/clave_publica.pem`, y publica una etiqueta:
  `git tag v1.0.0 && git push --tags`. Esa ejecución usa tu llave y deja el artefacto `PuntoDeVenta-Setup`.
- Windows mostrará "SmartScreen protegió su PC" porque el instalador no está firmado: *Más información → Ejecutar de todas formas*.
  Un certificado de firma de código lo evita (cuesta por año).
- Sin GitHub, en una PC con Windows: `pip install -r requirements-build.txt`, `pyinstaller --noconfirm instalador/pos.spec`,
  `iscc /DVersion=1.0.0 instalador\pos.iss`. `python servidor.py --sin-ventana` corre sin ventana (soporte técnico).

### Entregar una venta
1. El cliente instala, abre el programa y te manda el **ID de instalación** que aparece en pantalla.
2. Emites su clave (`tools/licencias.py emitir ...`) y se la envías; la pega y queda activado.

### Usuarios y acceso desde tablet
- La primera vez que se abre, el sistema pide crear la cuenta del **dueño**. Después hay dos roles:
  **dueño** (todo) y **cajero** (cobrar, fiado/abonos y recibir envases; no ve costos, utilidades ni inventario).
  El dueño administra usuarios en la pestaña *Usuarios*; cada venta queda registrada con quién la hizo.
- Contraseñas con hash (scrypt), bloqueo tras 5 intentos fallidos, sesión de 12 h y cookie `HttpOnly`/`SameSite=Lax`.
  Desactivar a un usuario o cambiarle la contraseña cierra sus sesiones abiertas al instante.
- **Tablet/celular:** marcar la casilla "Permitir usar el sistema desde una tablet o celular" de la ventanita
  (o `python servidor.py --lan`). La ventanita y la pestaña *Usuarios* muestran la dirección (ej. `http://192.168.1.50:5000`) que se
  escribe en el navegador de la tablet, conectada al mismo Wi-Fi. La computadora debe estar encendida con el programa abierto.
  Conviene reservar una IP fija para esa computadora en el router para que la dirección no cambie.
- El tráfico dentro del Wi-Fi va por HTTP sin cifrar: usa una red privada con contraseña, nunca un Wi-Fi público,
  y no expongas el puerto a internet.

## Turno de caja
Cada usuario abre su turno con un fondo inicial antes de cobrar (sin turno abierto no se puede vender,
registrar abonos ni recibir envases). Durante el turno se registran retiros e ingresos de efectivo con su motivo.
Al cerrar, la persona cuenta el dinero **sin ver cuánto debería haber** (conteo ciego) y el sistema calcula la diferencia:

`esperado = fondo + ventas en efectivo + abonos + ingresos - retiros - casco reembolsado` (el fiado no entra).

El dueño ve todos los turnos, las diferencias (faltantes en rojo, sobrantes en naranja) y puede cerrar un turno que
quedó abierto. El corte del día incluye la tabla de turnos.

## Pruebas
```bash
pip install -r requirements.txt
pytest                        # 137 ejecuciones: API, permisos, concurrencia, licencias, respaldos, navegador
python tools/casos_de_prueba.py   # regenera docs/CASOS_DE_PRUEBA.md (lista de todos los casos)
```
La prueba de navegador (`tests/test_e2e.py`) usa Node + Playwright y se omite sola si no están instalados.
Ver [docs/CASOS_DE_PRUEBA.md](docs/CASOS_DE_PRUEBA.md).
