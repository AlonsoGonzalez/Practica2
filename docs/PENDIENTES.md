# Pendientes y estado de los hallazgos de las pruebas en Windows

Origen: informe de la ronda de pruebas hecha en una PC con Windows (TODO del 11-nov). Estado de cada punto:

## Hecho (con prueba automática)
**Instalador y sistema**
- **Desinstalar cierra el programa** antes de borrar. CI en Windows: abre el programa, desinstala y verifica proceso cerrado, puerto 5000 libre y datos conservados. ✅ verificado en Windows
- **Respaldos**: al abrir, cada 4 h, al cerrar cada turno, al cerrar el sistema y a mano; rotación 24 h + último de cada día por 30 días. ✅ el cierre de turno genera su respaldo (verificado en Windows)
- **Restaurar un respaldo desde la app** (pestaña *Respaldos*, solo dueño): valida el archivo, guarda copia previa, migra respaldos viejos.
- **Tablet**: el estado se muestra siempre en la ventanita; instalar o reinstalar la apaga. ✅ verificado en Windows
- **Firewall**: regla para redes **privadas y de dominio** (nunca públicas), creada desde la ventanita al activar la tablet (Windows pide permiso de administrador). CI la crea y verifica el perfil Privado.
- **Enlace http**: si Windows no tiene navegador predeterminado, se abre en Microsoft Edge en lugar de preguntar con qué app abrirlo.
- **Pantalla «Activar licencia»**: se confirma con el servidor antes de mostrarla, así una respuesta atrasada ya no puede reabrirla tras activar.
- Autoconexión TCP en Windows (un puerto cerrado que "se conecta consigo mismo") ya no se toma por la app. ✅ detectado en Windows.
- Texto de Usuarios corregido; texto de la licencia de prueba aclarado; ventanita con tamaño fijo según su contenido (arreglo probable de la franja 136x40).

**Experiencia de uso**
- Venta en celular: barra fija con total + «Ver ticket y cobrar»; el ticket sube como hoja.
- Sin scroll horizontal en celular (tablas como tarjetas); etiquetas visibles; botones ≥ 44 px; diálogos propios; aviso de turno cerrado; guía de primeros pasos; estados vacíos con ilustración; mensajes de error claros; teclado numérico; favicon; salir sin dejar ver la app.
- **Ticket imprimible** (papel térmico de 80 mm) con opción de imprimir al cobrar.

**Más bonito**
- Sistema de diseño (rojo solo como acento, escala de espacios y tipografía, sombras suaves), encabezado compacto con pestaña activa, **íconos reales**, tarjetas de producto con ícono por categoría y existencias en color, total grande, **avisos (toasts)**, tablas con filas alternas y acciones agrupadas, **modo oscuro**, logo propio.

## Pendiente
- **Firmar el instalador** (SmartScreen): requiere comprar un certificado de firma de código.
- **Licencia ligada al ID de instalación**: las licencias reales ya lo permiten (`--instalacion`); la de prueba no lo lleva a propósito.
- **Probar en dispositivos reales**: celular real, impresora térmica real (el ticket se probó con emulación de impresión), reinicio con inicio automático, licencia vencida/renovación a los 30 días.
- **Ver la ventanita en Windows** (solo se verificó que arranca y responde, no cómo se ve).
- Herramienta de escritorio para el vendedor (emitir licencias sin terminal).
- Recargas y pago de servicios (necesita un proveedor/agregador con contrato).
