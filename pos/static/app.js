const $ = (s, r = document) => r.querySelector(s);
const money = c => "$" + (c / 100).toFixed(2);
const esc = s => String(s).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const api = async (url, opts = {}) => {
  const r = await fetch(url, opts.body
    ? {method: opts.method || "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(opts.body)}
    : opts);
  const data = await r.json();
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
    carrito = {}; $("#recibido").value = ""; pintarCarrito(); // ---- Fiado ----
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

cargarCatalogo();
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

cargarCatalogo();
