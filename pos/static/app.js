const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
// Cuando la sesion se cierra, api() ya muestra el login; evita el ruido de la promesa rechazada.
addEventListener("unhandledrejection", e => { if (/Inicia sesi[oó]n|Licencia|licencia/.test(e.reason?.message || "")) e.preventDefault(); });
const money = c => "$" + (c / 100).toFixed(2);
const esc = s => String(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const api = async (url, opts = {}) => {
  const r = await fetch(url, opts.body
    ? {method: opts.method || "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(opts.body)}
    : opts);
  const data = await r.json();
  if (r.status === 402) mostrarLicencia(data);
  if (r.status === 401 && data.estado === "sin_sesion") mostrarAuth();
  if (data.estado === "sin_turno") { refrescarTurno(); irATab("caja"); }
  if (!r.ok) throw new Error(data.error || "Ocurrió un error. Inténtalo de nuevo.");
  return data;
};
// la altura real del encabezado (una o dos filas) se usa para pegar encabezados de tablas y avisos debajo de el
new ResizeObserver(() => document.documentElement.style.setProperty("--alto-header", $("header").offsetHeight + "px")).observe($("header"));
const ico = n => `<svg class="ico"><use href="#i-${n}"/></svg>`;
function toast(texto, ok, html = false) {
  const t = document.createElement("div"), msg = document.createElement("span"), x = document.createElement("button");
  t.className = "toast " + (ok ? "ok" : "error");
  html ? msg.innerHTML = texto : msg.textContent = texto;
  x.textContent = "✕"; x.setAttribute("aria-label", "Cerrar aviso"); x.onclick = () => t.remove();
  t.append(msg, x); $("#toasts").append(t);
  setTimeout(() => t.remove(), ok ? 4000 : 7000);
}
// El texto queda en el elemento (lectores de pantalla y pruebas); lo que ve la persona es el aviso (toast).
const say = (el, text, ok) => {
  el.textContent = text; el.className = "msg " + (ok ? "ok" : "error");
  if (text && !el.closest("#form-auth, #form-licencia")) toast(text, ok);
};
// ---- Tema claro / oscuro ----
function aplicarTema(t) {
  document.documentElement.dataset.tema = t;
  try { localStorage.setItem("pos_tema", t); } catch (e) {}
  $("#tema use").setAttribute("href", t === "oscuro" ? "#i-sol" : "#i-luna");
}
$("#tema").onclick = () => aplicarTema(document.documentElement.dataset.tema === "oscuro" ? "claro" : "oscuro");
$("#tema use").setAttribute("href", document.documentElement.dataset.tema === "oscuro" ? "#i-sol" : "#i-luna");

// ---- Ventanas de dialogo propias (en lugar de prompt/confirm del navegador: se ven bien y se usan con el dedo) ----
function dialogo({titulo, texto = "", campos = [], boton = "Aceptar", peligro = false}) {
  return new Promise(resolver => {
    const d = $("#dlg"), f = $("#dlg-form");
    let valor = null;
    $("#dlg-titulo").textContent = titulo;
    $("#dlg-texto").textContent = texto;
    $("#dlg-campos").innerHTML = campos.map(c =>
      `<label class="campo"><span>${esc(c.etiqueta)}</span>
         <input name="${esc(c.nombre)}" type="${c.tipo || "text"}" ${c.step ? `step="${c.step}"` : ""}
           ${c.min !== undefined ? `min="${c.min}"` : ""} ${c.tipo === "number" ? 'inputmode="decimal"' : ""}
           autocomplete="${c.tipo === "password" ? "new-password" : "off"}" required></label>`).join("");
    const ok = $("#dlg-ok");
    ok.textContent = boton;
    ok.classList.toggle("peligro", peligro); ok.classList.toggle("primario", !peligro);
    f.onsubmit = e => { e.preventDefault(); valor = Object.fromEntries(new FormData(f)); d.close(); };
    $("#dlg-cancelar").onclick = () => d.close();
    d.onclose = () => resolver(valor);              // Escape o "Cancelar" -> null
    d.showModal();
    ($("input", d) || ok).focus();
  });
}
const confirmar = (titulo, texto, boton = "Confirmar", peligro = false) =>
  dialogo({titulo, texto, boton, peligro}).then(v => v !== null);

// ---- Tablas: etiquetas para el modo tarjeta del celular y mensaje cuando no hay datos ----
function prepararTablas() {
  $$("table:not(#carrito)").forEach(t => {
    const tb = t.tBodies[0]; if (!tb) return;
    const heads = $$("thead th", t).map(th => th.textContent.trim());
    const filas = [...tb.rows].filter(r => !r.classList.contains("vacio"));
    filas.forEach(tr => [...tr.cells].forEach((td, i) => {
      if (td.dataset.label !== (heads[i] ?? "")) td.dataset.label = heads[i] ?? "";
      if (/^[\$\d.,\s\/%—-]+$/.test(td.textContent.trim()) && td.textContent.trim()) td.classList.add("num");   // cifras y precios no se parten
    }));
    const vacio = tb.querySelector("tr.vacio");
    if (!filas.length && !vacio)
      tb.insertAdjacentHTML("beforeend", `<tr class="vacio"><td colspan="${heads.length || 1}" data-label=""><svg class="ilus"><use href="#i-vacio"/></svg>${esc(t.dataset.vacio || "Sin datos.")}</td></tr>`);
    else if (filas.length && vacio) vacio.remove();
  });
}
new MutationObserver(prepararTablas).observe($("main"), {childList: true, subtree: true});
prepararTablas();

let productos = [], carrito = {}, turnoAbierto = false;

function irATab(nombre) { $(`nav [data-tab=${nombre}]`).click(); }
$$("nav button").forEach(b => b.onclick = () => {
  $$("nav button, .tab").forEach(e => e.classList.remove("active"));
  b.classList.add("active"); $("#" + b.dataset.tab).classList.add("active");
  b.scrollIntoView?.({inline: "center", block: "nearest"});
  document.body.classList.remove("ticket-abierto");
  const t = b.dataset.tab;
  if (t === "inventario") cargarInventario();
  if (t === "corte") cargarCorte();
  if (t === "clientes") cargarClientes();
  if (t === "pedido") cargarPedido();
  if (t === "usuarios") cargarUsuarios();
  if (t === "caja") cargarCaja();
  if (t === "respaldos") cargarRespaldos();
  if (t === "venta") enfocarBuscador();
});

// ---- Estado del turno (sin turno abierto no se puede cobrar) ----
async function refrescarTurno() {
  const t = await fetch("/api/turno").then(r => r.json()).catch(() => null);
  if (!t || t.error) return null;
  turnoAbierto = t.abierto;
  $("#banner-turno").hidden = turnoAbierto;
  $("#paso-turno")?.classList.toggle("hecho", turnoAbierto);
  actualizarCobrar();
  return t;
}
$("#ir-a-caja").onclick = () => irATab("caja");
$$("[data-ir]").forEach(b => b.onclick = () => irATab(b.dataset.ir));
function mostrarGuia() {
  $("#primeros-pasos").hidden = document.body.dataset.rol !== "dueno" || localStorage.getItem("pos_guia_oculta") === "1";
}
$("#ocultar-pasos").onclick = () => { localStorage.setItem("pos_guia_oculta", "1"); mostrarGuia(); };

// ---- Venta ----
function iconoCategoria(c) {
  c = (c || "").toLowerCase();
  if (/refresc|agua|jugo|bebida/.test(c)) return "bebida";
  if (/botana|galleta|dulce/.test(c)) return "bolsa";
  if (/l[aá]cteo|leche/.test(c)) return "leche";
  if (/panader|pan\b/.test(c)) return "pan";
  return "paquete";
}
async function cargarCatalogo() {
  productos = await api("/api/productos?q=" + encodeURIComponent($("#buscar").value));
  $("#catalogo").innerHTML = productos.map(p => {
    const nivel = p.stock <= 0 ? "cero" : p.stock <= p.stock_minimo ? "bajo" : "ok";
    return `<button class="prod ${p.stock <= 0 ? "agotado" : ""}" data-id="${p.id}">
       <span class="cat">${ico(iconoCategoria(p.categoria))}${esc(p.categoria)}</span><span class="nom">${esc(p.nombre)}</span><b>${money(p.precio)}</b>
       <span class="st ${nivel}">${p.stock <= 0 ? "Agotado" : "Quedan " + p.stock}</span></button>`;
  }).join("") || `<p class="nota">No se encontraron productos.</p>`;
  $$(".prod").forEach(b => b.onclick = () => { agregar(productos.find(p => p.id === +b.dataset.id)); enfocarBuscador(); });
}
let tBuscar;
$("#buscar").oninput = () => { clearTimeout(tBuscar); tBuscar = setTimeout(cargarCatalogo, 180); };   // un lector escribe 13 digitos en milisegundos

// ---- Lector de codigos de barras ----
// Los lectores USB y Bluetooth se comportan como un teclado: escriben el codigo y terminan con Enter (algunos con Tab).
let audioCtx;
function pitido(ok) {   // confirmacion sonora: agudo corto = leido; grave largo = no se pudo
  if (localStorage.getItem("pos_sonido") === "0") return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.frequency.value = ok ? 1000 : 220; g.gain.value = 0.08; o.connect(g); g.connect(audioCtx.destination);
    o.start(); o.stop(audioCtx.currentTime + (ok ? 0.07 : 0.25));
  } catch (e) {}
}
function toastAccion(texto, etiqueta, accion) {
  const t = document.createElement("div"), msg = document.createElement("span"), b = document.createElement("button");
  t.className = "toast error"; msg.textContent = texto; b.textContent = etiqueta;
  b.onclick = () => { t.remove(); accion(); };
  t.append(msg, b); $("#toasts").append(t); setTimeout(() => t.remove(), 9000);
}
async function procesarCodigo(codigo) {
  let p = productos.find(x => x.codigo === codigo);
  if (!p) p = (await api("/api/productos?codigo=" + encodeURIComponent(codigo)).catch(() => []))[0];
  if (!p) {
    pitido(false);
    const aviso = `No encontré ningún producto con el código ${codigo}.`;
    if (document.body.dataset.rol === "dueno") {   // el dueño puede darlo de alta al momento (un solo aviso, con el boton)
      $("#msg-venta").textContent = aviso; $("#msg-venta").className = "msg error";
      toastAccion(aviso, "Agregar este producto", () => {
        irATab("inventario");
        $("#form-producto [name=codigo]").value = codigo; $("#form-producto [name=nombre]").focus();
      });
    } else say($("#msg-venta"), aviso, false);
    return;
  }
  if (p.stock <= 0) { pitido(false); return say($("#msg-venta"), `${p.nombre}: no hay existencias.`, false); }
  pitido(agregar(p));
}
$("#buscar").onkeydown = async e => {
  let valor = e.target.value.trim();
  // Si quedo texto de una busqueda anterior y despues se paso el lector, el codigo llega pegado al final: se rescata el codigo.
  const final = valor.match(/(\d{8,14})$/);
  if (final && final[1] !== valor) valor = final[1];
  const esCodigo = /^\d{6,}$/.test(valor);
  if (e.key !== "Enter" && !(e.key === "Tab" && esCodigo)) return;   // Tab solo si ya parece un codigo (algunos lectores terminan con Tab)
  if (!valor) return;
  e.preventDefault(); clearTimeout(tBuscar);
  const original = e.target.value;
  e.target.value = "";
  if (esCodigo || productos.some(x => x.codigo === valor)) await procesarCodigo(valor);
  else if (productos.length === 1 && productos[0].stock > 0) agregar(productos[0]);   // texto con un solo resultado: se agrega
  else {
    // codigos con letras (Code 128, etc.): se busca por codigo exacto antes de dejarlo como texto de busqueda
    const exacto = (await api("/api/productos?codigo=" + encodeURIComponent(valor)).catch(() => []))[0];
    if (exacto) await procesarCodigo(valor);
    else { e.target.value = original; return; }
  }
  cargarCatalogo();
};
// Si el cursor no esta en un campo (se toco un boton, se cerro un dialogo...), lo que escribe el lector va al buscador.
addEventListener("keydown", e => {
  if (!$("#venta").classList.contains("active") || document.body.classList.contains("sin-sesion")) return;
  if ($("#dlg").open || !$("#auth-overlay").hidden || !$("#licencia-overlay").hidden) return;
  if (e.ctrlKey || e.altKey || e.metaKey || e.key.length !== 1) return;
  if (e.target.matches?.("input, textarea, select, [contenteditable]")) return;
  $("#buscar").focus();
});
function enfocarBuscador() { if (!matchMedia("(pointer: coarse)").matches) $("#buscar").focus(); }   // en tablet/celular no abre el teclado en pantalla
$("#sonido").checked = localStorage.getItem("pos_sonido") !== "0";
$("#sonido").onchange = e => localStorage.setItem("pos_sonido", e.target.checked ? "1" : "0");

function agregar(p) {
  const id = p.id;
  if ((carrito[id]?.cantidad || 0) + 1 > p.stock) { say($("#msg-venta"), `No hay más existencias de ${p.nombre}.`, false); return false; }
  carrito[id] = {p, cantidad: (carrito[id]?.cantidad || 0) + 1, dev: carrito[id]?.dev || 0};
  say($("#msg-venta"), "", true); pintarCarrito();
  return true;
}
const cascoLinea = l => l.p.retornable ? (l.cantidad - l.dev) * l.p.casco : 0;
const cascoTotal = () => Object.values(carrito).reduce((s, l) => s + cascoLinea(l), 0);
function total() { return Object.values(carrito).reduce((s, l) => s + l.p.precio * l.cantidad + cascoLinea(l), 0); }
function actualizarCobrar() {
  const b = $("#cobrar"), vacio = !Object.keys(carrito).length;
  b.disabled = vacio || !turnoAbierto;
  b.title = !turnoAbierto ? "Abre tu turno de caja para poder cobrar" : vacio ? "Agrega productos al ticket" : "";
}
function pintarCarrito() {
  const lineas = Object.entries(carrito);
  $("#carrito tbody").innerHTML = lineas.map(([id, l]) =>
    `<tr><td>${esc(l.p.nombre)}${l.p.retornable ? `<br><label class="nota">Envases vacíos que entrega:
         <input class="dev" type="number" inputmode="numeric" min="0" max="${l.cantidad}" value="${l.dev}" data-dev="${id}"
           aria-label="Envases vacíos que entrega el cliente de ${esc(l.p.nombre)}"></label>` : ""}</td>
       <td><div class="cant"><button data-d="-1" data-id="${id}" aria-label="Quitar uno de ${esc(l.p.nombre)}">−</button>
         <b>${l.cantidad}</b><button data-d="1" data-id="${id}" aria-label="Agregar uno de ${esc(l.p.nombre)}">+</button></div></td>
       <td>${money(l.p.precio * l.cantidad + cascoLinea(l))}</td></tr>`).join("")
    || `<tr class="vacio"><td colspan="3" class="nota">El ticket está vacío. Toca un producto para agregarlo.</td></tr>`;
  $$("#carrito [data-d]").forEach(b => b.onclick = () => {
    const l = carrito[b.dataset.id], n = l.cantidad + +b.dataset.d;
    if (n > l.p.stock) return;
    if (n <= 0) delete carrito[b.dataset.id]; else { l.cantidad = n; l.dev = Math.min(l.dev, n); }
    pintarCarrito();
  });
  $$("[data-dev]").forEach(i => i.onchange = () => {
    const l = carrito[i.dataset.dev];
    l.dev = Math.max(0, Math.min(l.cantidad, parseInt(i.value) || 0)); setTimeout(pintarCarrito);
  });
  $("#total").textContent = money(total()); $("#casco").textContent = money(cascoTotal());
  $("#barra-total").textContent = money(total());
  $("#barra-n").textContent = lineas.reduce((s, [, l]) => s + l.cantidad, 0);
  cambio(); actualizarCobrar();
}
function cambio() {
  const r = parseFloat($("#recibido").value);
  $("#cambio").textContent = isNaN(r) ? "$0.00" : money(Math.max(0, Math.round(r * 100) - total()));
}
$("#recibido").oninput = cambio;
$("#metodo").onchange = async () => {
  const fiado = $("#metodo").value === "fiado";
  $("#lbl-cliente").hidden = !fiado; $("#lbl-recibido").hidden = fiado;
  if (fiado) {
    const cs = await api("/api/clientes");
    $("#cliente").innerHTML = cs.length
      ? cs.map(c => `<option value="${c.id}">${esc(c.nombre)} (debe ${money(c.saldo)})</option>`).join("")
      : `<option value="">Primero agrega un cliente en Fiado</option>`;
  }
};
let ultimaVenta = null;
async function imprimirTicket(id) {
  try {
    const [v, lic] = await Promise.all([api(`/api/ventas/${id}`), fetch("/api/licencia").then(r => r.json()).catch(() => ({}))]);
    const lineas = v.items.map(i => `<tr><td>${i.cantidad} x ${esc(i.nombre)}</td><td>${money(i.precio * i.cantidad)}</td></tr>`).join("");
    $("#ticket-impreso").innerHTML =
      `<h1>${esc(lic.tienda || "Punto de Venta")}</h1><div class="c">Ticket #${v.id}<br>${esc(v.fecha)}</div><div class="linea"></div>` +
      `<table>${lineas}${v.casco ? `<tr><td>Casco (depósito de envases)</td><td>${money(v.casco)}</td></tr>` : ""}</table><div class="linea"></div>` +
      `<table class="tot"><tr><td>TOTAL</td><td>${money(v.total)}</td></tr></table>` +
      (v.metodo === "fiado" ? `<div class="c">Venta a fiado</div>`
        : `<table><tr><td>Recibido</td><td>${money(v.recibido)}</td></tr><tr><td>Cambio</td><td>${money(v.cambio)}</td></tr></table>`) +
      `<div class="linea"></div><div class="c">¡Gracias por su compra!</div>`;
    window.print();
  } catch (e) { say($("#msg-venta"), "No se pudo preparar el ticket: " + e.message, false); }
}
$("#imprimir-ticket").onclick = () => ultimaVenta && imprimirTicket(ultimaVenta);
$("#auto-imprimir").checked = localStorage.getItem("pos_auto_imprimir") === "1";
$("#auto-imprimir").onchange = e => localStorage.setItem("pos_auto_imprimir", e.target.checked ? "1" : "0");
$("#vaciar").onclick = () => { carrito = {}; pintarCarrito(); };
$("#abrir-ticket").onclick = () => document.body.classList.add("ticket-abierto");
$("#cerrar-ticket").onclick = () => document.body.classList.remove("ticket-abierto");
$("#cobrar").onclick = async () => {
  const items = Object.entries(carrito).map(([id, l]) =>
    ({producto_id: +id, cantidad: l.cantidad, envases_devueltos: l.dev}));
  const body = {items, metodo: $("#metodo").value};
  if (body.metodo === "fiado") body.cliente_id = +$("#cliente").value;
  else if ($("#recibido").value) body.recibido = $("#recibido").value;
  try {
    const v = await api("/api/ventas", {body});
    say($("#msg-venta"), `Venta #${v.id} registrada. ` + (body.metodo === "fiado" ? "Cargada a fiado." : `Cambio: ${money(v.cambio)}`), true);
    ultimaVenta = v.id; $("#imprimir-ticket").hidden = false;
    if ($("#auto-imprimir").checked) imprimirTicket(v.id);
    carrito = {}; $("#recibido").value = ""; document.body.classList.remove("ticket-abierto");
    pintarCarrito(); cargarCatalogo(); enfocarBuscador();
  } catch (e) { say($("#msg-venta"), e.message, false); }
};

// ---- Inventario ----
async function cargarInventario() {
  const rows = await api("/api/productos");
  $("#tabla-inv tbody").innerHTML = rows.map(p =>
    `<tr><td>${esc(p.codigo)}</td><td>${esc(p.nombre)}</td><td>${esc(p.categoria)}</td>
     <td>${money(p.precio)}</td><td>${money(p.costo)}</td>
     <td class="${p.stock <= p.stock_minimo ? "bajo" : ""}">${p.stock}</td>
     <td>${p.retornable ? `<div class="acciones">${p.vacios} / ${p.en_calle}
         <button data-dev-env="${p.id}" data-nombre="${esc(p.nombre)}">Devolución</button>
         <button data-canje="${p.id}" data-nombre="${esc(p.nombre)}">Canje</button></div>` : "—"}</td>
     <td><div class="acciones"><input type="number" inputmode="numeric" step="1" style="width:90px" placeholder="±" data-aj="${p.id}"
           aria-label="Ajustar existencias de ${esc(p.nombre)} (positivo suma, negativo resta)">
         <button data-ok="${p.id}" aria-label="Aplicar ajuste a ${esc(p.nombre)}">Aplicar</button></div></td>
     <td><button class="peligro" data-del="${p.id}" data-nombre="${esc(p.nombre)}" aria-label="Eliminar ${esc(p.nombre)}">${ico("basura")} Eliminar</button></td></tr>`).join("");
  $$("[data-ok]").forEach(b => b.onclick = async () => {
    const cant = $(`[data-aj="${b.dataset.ok}"]`).value;
    try { await api(`/api/productos/${b.dataset.ok}/ajuste`, {body: {cantidad: cant}}); cargarInventario(); }
    catch (e) { say($("#msg-inv"), e.message, false); }
  });
  const envase = (attr, ruta, titulo, etiqueta, boton, texto) => $$(`[${attr}]`).forEach(b => b.onclick = async () => {
    const v = await dialogo({titulo, texto: `${b.dataset.nombre}. ${texto}`, boton,
      campos: [{nombre: "cantidad", etiqueta, tipo: "number", step: "1", min: 1}]});
    if (!v) return;
    try {
      const r = await api(`/api/productos/${b.getAttribute(attr)}/${ruta}`, {body: {cantidad: v.cantidad}});
      say($("#msg-inv"), r.reembolso !== undefined ? `Listo: reembolsa ${money(r.reembolso)} de casco.` : "Canje registrado.", true);
      cargarInventario();
    } catch (e) { say($("#msg-inv"), e.message, false); }
  });
  envase("data-dev-env", "devolucion", "Devolución de envases", "¿Cuántos envases vacíos regresa el cliente?", "Reembolsar casco",
    "El cliente regresa envases vacíos y se le devuelve su casco.");
  envase("data-canje", "canje-proveedor", "Canje con el proveedor", "¿Cuántos envases vacíos entregas al repartidor?", "Registrar canje",
    "Entregas envases vacíos al repartidor y recibes llenos.");
  $$("[data-del]").forEach(b => b.onclick = async () => {
    if (!await confirmar("Eliminar producto", `¿Eliminar «${b.dataset.nombre}»? Dejará de aparecer en el catálogo; su historial de ventas se conserva.`, "Eliminar", true)) return;
    try { await api(`/api/productos/${b.dataset.del}`, {method: "DELETE", body: {}}); cargarInventario(); }
    catch (e) { say($("#msg-inv"), e.message, false); }
  });
}
$("#form-producto [name=codigo]").onkeydown = e => {   // el lector termina con Enter: no debe enviar el formulario a medias
  if (e.key === "Enter") { e.preventDefault(); $("#form-producto [name=nombre]").focus(); }
};
$("#form-producto").onsubmit = async e => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  body.retornable = e.target.retornable.checked;
  if (!body.categoria) delete body.categoria;
  try { await api("/api/productos", {body}); e.target.reset(); say($("#msg-inv"), "Producto agregado.", true); cargarInventario(); }
  catch (err) { say($("#msg-inv"), err.message, false); }
};

