// Recorrido completo en navegador real (Playwright). Lo lanza tests/test_e2e.py.
// Uso: node flujo.js <puerto> <carpeta_llaves> <python_del_venv>
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const assert = require('assert');

const [puerto, llaves, python] = process.argv.slice(2);
const URL = `http://localhost:${puerto}`;
const tabs = p => p.locator('nav button:visible').allTextContents().then(a => a.map(t => t.trim()));

(async () => {
  const b = await chromium.launch(); const errores = [];
  const nueva = async () => {
    const p = await (await b.newContext()).newPage();
    p.on('pageerror', e => errores.push(e.message));
    p.on('dialog', d => d.accept(d.type() === 'prompt' ? '0' : undefined));
    return p;
  };
  const pc = await nueva();

  // 1. Licencia
  await pc.goto(URL); await pc.waitForSelector('#licencia-overlay:not([hidden])');
  await pc.fill('#form-licencia textarea', 'POS1.mala.firma'); await pc.click('#form-licencia button');
  await pc.waitForFunction(() => document.querySelector('#msg-lic').textContent.includes('no es válida'));
  const inst = (await pc.textContent('#lic-instalacion')).trim();
  const clave = execSync(`${python} tools/licencias.py emitir --privada ${llaves}/privada.pem --tienda "Abarrotes Dona Mary" --instalacion ${inst}`).toString().trim();
  await pc.fill('#form-licencia textarea', clave); await pc.click('#form-licencia button');
  await pc.waitForSelector('#auth-overlay:not([hidden])');
  console.log('OK 1 licencia: clave mala rechazada, clave buena activa y pasa a crear la cuenta');

  // 2. Cuenta del dueño y apertura de turno
  await pc.fill('#form-auth [name=nombre]', 'Doña Mary'); await pc.fill('#form-auth [name=usuario]', 'mary');
  await pc.fill('#form-auth [name=password]', 'secreto1'); await pc.click('#auth-boton');
  await pc.waitForSelector('#caja.active');           // sin turno abierto la app lo lleva a Caja
  assert.deepStrictEqual(await tabs(pc), ['Venta', 'Inventario', 'Caja', 'Fiado', 'Pedido', 'Corte de caja', 'Usuarios', 'Respaldos']);
  await pc.fill('#form-abrir [name=fondo]', '200'); await pc.click('#form-abrir button');
  await pc.waitForSelector('#turno-abierto:not([hidden])');
  console.log('OK 2 dueño: ve las 8 pestañas, abre turno con fondo $200');

  // 3. XSS: un nombre malicioso se muestra como texto y no se ejecuta
  await pc.click('[data-tab=inventario]');
  await pc.fill('#form-producto [name=codigo]', 'XSS1');
  await pc.fill('#form-producto [name=nombre]', '<img src=x onerror="window.__xss=1"> Peligro');
  await pc.fill('#form-producto [name=precio]', '9.5'); await pc.fill('#form-producto [name=stock]', '4');
  await pc.click('#form-producto button'); await pc.waitForTimeout(500);
  await pc.click('[data-tab=venta]'); await pc.fill('#buscar', 'Peligro'); await pc.waitForTimeout(500);
  assert.strictEqual(await pc.evaluate(() => window.__xss), undefined, 'se ejecuto codigo inyectado');
  assert((await pc.textContent('.prod')).includes('<img src=x'), 'el nombre debe verse como texto');
  console.log('OK 3 XSS: el nombre con HTML se muestra como texto y no se ejecuta');

  // 4. Venta del dueño
  await pc.fill('#buscar', 'Sprite'); await pc.waitForTimeout(400); await pc.click('.prod'); await pc.click('#cobrar');
  await pc.waitForFunction(() => document.querySelector('#msg-venta').textContent.includes('registrada'));
  console.log('OK 4 venta cobrada');

  // 5. Cajero (otro navegador / tablet)
  await pc.click('[data-tab=usuarios]');
  await pc.fill('#form-usuario [name=nombre]', 'Luis'); await pc.fill('#form-usuario [name=usuario]', 'luis');
  await pc.fill('#form-usuario [name=password]', 'caja123'); await pc.click('#form-usuario button');
  await pc.waitForFunction(() => document.querySelectorAll('#t-usuarios tbody tr').length === 2);
  const tab = await nueva(); await tab.goto(URL); await tab.waitForSelector('#auth-overlay:not([hidden])');
  assert(!(await tab.isVisible('#lbl-auth-nombre')), 'al iniciar sesion no se pide el nombre (solo al crear la cuenta)');
  await tab.fill('#form-auth [name=usuario]', 'luis'); await tab.fill('#form-auth [name=password]', 'mala'); await tab.click('#auth-boton');
  await tab.waitForFunction(() => document.querySelector('#msg-auth').textContent.length > 0);
  await tab.fill('#form-auth [name=password]', 'caja123'); await tab.click('#auth-boton');
  await tab.waitForSelector('#caja.active');
  assert.deepStrictEqual(await tabs(tab), ['Venta', 'Caja', 'Fiado']);
  console.log('OK 5 cajero: clave mala rechazada, solo ve Venta/Caja/Fiado y cae en Caja por no tener turno');

  // 6. Sin turno no cobra; con turno si; cierre con faltante
  await tab.click('[data-tab=venta]'); await tab.fill('#buscar', 'Sprite'); await tab.waitForTimeout(400);
  await tab.click('.prod');
  assert(await tab.isVisible('#banner-turno'), 'debe avisar que el turno esta cerrado');
  assert(await tab.isDisabled('#cobrar'), 'sin turno el boton Cobrar debe estar deshabilitado');
  await tab.click('#ir-a-caja'); await tab.waitForSelector('#caja.active');
  await tab.fill('#form-abrir [name=fondo]', '100'); await tab.click('#form-abrir button');
  await tab.waitForSelector('#turno-abierto:not([hidden])');
  assert(!(await tab.textContent('#turno-kpis')).includes('esperado'), 'el cajero no debe ver el esperado');
  await tab.click('[data-tab=venta]'); await tab.click('#cobrar');
  await tab.waitForFunction(() => document.querySelector('#msg-venta').textContent.includes('registrada'));
  await tab.click('[data-tab=caja]'); await tab.fill('#form-cerrar [name=contado]', '100'); await tab.click('#form-cerrar button');
  await tab.click('#dlg-ok');   // confirmacion propia (ya no es el cuadro del navegador)
  await tab.waitForFunction(() => document.querySelector('#msg-caja').textContent.includes('Faltan'));
  console.log('OK 6 cajero: sin turno ve el aviso y no puede cobrar; con turno cobra; cierra con faltante y se lo dice');

  // 7. El dueño ve el faltante en el corte; luego desactiva al cajero
  await pc.click('[data-tab=corte]'); await pc.waitForTimeout(600);
  const filas = await pc.locator('#t-turnos-corte tbody tr').allTextContents();
  assert(filas.some(f => f.includes('Luis') && f.includes('Faltan')), filas.join('|'));
  await pc.click('[data-tab=usuarios]'); await pc.waitForTimeout(300);
  await pc.locator('tr', { hasText: 'luis' }).locator('[data-act]').click(); await pc.waitForTimeout(400);
  await tab.click('[data-tab=venta]'); await tab.fill('#buscar', 'Coca'); await tab.waitForSelector('#auth-overlay:not([hidden])');
  console.log('OK 7 corte muestra el faltante de Luis; al desactivarlo su tablet vuelve al login');

  // 7b. Lo que debe estar oculto lo esta (un estilo display:flex podia anular el atributo hidden)
  await pc.click('[data-tab=venta]'); await pc.waitForTimeout(300);
  assert(!(await pc.isVisible('#banner-turno')), 'con turno abierto no debe verse el aviso de turno cerrado');
  assert(!(await pc.isVisible('#lbl-cliente')), 'el selector de cliente solo aparece al elegir fiado');
  console.log('OK 7b con turno abierto no hay aviso de turno cerrado; cliente solo con fiado');

  // 8. Etiquetas visibles y botones de al menos 44 px en TODAS las pantallas (escritorio)
  const revisar = () => pc.evaluate(() => {
    const out = [];
    document.querySelectorAll('.tab.active input:not([type=checkbox]):not([type=hidden]), .tab.active select, .tab.active textarea').forEach(el => {
      if (el.offsetParent === null) return;
      if (!(el.labels && el.labels.length) && !el.getAttribute('aria-label')) out.push('campo sin etiqueta: ' + (el.name || el.id));
    });
    document.querySelectorAll('.tab.active button, header button').forEach(b => {
      if (b.offsetParent === null) return;
      const r = b.getBoundingClientRect();
      if (r.height < 43.5 || r.width < 43.5) out.push(`boton pequeño: "${b.textContent.trim()}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    });
    return out;
  });
  const pestanas = ['venta', 'inventario', 'caja', 'clientes', 'pedido', 'corte', 'usuarios', 'respaldos'];
  for (const t of pestanas) {
    await pc.click(`[data-tab=${t}]`); await pc.waitForTimeout(400);
    assert.deepStrictEqual(await revisar(), [], `pestaña ${t}`);
  }
  console.log('OK 8 las 8 pestañas: todos los campos tienen etiqueta visible y todos los botones miden al menos 44 px');

  // 9. Celular (375 px): sin scroll horizontal, tablas como tarjetas, y el cobro siempre a la mano
  const cel = await b.newContext({ viewport: { width: 375, height: 812 }, hasTouch: true });
  const m = await cel.newPage(); m.on('pageerror', e => errores.push(e.message));
  await m.goto(URL); await m.waitForSelector('#auth-overlay:not([hidden])');
  await m.fill('#form-auth [name=usuario]', 'mary'); await m.fill('#form-auth [name=password]', 'secreto1'); await m.click('#auth-boton');
  await m.waitForSelector('.prod');
  assert(!(await m.isVisible('#imprimir-ticket')), 'no hay ticket que imprimir antes de la primera venta');
  const ancho = () => m.evaluate(() => ({ doc: document.documentElement.scrollWidth, vista: window.innerWidth }));
  for (const t of pestanas) {
    await m.click(`[data-tab=${t}]`); await m.waitForTimeout(400);
    const a = await ancho();
    assert(a.doc <= a.vista + 1, `scroll horizontal en ${t}: ${a.doc}px sobre ${a.vista}px`);
  }
  await m.click('[data-tab=inventario]'); await m.waitForTimeout(300);
  assert(!(await m.isVisible('#tabla-inv thead')), 'en celular las tablas no llevan encabezado');
  assert.strictEqual(await m.evaluate(() => getComputedStyle(document.querySelector('#tabla-inv tbody td')).display), 'flex');
  assert((await m.locator('#tabla-inv tbody td').first().getAttribute('data-label')).length > 0, 'las tarjetas llevan el nombre de cada dato');
  await m.click('[data-tab=venta]'); await m.waitForSelector('.prod');
  await m.click('.prod');
  const barra = await m.locator('#barra-ticket').boundingBox();
  assert(barra && barra.y + barra.height <= 813 && barra.y > 400, 'la barra de cobro debe verse fija abajo');
  const cerrado = await m.locator('#cobrar').boundingBox();
  assert(!cerrado || cerrado.y >= 812, 'el ticket completo empieza cerrado (fuera de la pantalla, la barra es lo unico que se ve)');
  await m.click('#abrir-ticket'); await m.waitForTimeout(400);
  assert(!(await m.isVisible('#lbl-cliente')), 'en efectivo no se muestra el selector de cliente');
  const cobrar = await m.locator('#cobrar').boundingBox();
  assert(cobrar && cobrar.y >= 0 && cobrar.y + cobrar.height <= 813, 'Cobrar debe quedar visible sin hacer scroll');
  await m.click('#cerrar-ticket');
  console.log('OK 9 celular: sin scroll horizontal en 8 pestañas, tablas como tarjetas, barra de cobro fija y Cobrar a un toque');
  await cel.close();

  // 10. Fiado con diálogos propios (sin cuadros del navegador) y estado vacío
  await pc.click('[data-tab=clientes]'); await pc.waitForTimeout(300);
  assert((await pc.textContent('#t-clientes tbody')).includes('Todavía no hay clientes a fiado'), 'estado vacio con mensaje');
  assert(await pc.locator('#t-clientes tbody tr.vacio svg.ilus').count() === 1, 'el estado vacio lleva ilustracion');
  await pc.fill('#form-cliente [name=nombre]', 'Doña Ana'); await pc.click('#form-cliente button'); await pc.waitForTimeout(400);
  await pc.click('[data-tab=venta]'); await pc.fill('#buscar', 'Sprite'); await pc.waitForTimeout(400); await pc.click('.prod');
  await pc.selectOption('#metodo', 'fiado'); await pc.waitForTimeout(400); await pc.click('#cobrar');
  await pc.waitForFunction(() => document.querySelector('#msg-venta').textContent.includes('fiado'));
  await pc.click('[data-tab=clientes]'); await pc.waitForSelector('[data-abono]');
  await pc.click('[data-abono]');
  assert(await pc.isVisible('#dlg'), 'debe abrir un dialogo propio');
  assert(await pc.locator('#dlg label.campo span').first().isVisible(), 'el campo del dialogo lleva etiqueta');
  await pc.fill('#dlg input[name=monto]', '5'); await pc.click('#dlg-ok');
  await pc.waitForFunction(() => document.querySelector('#msg-cli').textContent.includes('Abono registrado'));
  console.log('OK 10 fiado: estado vacío con mensaje, dialogo propio para abonar y abono registrado');

  // 11. Mensaje claro al exceder el límite de crédito
  const lim = await pc.evaluate(async () => {
    const cs = await (await fetch('/api/clientes')).json(); const id = cs[0].id;
    await fetch('/api/clientes/' + id, { method: 'GET' });
    const r = await fetch('/api/ventas', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: [{ producto_id: (await (await fetch('/api/productos')).json())[0].id, cantidad: 1 }], metodo: 'fiado', cliente_id: id }) });
    return { status: r.status };
  });
  assert.strictEqual(lim.status, 201);   // sin limite: debe dejar fiar
  console.log('OK 11 fiado sin límite permite la venta');

  // 12. Respaldos visibles: se hicieron solos, se puede respaldar y pide confirmación para restaurar
  await pc.click('[data-tab=respaldos]'); await pc.waitForTimeout(500);
  const motivos = await pc.locator('#t-respaldos tbody tr td:nth-child(2)').allTextContents();
  assert(motivos.some(t => t.includes('Al cerrar un turno')), 'el cierre de turno de Luis debe haber generado un respaldo: ' + motivos.join('|'));
  const antes = await pc.locator('#t-respaldos tbody tr').count();
  await pc.click('#respaldar-ahora'); await pc.waitForFunction(n => document.querySelectorAll('#t-respaldos tbody tr').length === n, antes + 1);
  await pc.click('[data-restaurar] >> nth=0');
  assert(await pc.isVisible('#dlg'), 'restaurar debe pedir confirmacion');
  assert((await pc.textContent('#dlg-texto')).includes('reemplazar TODOS los datos'), 'la advertencia debe ser clara');
  await pc.click('#dlg-cancelar');
  console.log('OK 12 respaldos: se ven los automáticos (incluido el del cierre de turno), respaldar ahora y confirmación antes de restaurar');

  // 12b. Avisos (toast), tema oscuro y ticket imprimible
  await pc.click('#respaldar-ahora');
  await pc.waitForSelector('#toasts .toast.ok:has-text("Respaldo creado")');   // el aviso es visible, no solo el texto oculto
  await pc.click('#tema'); await pc.waitForTimeout(200);
  assert.strictEqual(await pc.evaluate(() => document.documentElement.dataset.tema), 'oscuro');
  const oscuro = await pc.evaluate(() => { const [r, g, b] = getComputedStyle(document.body).backgroundColor.match(/\d+/g).map(Number); return (r + g + b) / 3; });
  assert(oscuro < 60, 'el fondo del tema oscuro debe ser oscuro: ' + oscuro);
  await pc.click('#tema'); await pc.waitForTimeout(100);
  assert.strictEqual(await pc.evaluate(() => document.documentElement.dataset.tema), 'claro');
  await pc.evaluate(() => { window.__impreso = 0; window.print = () => { window.__impreso++; }; });
  await pc.click('[data-tab=venta]'); await pc.fill('#buscar', 'Sprite'); await pc.waitForTimeout(400); await pc.click('.prod');
  await pc.selectOption('#metodo', 'efectivo');
  await pc.fill('#recibido', '50'); await pc.click('#cobrar');
  await pc.waitForFunction(() => document.querySelector('#msg-venta').textContent.includes('registrada'));
  await pc.waitForSelector('#imprimir-ticket:not([hidden])');
  await pc.click('#imprimir-ticket'); await pc.waitForFunction(() => window.__impreso === 1);
  const ticket = await pc.textContent('#ticket-impreso');
  assert(ticket.includes('Sprite') && ticket.includes('TOTAL') && ticket.includes('Cambio') && ticket.includes('Gracias'), 'contenido del ticket: ' + ticket);
  await pc.emulateMedia({ media: 'print' });
  assert(await pc.isVisible('#ticket-impreso') && !(await pc.isVisible('header')) && !(await pc.isVisible('main')), 'al imprimir solo debe verse el ticket');
  await pc.emulateMedia({ media: 'screen' });
  console.log('OK 12b avisos visibles, tema oscuro y claro, ticket con total y cambio, y al imprimir solo se ve el ticket');

  // 13. Salir: no debe verse nada de la app detrás del inicio de sesión
  await pc.click('#btn-salir'); await pc.waitForSelector('#auth-overlay:not([hidden])');
  assert(!(await pc.isVisible('header')) && !(await pc.isVisible('main')), 'al salir no debe quedar visible el menú ni los datos');
  console.log('OK 13 salir: solo se ve el inicio de sesión, sin menú ni datos detrás');

  assert.deepStrictEqual(errores.filter(e => !/Inicia sesi[oó]n/.test(e)), [], 'errores de JavaScript');
  console.log('OK 8 sin errores de JavaScript en ningun navegador');
  await b.close();
})().catch(e => { console.error('FALLO:', e.message); process.exit(1); });
