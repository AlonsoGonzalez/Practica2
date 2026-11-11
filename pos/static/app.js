const $ = (s, r = document) => r.querySelector(s);
// Cuando la sesion se cierra, api() ya muestra el login; evita el ruido de la promesa rechazada.
addEventListener("unhandledrejection", e => { if (/Inicia sesion|Licencia|licencia/.test(e.reason?.message || "")) e.preventDefault(); });
const money = c => "$" + (c / 100).toFixed(2);
const esc = s => String(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const api = async (url, opts = {}) => {
  const r = await fetch(url, opts.body
    ? {method: opts.method || "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(opts.body)}
    : opts);
  const data = await r.json();
  if (r.status === 402) mostrarLicencia(data);
  if (r.status === 401 && data.estado === "sin_sesion") mostrarAuth();
  if (!r.ok) throw new Error(data.error || "Error");
  return data;
};
const say = (el, text, ok) => { el.textContent = text; el.className = "msg " + (ok ? "ok" : "error"); };

let productos = [], carrito = {};

document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button, .tab").forEach(e => e.classList.remove("active"));
  b.classList.add("active"); $("#" + b.dataset.tab).classList.add("active");
  if (b.dataset.tab === "inventario") cargarInventario();
  if (b.dataset.tab === "corte") cargarCorte();
  if (b.dataset.tab === "clientes") cargarClientes();
  if (b.dataset.tab === "pedido") cargarPedido();
  if (b.dataset.tab === "usuarios") cargarUsuarios();
});

// ---- Venta ----
async function cargarCatalogo() {
  productos = await api("/api/productos?q=" + encodeURIComponent($("#buscar").value));
  $("#catalogo").innerHTML = productos.map(p =>
    `<button class="prod ${p.stock <= 0 ? "agotado" : ""}" data-id="${p.id}">
       <small>${esc(p.categoria)}</small><br>${esc(p.nombre)}<b>${money(p.precio)}</b><small>Stock: ${p.stock}</small></button>`).join("");
  document.querySelectorAll(".prod").forEach(b => b.onclick = () => agregar(+b.dataset.id));
}
$("#buscar").oninput = cargarCatalogo;
$("#buscar").onkeydown = e => {  // Enter con código exacto (lector de barras)
  if (e.key !== "Enter") return;
  const p = productos.find(p => p.codigo === e.target.value.trim()) || (productos.length === 1 && productos[0]);
  if (p && p.stock > 0) { agregar(p.id); e.target.value = ""; cargarCatalogo(); }
};
function agregar(id) {
  const p = productos.find(p => p.id === id);
  if ((carrito[id]?.cantidad || 0) + 1 > p.stock) return say($("#msg-venta"), "Sin stock suficiente", false);
  carrito[id] = {p, cantidad: (carrito[id]?.cantidad || 0) + 1, dev: carrito[id]?.dev || 0};
  say($("#msg-venta"), "", true); pintarCarrito();
}
const cascoLinea = l => l.p.retornable ? (l.cantidad - l.dev) * l.p.casco : 0;
const cascoTotal = () => Object.values(carrito).reduce((s, l) => s + cascoLinea(l), 0);
function total() { return Object.values(carrito).reduce((s, l) => s + l.p.precio * l.cantidad + cascoLinea(l), 0); }
function pintarCarrito() {
  $("#carrito tbody").innerHTML = Object.entries(carrito).map(([id, l]) =>
    `<tr><td>${esc(l.p.nombre)}${l.p.retornable ? `<br><small>Envases devueltos:
         <input class="dev" type="number" min="0" max="${l.cantidad}" value="${l.dev}" data-dev="${id}"></small>` : ""}</td><td>
       <button data-d="-1" data-id="${id}">−</button> ${l.cantidad} <button data-d="1" data-id="${id}">+</button></td>
       <td>${money(l.p.precio * l.cantidad + cascoLinea(l))}</td></tr>`).join("");
  document.querySelectorAll("#carrito [data-d]").forEach(b => b.onclick = () => {
    const l = carrito[b.dataset.id], n = l.cantidad + +b.dataset.d;
    if (n > l.p.stock) return;
    if (n <= 0) delete carrito[b.dataset.id]; else { l.cantidad = n; l.dev = Math.min(l.dev, n); }
    pintarCarrito();
  });
  document.querySelectorAll("[data-dev]").forEach(i => i.onchange = () => {
    const l = carrito[i.dataset.dev];
    l.dev = Math.max(0, Math.min(l.cantidad, parseInt(i.value) || 0)); setTimeout(pintarCarrito);
  });
  $("#total").textContent = money(total()); $("#casco").textContent = money(cascoTotal()); cambio();
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
    $("#cliente").innerHTML = cs.map(c => `<option value="${c.id}">${esc(c.nombre)} (debe ${money(c.saldo)})</option>`).join("");
  }
};
$("#vaciar").onclick = () => { carrito = {}; pintarCarrito(); };
$("#cobrar").onclick = async () => {
  const items = Object.entries(carrito).map(([id, l]) =>
    ({producto_id: +id, cantidad: l.cantidad, envases_devueltos: l.dev}));
  const body = {items, metodo: $("#metodo").value};
  if (body.metodo === "fiado") body.cliente_id = +$("#cliente").value;
  else if ($("#recibido").value) body.recibido = $("#recibido").value;
  try {
    const v = await api("/api/ventas", {body});
    say($("#msg-venta"), `Venta #${v.id} registrada. ` + (body.metodo === "fiado" ? "Cargada a fiado." : `Cambio: ${money(v.cambio)}`), true);
    carrito = {}; $("#recibido").value = ""; pintarCarrito(); cargarCatalogo();
  } catch (e) { say($("#msg-venta"), e.message, false); }
};