// ---- Corte ----
async function cargarCorte() {
  const f = $("#fecha-corte").value || new Date().toLocaleDateString("sv");
  $("#fecha-corte").value = f;
  const c = await api("/api/corte?fecha=" + f);
  $("#k-n").textContent = c.num_ventas; $("#k-total").textContent = money(c.total);
  $("#k-util").textContent = money(c.utilidad); $("#k-prom").textContent = money(c.ticket_promedio);
  $("#k-fiado").textContent = money(c.fiado); $("#k-abonos").textContent = money(c.abonos);
  $("#k-casco").textContent = money(c.cascos_cobrados) + " / " + money(c.cascos_reembolsados);
  $("#k-caja").textContent = money(c.efectivo_en_caja);
  $("#t-usr-corte tbody").innerHTML = c.por_usuario.map(u =>
    `<tr><td>${esc(u.nombre)}</td><td>${u.ventas}</td><td>${money(u.total)}</td></tr>`).join("");
  $("#t-turnos-corte tbody").innerHTML = c.turnos.map(t =>
    `<tr><td>${esc(t.cajero)}</td><td>${money(t.fondo)}</td><td>${t.esperado === null ? "abierto" : money(t.esperado)}</td>
     <td>${t.contado === null ? "—" : money(t.contado)}</td><td>${difTexto(t.diferencia)}</td></tr>`).join("");
  const env = await api("/api/reportes/envases");
  $("#t-env tbody").innerHTML = env.map(e =>
    `<tr><td>${esc(e.nombre)}</td><td>${money(e.casco)}</td><td>${e.vacios}</td><td>${e.en_calle}</td><td>${money(e.casco_en_calle)}</td></tr>`).join("");
  $("#t-top tbody").innerHTML = c.top_productos.map(t =>
    `<tr><td>${esc(t.nombre)}</td><td>${t.unidades}</td><td>${money(t.importe)}</td></tr>`).join("");
  const bajo = await api("/api/reportes/stock-bajo");
  $("#t-bajo tbody").innerHTML = bajo.map(p =>
    `<tr><td>${esc(p.nombre)}</td><td class="bajo">${p.stock}</td><td>${p.stock_minimo}</td></tr>`).join("");
}
$("#fecha-corte").onchange = cargarCorte;

