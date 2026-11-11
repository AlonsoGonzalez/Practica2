// Recorrido completo en navegador real (Playwright). Lo lanza tests/test_e2e.py.
// Uso: node flujo.js <puerto> <carpeta_llaves> <python_del_venv>
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const assert = require('assert');

const [puerto, llaves, python] = process.argv.slice(2);
const URL = `http://localhost:${puerto}`;
const tabs = p => p.locator('nav button:visible').allTextContents();

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
  await pc.waitForFunction(() => document.querySelector('#msg-lic').textContent.includes('no es valida'));
  const inst = (await pc.textContent('#lic-instalacion')).trim();
  const clave = execSync(`${python} tools/licencias.py emitir --privada ${llaves}/privada.pem --tienda "Abarrotes Dona Mary" --instalacion ${inst}`).toString().trim();
  await pc.fill('#form-licencia textarea', clave); await pc.click('#form-licencia button');
  await pc.waitForSelector('#auth-overlay:not([hidden])');
  console.log('OK 1 licencia: clave mala rechazada, clave buena activa y pasa a crear la cuenta');

  // 2. Cuenta del dueño y apertura de turno
  await pc.fill('#form-auth [name=nombre]', 'Doña Mary'); await pc.fill('#form-auth [name=usuario]', 'mary');
  await pc.fill('#form-auth [name=password]', 'secreto1'); await pc.click('#auth-boton');
  await pc.waitForSelector('#caja.active');           // sin turno abierto la app lo lleva a Caja
  assert.deepStrictEqual(await tabs(pc), ['Venta', 'Inventario', 'Caja', 'Fiado', 'Pedido', 'Corte de caja', 'Usuarios']);
  await pc.fill('#form-abrir [name=fondo]', '200'); await pc.click('#form-abrir button');
  await pc.waitForSelector('#turno-abierto:not([hidden])');
  console.log('OK 2 dueño: ve las 7 pestañas, abre turno con fondo $200');

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
  await tab.fill('#form-auth [name=usuario]', 'luis'); await tab.fill('#form-auth [name=password]', 'mala'); await tab.click('#auth-boton');
  await tab.waitForFunction(() => document.querySelector('#msg-auth').textContent.length > 0);
  await tab.fill('#form-auth [name=password]', 'caja123'); await tab.click('#auth-boton');
  await tab.waitForSelector('#caja.active');
  assert.deepStrictEqual(await tabs(tab), ['Venta', 'Caja', 'Fiado']);
  console.log('OK 5 cajero: clave mala rechazada, solo ve Venta/Caja/Fiado y cae en Caja por no tener turno');

  // 6. Sin turno no cobra; con turno si; cierre con faltante
  await tab.click('[data-tab=venta]'); await tab.fill('#buscar', 'Sprite'); await tab.waitForTimeout(400);
  await tab.click('.prod'); await tab.click('#cobrar'); await tab.waitForSelector('#caja.active');
  await tab.fill('#form-abrir [name=fondo]', '100'); await tab.click('#form-abrir button');
  await tab.waitForSelector('#turno-abierto:not([hidden])');
  assert(!(await tab.textContent('#turno-kpis')).includes('esperado'), 'el cajero no debe ver el esperado');
  await tab.click('[data-tab=venta]'); await tab.click('#cobrar');
  await tab.waitForFunction(() => document.querySelector('#msg-venta').textContent.includes('registrada'));
  await tab.click('[data-tab=caja]'); await tab.fill('#form-cerrar [name=contado]', '100'); await tab.click('#form-cerrar button');
  await tab.waitForFunction(() => document.querySelector('#msg-caja').textContent.includes('Faltan'));
  console.log('OK 6 cajero: sin turno lo manda a Caja; cobra con turno; cierra con faltante y se lo dice');

  // 7. El dueño ve el faltante en el corte; luego desactiva al cajero
  await pc.click('[data-tab=corte]'); await pc.waitForTimeout(600);
  const filas = await pc.locator('#t-turnos-corte tbody tr').allTextContents();
  assert(filas.some(f => f.includes('Luis') && f.includes('Faltan')), filas.join('|'));
  await pc.click('[data-tab=usuarios]'); await pc.waitForTimeout(300);
  await pc.locator('tr', { hasText: 'luis' }).locator('[data-act]').click(); await pc.waitForTimeout(400);
  await tab.click('[data-tab=venta]'); await tab.fill('#buscar', 'Coca'); await tab.waitForSelector('#auth-overlay:not([hidden])');
  console.log('OK 7 corte muestra el faltante de Luis; al desactivarlo su tablet vuelve al login');

  assert.deepStrictEqual(errores.filter(e => !/Inicia sesion/.test(e)), [], 'errores de JavaScript');
  console.log('OK 8 sin errores de JavaScript en ningun navegador');
  await b.close();
})().catch(e => { console.error('FALLO:', e.message); process.exit(1); });