// ---- Inventario ----
async function cargarInventario() {
  const rows = await api("/api/productos");
  $("#tabla-inv tbody").innerHTML = rows.map(p =>
    `<tr><td>${esc(p.codigo)}</td><td>${esc(p.nombre)}</td><td>${esc(p.categoria)}</td>
     <td>${money(p.precio)}</td><td>${money(p.costo)}</td>
     <td class="${p.stock <= p.stock_minimo ? "bajo" : ""}">${p.stock}</td>
     <td>${p.retornable ? `${p.vacios} / ${p.en_calle}<br>
         <button data-dev-env="${p.id}">Devolución</button> <button data-canje="${p.id}">Canje</button>` : "—"}</td>
     <td><input type="number" size="3" style="width:70px" placeholder="±" data-aj="${p.id}">
         <button data-ok="${p.id}">OK</button></td>
     <td><button data-del="${p.id}">🗑</button></td></tr>`).join("");
  document.querySelectorAll("[data-ok]").forEach(b => b.onclick = async () => {
    const cant = $(`[data-aj="${b.dataset.ok}"]`).value;
    try { await api(`/api/productos/${b.dataset.ok}/ajuste`, {body: {cantidad: cant}}); cargarInventario(); }
    catch (e) { say($("#msg-inv"), e.message, false); }
  });
  const envase = (attr, ruta, texto) => document.querySelectorAll(`[${attr}]`).forEach(b => b.onclick = async () => {
    const n = prompt(texto); if (!n) return;
    try {
      const r = await api(`/api/productos/${b.getAttribute(attr)}/${ruta}`, {body: {cantidad: n}});
      say($("#msg-inv"), r.reembolso !== undefined ? `Reembolsa ${money(r.reembolso)} de casco` : "Canje registrado", true);
      cargarInventario();
    } catch (e) { say($("#msg-inv"), e.message, false); }
  });
  envase("data-dev-env", "devolucion", "¿Cuántos envases vacíos regresa el cliente?");
  envase("data-canje", "canje-proveedor", "¿Cuántos envases vacíos entregas al repartidor?");
  document.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    if (!confirm("¿Eliminar producto?")) return;
    await api(`/api/productos/${b.dataset.del}`, {method: "DELETE", body: {}}); cargarInventario();
  });
}
$("#form-producto").onsubmit = async e => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  body.retornable = e.target.retornable.checked;
  if (!body.categoria) delete body.categoria;
  try { await api("/api/productos", {body}); e.target.reset(); say($("#msg-inv"), "Producto agregado", true); cargarInventario(); }
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
     <td>${c.saldo ? `<button data-abono="${c.id}">Abonar</button>` : ""}</td></tr>`).join("");
  $("#por-cobrar").textContent = money(cs.reduce((s, c) => s + c.saldo, 0));
  document.querySelectorAll("[data-abono]").forEach(b => b.onclick = async () => {
    const m = prompt("Monto del abono ($)"); if (!m) return;
    try { await api(`/api/clientes/${b.dataset.abono}/abono`, {body: {monto: m}}); cargarClientes(); }
    catch (e) { say($("#msg-cli"), e.message, false); }
  });
}
$("#form-cliente").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("/api/clientes", {body: Object.fromEntries(new FormData(e.target))});
    e.target.reset(); say($("#msg-cli"), "Cliente agregado", true); cargarClientes();
  } catch (err) { say($("#msg-cli"), err.message, false); }
};

// ---- Sugerencia de pedido ----
async function cargarPedido() {
  const d = await api(`/api/sugerencia-pedido?historial=${$("#p-hist").value}&cobertura=${$("#p-cob").value}`);
  $("#t-pedido tbody").innerHTML = d.items.map(i =>
    `<tr><td>${esc(i.nombre)}</td><td class="${i.dias_de_stock !== null && i.dias_de_stock < 2 ? "bajo" : ""}">${i.stock}</td>
     <td>${i.promedio_diario}</td><td>${i.dias_de_stock ?? "—"}</td><td><b>${i.pedir}</b></td><td>${money(i.costo_estimado)}</td></tr>`).join("")
    || `<tr><td colspan="6">No hace falta pedir nada 🎉</td></tr>`;
  $("#p-total").textContent = money(d.total_estimado);
}
$("#p-calc").onclick = cargarPedido;

// ---- Licencia ----
async function mostrarLicencia(info) {
  info = info.instalacion ? info : await fetch("/api/licencia").then(r => r.json());
  $("#lic-mensaje").textContent = info.mensaje || info.error || "";
  $("#lic-instalacion").textContent = info.instalacion;
  $("#licencia-overlay").hidden = false;
}
async function revisarLicencia() {
  const info = await fetch("/api/licencia").then(r => r.json());
  if (!info.activa) return mostrarLicencia(info);
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
  $("#licencia-overlay").hidden = true; e.target.reset(); say($("#msg-lic"), "", true);
  revisarLicencia();
};

// ---- Sesion y usuarios ----
let modoAuth = "login";
function mostrarAuth(configurado) {
  const setup = configurado === false;
  modoAuth = setup ? "setup" : "login";
  $("#form-auth [name=nombre]").hidden = !setup;
  $("#form-auth [name=nombre]").required = setup;
  $("#form-auth [name=password]").autocomplete = setup ? "new-password" : "current-password";
  $("#auth-titulo").textContent = setup ? "Bienvenido: crea la cuenta del dueño" : "Iniciar sesión";
  $("#auth-ayuda").textContent = setup ? "Será la cuenta con acceso total. Guarda bien la contraseña (mínimo 6 caracteres)." : "";
  $("#auth-boton").textContent = setup ? "Crear cuenta" : "Entrar";
  $("#auth-overlay").hidden = false;
}
function aplicarUsuario(u) {
  document.body.dataset.rol = u.rol;
  $("#usuario-actual").textContent = `${u.nombre} (${u.rol === "dueno" ? "dueño" : "cajero"})`;
  $("#auth-overlay").hidden = true;
  document.querySelectorAll("nav button, .tab").forEach(e => e.classList.remove("active"));
  document.querySelector('nav [data-tab=venta]').classList.add("active"); $("#venta").classList.add("active");
  carrito = {}; pintarCarrito(); cargarCatalogo();
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
  const actual = prompt("Contraseña actual"); if (!actual) return;
  const nueva = prompt("Contraseña nueva (mínimo 6 caracteres)"); if (!nueva) return;
  try { await api("/api/auth/password", {body: {actual, nueva}}); alert("Contraseña actualizada"); }
  catch (e) { alert(e.message); }
};
async function cargarUsuarios() {
  const us = await api("/api/usuarios");
  $("#t-usuarios tbody").innerHTML = us.map(u =>
    `<tr><td>${esc(u.nombre)}</td><td>${esc(u.usuario)}</td><td>${u.rol === "dueno" ? "Dueño" : "Cajero"}</td>
     <td>${u.activo ? "Activo" : "<span class='bajo'>Desactivado</span>"}</td>
     <td><button data-pw="${u.id}">Nueva contraseña</button>
         <button data-act="${u.id}" data-val="${u.activo ? 0 : 1}">${u.activo ? "Desactivar" : "Activar"}</button></td></tr>`).join("");
  const editar = async (id, body) => {
    try { await api(`/api/usuarios/${id}`, {method: "PUT", body}); cargarUsuarios(); }
    catch (e) { say($("#msg-usr"), e.message, false); }
  };
  document.querySelectorAll("[data-pw]").forEach(b => b.onclick = () => {
    const p = prompt("Nueva contraseña (mínimo 6 caracteres)"); if (p) editar(b.dataset.pw, {password: p});
  });
  document.querySelectorAll("[data-act]").forEach(b => b.onclick = () => editar(b.dataset.act, {activo: b.dataset.val === "1"}));
  const red = await api("/api/red");
  $("#acceso-red").innerHTML = red.urls.length
    ? `<p>Abre una de estas direcciones en el navegador de la tablet (mismo Wi-Fi):</p>` +
      red.urls.map(u => `<div class="url">${esc(u)}</div>`).join("")
    : `<p>El acceso desde otros dispositivos está apagado. Abre el programa con el acceso directo
       <b>"Punto de Venta (con acceso desde tablet)"</b> para activarlo.</p>`;
}
$("#form-usuario").onsubmit = async e => {
  e.preventDefault();
  try {
    await api("/api/usuarios", {body: Object.fromEntries(new FormData(e.target))});
    e.target.reset(); say($("#msg-usr"), "Usuario agregado", true); cargarUsuarios();
  } catch (err) { say($("#msg-usr"), err.message, false); }
};

revisarLicencia();