// ---- Fiado ----
async function cargarClientes() {
  const cs = await api("/api/clientes");
  $("#t-clientes tbody").innerHTML = cs.map(c =>
    `<tr><td>${esc(c.nombre)}</td><td>${esc(c.telefono)}</td><td>${c.limite ? money(c.limite) : "—"}</td>
     <td class="${c.saldo ? "bajo" : ""}">${money(c.saldo)}</td>
     <td>${c.saldo ? `<button data-abono="${c.id}" data-nombre="${esc(c.nombre)}" data-saldo="${c.saldo}">Abonar</button>` : ""}</td></tr>`).join("");
  $("#por-cobrar").textContent = money(cs.reduce((s, c) => s + c.saldo, 0));
  $$("[data-abono]").forEach(b => b.onclick = async () => {
    const v = await dialogo({titulo: "Registrar abono", boton: "Registrar abono",
      texto: `${b.dataset.nombre} debe ${money(+b.dataset.saldo)}.`,
      campos: [{nombre: "monto", etiqueta: "¿Cuánto abona? ($)", tipo: "number", step: "0.01", min: 0.01}]});
    if (!v) return;
    try { await api(`/api/clientes/${b.dataset.abono}/abono`, {body: {monto: v.monto}}); say($("#msg-cli"), "Abono registrado.", true); cargarClientes(); }
    catch (e) { say($("#msg-cli"), e.message, false); }
  });
}
$("#form-cliente").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("/api/clientes", {body: Object.fromEntries(new FormData(e.target))});
    e.target.reset(); say($("#msg-cli"), "Cliente agregado.", true); cargarClientes();
  } catch (err) { say($("#msg-cli"), err.message, false); }
};

