# Pendientes y estado de los hallazgos de las pruebas en Windows

Origen: informe de la ronda de pruebas hecha en una PC con Windows (TODO del 11-nov). Estado de cada punto:

## Hecho (con prueba automática)
- **Desinstalar cierra el programa** antes de borrar (`taskkill` en el desinstalador). CI en Windows: abre el programa, desinstala y verifica proceso cerrado, puerto 5000 libre y datos conservados.
- **Respaldos**: al abrir, cada 4 h, al cerrar cada turno, al cerrar el sistema y a mano; nombre con hora y motivo; se conserva 24 h completas + el último de cada día por 30 días. (`tests/test_operacion.py`, `tests/test_arranque.py`)
- **Restaurar un respaldo desde la app** (pestaña *Respaldos*, solo dueño): valida el archivo, guarda copia previa y migra respaldos viejos.
- **Tablet**: el estado se muestra siempre en la ventanita; instalar o reinstalar la apaga (`--apagar-tablet`). CI verifica que reinstalar apaga `lan` y conserva datos.
- **Ticket y Cobrar en celular**: barra fija abajo con total y «Ver ticket y cobrar»; el ticket sube como hoja.
- **Sin scroll horizontal en celular**: las tablas se vuelven tarjetas; nombres largos se parten.
- **Etiquetas visibles** en todos los campos; **botones de al menos 44 px**; papelera con texto y nombre accesible; confirmar antes de borrar.
- **Mensajes de error** claros y con acentos; el límite de crédito dice cuánto debe, cuánto es la venta y cuánto le queda.
- Cuadros de **prompt/confirm del navegador** reemplazados por diálogos propios (abonar, envases, contraseñas, cerrar turno, borrar).
- **Salir** ya no deja ver menú ni datos detrás del inicio de sesión.
- **Aviso «turno cerrado»** en Venta y botón Cobrar deshabilitado sin turno.
- **Guía de primeros pasos** para el dueño; **estados vacíos** con mensaje; **teclado numérico** en campos numéricos; **favicon**.
- Texto de Usuarios corregido (ya no menciona un acceso directo que no existe); aclarado el texto de la licencia de prueba.
- Ventanita con tamaño fijo según su contenido (arreglo probable de la franja 136x40; **verificar en Windows**).

## Pendiente
- [M] **Regla de Firewall** para el perfil Privado: hoy solo se explica en la ventanita (marcar «Redes privadas»). Crearla desde el instalador requiere permisos de administrador.
- [M] **Firmar el instalador** (SmartScreen): requiere comprar un certificado de firma de código.
- [M] **Windows pregunta con qué app abrir el enlace**: depende de que la PC no tenga navegador predeterminado; no se reprodujo en CI.
- [M] **Pantalla «Activar licencia» que no desaparece sola**: no se pudo reproducir (en la prueba de navegador desaparece y pasa a crear la cuenta). Volver a probar en Windows.
- [M] Licencia **ligada al ID de instalación**: las licencias reales ya lo permiten (`--instalacion`); la de prueba no lo lleva a propósito.
- **Hacerlo más bonito** (sistema de diseño, íconos, modo oscuro, toasts): hecha solo una primera limpieza (encabezado más compacto, pestaña activa, tarjetas con existencias en color).
- **Pruebas pendientes**: celular real, licencia vencida/renovación, reinicio con inicio automático, restaurar respaldo (en la app), cierre de turno por cajero y turnos simultáneos, envases/casco y pedido, impresión de ticket (no existe aún).
