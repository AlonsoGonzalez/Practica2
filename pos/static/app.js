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
  carrito[id] = {p, cantidad: (carrito[id]?.cantidad || 0) + 1};
  say($("#msg-venta"), "", true); pintarCarrito();
}
function total() { return Object.values(carrito).reduce((s, l) => s + l.p.precio * l.cantidad, 0); }
function pintarCarrito() {
  $("#carrito tbody").innerHTML = Object.entries(carrito).map(([id, l]) =>
    `<tr><td>${esc(l.p.nombre)}</td><td>
       <button data-d="-1" data-id="${id}">−</button> ${l.cantidad} <button data-d="1" data-id="${id}">+</button></td>
       <td>${money(l.p.precio * l.cantidad)}</td></tr>`).join("");
  document.querySelectorAll("#carrito [data-d]").forEach(b => b.onclick = () => {
    const l = carrito[b.dataset.id], n = l.cantidad + +b.dataset.d;
    if (n > l.p.stock) return;
    if (n <= 0) delete carrito[b.dataset.id]; else l.cantidad = n;
    pintarCarrito();
  });
  $("#total").textContent = money(total()); cambio();
}
function cambio() {
  const r = parseFloat($("#recibido").value);
  $("#cambio").textContent = isNaN(r) ? "$0.00" : money(Math.max(0, Math.round(r * 100) - total()));
}
$("#recibido").oninput = cambio;
$("#vaciar").onclick = () => { carrito = {}; pintarCarrito(); };
$("#cobrar").onclick = async () => {
  const items = Object.entries(carrito).map(([id, l]) => ({producto_id: +id, cantidad: l.cantidad}));
  const body = {items}; if ($("#recibido").value) body.recibido = $("#recibido").value;
  try {
    const v = await api("/api/ventas", {body});
    say($("#msg-venta"), `Venta #${v.id} cobrada. Cambio: ${money(v.cambio)}`, true);
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
     <td><input type="number" size="3" style="width:70px" placeholder="±" data-aj="${p.id}">
         <button data-ok="${p.id}">OK</button></td>
     <td><button data-del="${p.id}">🗑</button></td></tr>`).join("");
  document.querySelectorAll("[data-ok]").forEach(b => b.onclick = async () => {
    const cant = $(`[data-aj="${b.dataset.ok}"]`).value;
    try { await api(`/api/productos/${b.dataset.ok}/ajuste`, {body: {cantidad: cant}}); cargarInventario(); }
    catch (e) { say($("#msg-inv"), e.message, false); }
  });
  document.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    if (!confirm("¿Eliminar producto?")) return;
    await api(`/api/productos/${b.dataset.del}`, {method: "DELETE", body: {}}); cargarInventario();
  });
}
$("#form-producto").onsubmit = async e => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
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
  $("#t-top tbody").innerHTML = c.top_productos.map(t =>
    `<tr><td>${esc(t.nombre)}</td><td>${t.unidades}</td><td>${money(t.importe)}</td></tr>`).join("");
  const bajo = await api("/api/reportes/stock-bajo");
  $("#t-bajo tbody").innerHTML = bajo.map(p =>
    `<tr><td>${esc(p.nombre)}</td><td class="bajo">${p.stock}</td><td>${p.stock_minimo}</td></tr>`).join("");
}
$("#fecha-corte").onchange = cargarCorte;

cargarCatalogo();