// ---- Sugerencia de pedido ----
async function cargarPedido() {
  const d = await api(`/api/sugerencia-pedido?historial=${$("#p-hist").value}&cobertura=${$("#p-cob").value}`);
  $("#t-pedido tbody").innerHTML = d.items.map(i =>
    `<tr><td>${esc(i.nombre)}</td><td class="${i.dias_de_stock !== null && i.dias_de_stock < 2 ? "bajo" : ""}">${i.stock}</td>
     <td>${i.promedio_diario}</td><td>${i.dias_de_stock ?? "—"}</td><td><b>${i.pedir}</b></td><td>${money(i.costo_estimado)}</td></tr>`).join("");
  $("#p-total").textContent = money(d.total_estimado);
}
$("#p-calc").onclick = cargarPedido;

// ---- Licencia ----
async function mostrarLicencia(info) {
  // Se confirma con el servidor antes de mostrarla: una respuesta 402 atrasada no debe reabrirla despues de activar.
  const actual = await fetch("/api/licencia").then(r => r.json()).catch(() => info);
  if (actual.activa) return;
  info = actual.instalacion ? actual : info;
  $("#lic-mensaje").textContent = info.mensaje || info.error || "";
  $("#lic-instalacion").textContent = info.instalacion;
  $("#licencia-overlay").hidden = false;
}
async function revisarLicencia() {
  const info = await fetch("/api/licencia").then(r => r.json());
  if (!info.activa) return mostrarLicencia(info);
  $("#licencia-overlay").hidden = true;
  $("#lic-badge").textContent = info.estado === "desarrollo" ? "Modo desarrollo (sin licencia)"
    : `Licencia ${info.tipo} · ${info.tienda}`;
  iniciarSesion();
}
$("#form-licencia").onsubmit = async e => {
  e.preventDefault();
  const r = await fetch("/api/licencia", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({clave: e.target.clave.value})});
  const d = await r.json();
  if (!r.ok) return say($("#msg-lic"), d.error, false);
  e.target.reset(); say($("#msg-lic"), "", true);
  revisarLicencia();   // oculta esta pantalla por si sola y sigue con la cuenta del dueño
};

