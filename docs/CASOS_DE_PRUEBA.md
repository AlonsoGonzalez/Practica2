# Casos de prueba

Generado con `python tools/casos_de_prueba.py`. **94 pruebas, 145 ejecuciones** (las parametrizadas corren varias veces). Se ejecutan con `pytest`.

## Ventas, inventario, fiado, envases y sugerencia de pedido (flujo base)
`tests/test_pos.py` · 11 pruebas · 11 ejecuciones

- Catalogo semilla
- Venta descuenta stock y calcula cambio
- Venta rechaza stock insuficiente y pago corto
- Inventario crud y ajuste
- Corte de caja
- Stock bajo
- Fiado saldo limite y abonos
- Retornables casco
- Envases devueltos solo en retornables
- Sugerencia pedido
- Respaldo diario y rotacion

## Escenarios límite: entradas raras, concurrencia, datos borrados, abusos
`tests/test_escenarios.py` · 25 pruebas · 76 ejecuciones

- Un cuerpo que no es un objeto JSON nunca debe romper el servidor. _(×36)_
- Cantidades invalidas en venta _(×10)_
- Montos invalidos no rompen _(×8)_
- Items mal formados
- Convertir pesos a centavos nunca pierde un centavo (todos los montos de 0.00 a 999.99).
- Producto con datos invalidos
- Textos con html y unicode se guardan tal cual
- Busqueda no es vulnerable a inyeccion sql
- El tendero borra un producto por error y lo vuelve a dar de alta con el mismo codigo.
- Producto borrado no se puede vender ni ajustar
- Mismo producto en dos lineas se suma y valida stock
- Vender todo el stock y luego ya no
- Pago exacto y un centavo menos
- Fiado limite exacto y abonos limite
- Fiado cliente inexistente y metodo invalido
- Fiado incluye el casco en la deuda
- Envases casos limite
- Sugerencia parametros extremos
- Sugerencia sin ventas pide hasta el minimo
- Corte con fecha invalida o sin ventas
- Con 1 pieza en stock y 8 ventas simultaneas, exactamente una debe tener exito.
- Abonos simultaneos no dejan saldo negativo
- Errores de api siempre son json
- Cookie de sesion basura se trata como sin sesion
- El formulario web manda "" en los campos que el tendero deja en blanco.

## Usuarios, roles, sesiones y permisos
`tests/test_auth.py` · 10 pruebas · 10 ejecuciones

- Primer uso configura al dueno una sola vez
- Api exige sesion
- Login logout y credenciales incorrectas
- Bloqueo por intentos fallidos
- Cajero solo cobra y no ve costos
- Ventas registran al cajero y corte las separa
- Administrar usuarios
- Cambiar password cierra otras sesiones
- Sesion sobrevive reinicio y cookie segura
- Licencia se revisa antes que la sesion

## Turno de caja: apertura, movimientos, cierre y diferencias
`tests/test_caja.py` · 15 pruebas · 15 ejecuciones

- No se puede cobrar sin turno abierto
- Abonos y devolucion de envases tambien exigen turno
- Abrir turno valida fondo y no permite dos
- esperado = fondo + efectivo + abonos + ingresos - retiros - casco reembolsado (el fiado no cuenta).
- Conteo ciego el cajero no ve el esperado pero el dueno si
- Sobrante y cierre exacto
- Cierre invalido no cierra el turno
- Retiros validos e invalidos
- Movimiento sin turno
- Cada cajero tiene su propio turno
- Dueno cierra el turno olvidado de un cajero desactivado
- El cajero no puede ver ni cerrar turnos ajenos
- Corte del dia lista los turnos con su diferencia
- Dos aperturas simultaneas solo crean un turno
- Ventas quedan ligadas al turno y el historial sobrevive

## Licencias firmadas, expiración, instalación y manipulación
`tests/test_licencia.py` · 15 pruebas · 15 ejecuciones

- Sin licencia bloquea api pero no la pantalla
- Activar licencia valida
- Clave manipulada o de otra llave se rechaza
- Licencia ligada a otra instalacion
- Expiracion y cobertura de version
- Licencia activada se revalida en cada peticion
- Modo desarrollo sin llave publica
- Id de instalacion es estable
- Herramienta de linea de comandos
- Payload con tipos raros es invalido no error 500
- Version de formato desconocida y prefijo en minusculas
- Fechas limite son inclusivas
- Renovar reemplaza la licencia anterior
- Licencia guardada corrupta pide reactivar sin romper
- Si alguien regresa la fecha del sistema, la prueba no vuelve a funcionar.

## Respaldos, arranque, rutas de datos y migración de bases viejas
`tests/test_operacion.py` · 9 pruebas · 9 ejecuciones

- Respaldo es idempotente el mismo dia
- Rotacion no borra archivos ajenos
- Respaldo seguro no tumba el arranque
- Respaldo restaurado contiene las ventas
- Puerto ocupado usa el siguiente
- Direcciones para la tablet incluyen el nombre del equipo
- Rutas de datos
- Version instalada se niega a arrancar sin llave publica
- Una tienda que ya usaba la version 1 actualiza y conserva sus productos y ventas.

## Arranque de la app instalada: instancia única, servidor, configuración y errores
`tests/test_arranque.py` · 8 pruebas · 8 ejecuciones

- Ping es publico aun exigiendo licencia y sesion
- Servidor arranca responde y se detiene
- Activar y desactivar la tablet conserva el puerto
- Ya corriendo distingue nuestra app de otros programas
- Segundo doble clic no levanta otra copia
- Configuracion persistente y a prueba de archivos danados
- Main devuelve error y deja registro si no puede arrancar
- Lo mismo que hace el doble clic: arranca, atiende, un segundo lanzamiento no duplica y se apaga.

## Recorrido completo en navegador real
`tests/test_e2e.py` · 1 pruebas · 1 ejecuciones

- Licencia -> cuenta del dueño -> turno -> XSS -> venta -> cajero -> cierre con faltante -> corte.

## Pasos del recorrido en navegador (`tests/e2e/flujo.js`)

- OK 1 licencia: clave mala rechazada, clave buena activa y pasa a crear la cuenta
- OK 2 dueño: ve las 7 pestañas, abre turno con fondo $200
- OK 3 XSS: el nombre con HTML se muestra como texto y no se ejecuta
- OK 4 venta cobrada
- OK 5 cajero: clave mala rechazada, solo ve Venta/Caja/Fiado y cae en Caja por no tener turno
- OK 6 cajero: sin turno lo manda a Caja; cobra con turno; cierra con faltante y se lo dice
- OK 7 corte muestra el faltante de Luis; al desactivarlo su tablet vuelve al login
- OK 8 sin errores de JavaScript en ningun navegador