// ---- Caja (turnos) ----
function difTexto(d) {
  if (d === null || d === undefined) return "—";
  if (d === 0) return `<span class="cuadra">Cuadra</span>`;
  return d < 0 ? `<span class="falta">Faltan ${money(-d)}</span>` : `<span class="sobra">Sobran ${money(d)}</span>`;
}
async function cargarCaja() {
  const t = await api("/api/turno");
  turnoAbierto = t.abierto; $("#banner-turno").hidden = t.abierto; actualizarCobrar();
  $("#turno-cerrado").hidden = t.abierto; $("#turno-abierto").hidden = !t.abierto;
  if (t.abierto) {
    const r = t.turno.resumen, kpi = (n, v) => `<div><small>${n}</small><b>${v}</b></div>`;
    $("#turno-kpis").innerHTML = kpi("Abierto desde", esc(t.turno.abierto)) + kpi("Fondo inicial", money(r.fondo)) +
      kpi("Ventas del turno", r.num_ventas) +
      (r.esperado === undefined ? "" :  // el cajero no ve cuanto "deberia" haber (conteo ciego)
        kpi("Ventas en efectivo", money(r.ventas_efectivo)) + kpi("Fiado", money(r.ventas_fiado)) +
        kpi("Abonos", money(r.abonos)) + kpi("Retiros", money(r.retiros)) + kpi("Ingresos", money(r.ingresos)) +
        kpi("Efectivo esperado", money(r.esperado)));
  }
  if (document.body.dataset.rol === "dueno") {
    const ts = await api("/api/turnos");
    $("#t-turnos tbody").innerHTML = ts.slice(0, 30).map(x =>
      `<tr><td>${esc(x.cajero)}</td><td>${esc(x.abierto)}</td><td>${esc(x.cerrado || "abierto")}</td><td>${money(x.fondo)}</td>
       <td>${x.cerrado ? money(x.esperado) : money(x.resumen.esperado)}</td><td>${x.cerrado ? money(x.contado) : "—"}</td>
       <td>${difTexto(x.diferencia)}</td>
       <td>${x.cerrado ? "" : `<button data-cerrar-turno="${x.id}" data-cajero="${esc(x.cajero)}">Cerrar este turno</button>`}</td></tr>`).join("");
    $$("[data-cerrar-turno]").forEach(b => b.onclick = async () => {
      const v = await dialogo({titulo: "Cerrar el turno de " + b.dataset.cajero, boton: "Cerrar turno",
        texto: "Cuenta el efectivo que hay en esa caja y escríbelo.",
        campos: [{nombre: "contado", etiqueta: "Efectivo contado ($)", tipo: "number", step: "0.01", min: 0}]});
      if (!v) return;
      try { await api(`/api/turnos/${b.dataset.cerrarTurno}/cerrar`, {body: {contado: v.contado, notas: "Cerrado por el dueño"}}); cargarCaja(); }
      catch (e) { say($("#msg-caja"), e.message, false); }
    });
  }
}
$("#form-abrir").onsubmit = async e => {
  e.preventDefault();
  try { await api("/api/turno/abrir", {body: {fondo: e.target.fondo.value}}); e.target.reset(); say($("#msg-caja"), "Turno abierto. ¡Buenas ventas!", true); cargarCaja(); }
  catch (err) { say($("#msg-caja"), err.message, false); }
};
$("#form-mov").onsubmit = async e => {
  e.preventDefault();
  try { await api("/api/turno/movimiento", {body: Object.fromEntries(new FormData(e.target))}); e.target.reset(); say($("#msg-caja"), "Movimiento registrado.", true); cargarCaja(); }
  catch (err) { say($("#msg-caja"), err.message, false); }
};
$("#form-cerrar").onsubmit = async e => {
  e.preventDefault();
  if (!await confirmar("Cerrar turno", "Ya no podrás cobrar hasta abrir otro turno. ¿Cerrarlo?", "Cerrar turno")) return;
  try {
    const d = await api("/api/turno/cerrar", {body: Object.fromEntries(new FormData(e.target))});
    e.target.reset(); cargarCaja();
    const resumenCierre = `Turno cerrado. Esperado ${money(d.esperado)}, contado ${money(d.contado)}: ${difTexto(d.diferencia)}`;
    $("#msg-caja").className = "msg"; $("#msg-caja").innerHTML = resumenCierre;
    toast(resumenCierre, d.diferencia === 0, true);
  } catch (err) { say($("#msg-caja"), err.message, false); }
};

// ---- Respaldos ----
const MOTIVOS = {inicio: "Al abrir el sistema", auto: "Automático", "cierre-turno": "Al cerrar un turno", "al-cerrar": "Al cerrar el sistema",
  manual: "Manual", "antes-de-restaurar": "Antes de restaurar", antiguo: "De una versión anterior"};
async function cargarRespaldos() {
  const rs = await api("/api/respaldos");
  $("#t-respaldos tbody").innerHTML = rs.map(r =>
    `<tr><td>${esc(r.fecha)}</td><td>${esc(MOTIVOS[r.motivo] || r.motivo || "—")}</td><td>${(r.bytes / 1024).toFixed(0)} KB</td>
     <td><button data-restaurar="${esc(r.archivo)}" data-fecha="${esc(r.fecha)}">Restaurar</button></td></tr>`).join("");
  $$("[data-restaurar]").forEach(b => b.onclick = async () => {
    if (!await confirmar("Restaurar este respaldo",
        `Vas a reemplazar TODOS los datos actuales (ventas, productos, clientes, usuarios y turnos) por los que había el ${b.dataset.fecha}. ` +
        `Lo que hiciste después de esa fecha se perderá, aunque antes se guarda una copia de lo actual. ¿Continuar?`, "Sí, restaurar", true)) return;
    try {
      await api("/api/respaldos/restaurar", {body: {archivo: b.dataset.restaurar}});
      await dialogo({titulo: "Respaldo restaurado", texto: "Listo. Se volverá a cargar el sistema.", boton: "Aceptar"});
      location.reload();
    } catch (e) { say($("#msg-resp"), e.message, false); }
  });
}
$("#respaldar-ahora").onclick = async () => {
  try { await api("/api/respaldos", {body: {}}); say($("#msg-resp"), "Respaldo creado.", true); cargarRespaldos(); }
  catch (e) { say($("#msg-resp"), e.message, false); }
};

// ---- Sesion y usuarios ----
let modoAuth = "login";
function mostrarAuth(configurado) {
  const setup = configurado === false;
  modoAuth = setup ? "setup" : "login";
  document.body.classList.add("sin-sesion");
  $("#lbl-auth-nombre").hidden = !setup;
  $("#form-auth [name=nombre]").required = setup;
  $("#form-auth [name=password]").autocomplete = setup ? "new-password" : "current-password";
  $("#auth-titulo").textContent = setup ? "Bienvenido: crea la cuenta del dueño" : "Iniciar sesión";
  $("#auth-ayuda").textContent = setup ? "Será la cuenta con acceso total. Guarda bien la contraseña (mínimo 6 caracteres)." : "";
  $("#auth-boton").textContent = setup ? "Crear cuenta" : "Entrar";
  $("#auth-overlay").hidden = false;
}
function aplicarUsuario(u) {
  document.body.dataset.rol = u.rol;
  document.body.classList.remove("sin-sesion");
  $("#usuario-actual").textContent = `${u.nombre} (${u.rol === "dueno" ? "dueño" : "cajero"})`;
  $("#auth-overlay").hidden = true;
  $$("nav button, .tab").forEach(e => e.classList.remove("active"));
  $('nav [data-tab=venta]').classList.add("active"); $("#venta").classList.add("active");
  carrito = {}; pintarCarrito(); cargarCatalogo(); mostrarGuia();
  refrescarTurno().then(t => { if (t && !t.abierto) irATab("caja"); });
}
async function iniciarSesion() {
  const yo = await fetch("/api/auth/yo").then(r => r.json());
  if (yo.usuario) return aplicarUsuario(yo.usuario);
  mostrarAuth(yo.configurado);
}
$("#form-auth").onsubmit = async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const r = await fetch(modoAuth === "setup" ? "/api/auth/configurar" : "/api/auth/login",
    {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(f)});
  const d = await r.json();
  if (!r.ok) return say($("#msg-auth"), d.error, false);
  e.target.reset(); say($("#msg-auth"), "", true); aplicarUsuario(d.usuario);
};
$("#btn-salir").onclick = async () => { await fetch("/api/auth/logout", {method: "POST"}); location.reload(); };
$("#btn-password").onclick = async () => {
  const v = await dialogo({titulo: "Cambiar mi contraseña", boton: "Cambiar contraseña", campos: [
    {nombre: "actual", etiqueta: "Contraseña actual", tipo: "password"},
    {nombre: "nueva", etiqueta: "Contraseña nueva (mínimo 6 caracteres)", tipo: "password"}]});
  if (!v) return;
  try { await api("/api/auth/password", {body: v}); await dialogo({titulo: "Listo", texto: "Tu contraseña se actualizó.", boton: "Aceptar"}); }
  catch (e) { await dialogo({titulo: "No se pudo cambiar", texto: e.message, boton: "Aceptar"}); }
};
async function cargarUsuarios() {
  const us = await api("/api/usuarios");
  $("#t-usuarios tbody").innerHTML = us.map(u =>
    `<tr><td>${esc(u.nombre)}</td><td>${esc(u.usuario)}</td><td>${u.rol === "dueno" ? "Dueño" : "Cajero"}</td>
     <td>${u.activo ? "Activo" : "<span class='bajo'>Desactivado</span>"}</td>
     <td><button data-pw="${u.id}" data-nombre="${esc(u.nombre)}">Nueva contraseña</button>
         <button data-act="${u.id}" data-val="${u.activo ? 0 : 1}">${u.activo ? "Desactivar" : "Activar"}</button></td></tr>`).join("");
  const editar = async (id, body) => {
    try { await api(`/api/usuarios/${id}`, {method: "PUT", body}); cargarUsuarios(); }
    catch (e) { say($("#msg-usr"), e.message, false); }
  };
  $$("[data-pw]").forEach(b => b.onclick = async () => {
    const v = await dialogo({titulo: "Nueva contraseña para " + b.dataset.nombre, boton: "Guardar contraseña",
      texto: "Si esa persona tiene una sesión abierta, se cerrará.",
      campos: [{nombre: "password", etiqueta: "Contraseña nueva (mínimo 6 caracteres)", tipo: "password"}]});
    if (v) editar(b.dataset.pw, {password: v.password});
  });
  $$("[data-act]").forEach(b => b.onclick = () => editar(b.dataset.act, {activo: b.dataset.val === "1"}));
  const red = await api("/api/red");
  $("#acceso-red").innerHTML = red.urls.length
    ? `<p class="aviso">⚠ <b>El acceso desde tablet o celular está ACTIVADO.</b> Cualquier dispositivo de tu red Wi-Fi puede abrir
       la pantalla de inicio de sesión. Usa una red privada con contraseña.</p>
       <p>Abre una de estas direcciones en el navegador de la tablet (mismo Wi-Fi):</p>` +
      red.urls.map(u => `<div class="url">${esc(u)}</div>`).join("")
    : `<p>El acceso desde otros dispositivos está <b>apagado</b>. Para activarlo, abre la ventanita del programa en la computadora
       y marca <b>«Permitir usar el sistema desde una tablet o celular»</b>.</p>`;
}
$("#form-usuario").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("/api/usuarios", {body: Object.fromEntries(new FormData(e.target))});
    e.target.reset(); say($("#msg-usr"), "Usuario agregado.", true); cargarUsuarios();
  } catch (err) { say($("#msg-usr"), err.message, false); }
};

revisarLicencia();
