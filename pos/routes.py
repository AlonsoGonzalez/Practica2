from datetime import date

from flask import Blueprint, jsonify, render_template, request

from .db import get_db

bp = Blueprint("pos", __name__)


def err(msg, code=400):
    return jsonify(error=msg), code


def pesos_a_centavos(valor):
    """Convierte 18.5 / '18.50' a 1850 sin errores de punto flotante."""
    try:
        return int(round(float(valor) * 100))
    except (TypeError, ValueError):
        raise ValueError("Monto invalido")


@bp.get("/")
def index():
    return render_template("index.html")


# ---------- Productos / inventario ----------
@bp.get("/api/productos")
def listar_productos():
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM productos WHERE activo=1"
    params = []
    if q:
        sql += " AND (nombre LIKE ? OR codigo LIKE ? OR categoria LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY categoria, nombre"
    rows = get_db().execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/productos")
def crear_producto():
    d = request.get_json(silent=True) or {}
    try:
        nombre, codigo = d["nombre"].strip(), d["codigo"].strip()
        precio = pesos_a_centavos(d["precio"])
        costo = pesos_a_centavos(d.get("costo", 0))
        stock = int(d.get("stock", 0))
        minimo = int(d.get("stock_minimo", 5))
    except (KeyError, ValueError, AttributeError):
        return err("Datos de producto invalidos")
    if not nombre or not codigo or precio < 0 or costo < 0:
        return err("Datos de producto invalidos")
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO productos (codigo,nombre,categoria,precio,costo,stock,stock_minimo)"
            " VALUES (?,?,?,?,?,?,?)",
            (codigo, nombre, d.get("categoria", "General"), precio, costo, stock, minimo),
        )
    except Exception:
        return err("Ya existe un producto con ese codigo", 409)
    if stock:
        db.execute(
            "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
            (cur.lastrowid, stock, "inventario inicial"),
        )
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@bp.put("/api/productos/<int:pid>")
def editar_producto(pid):
    d = request.get_json(silent=True) or {}
    db = get_db()
    p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
    if not p:
        return err("Producto no encontrado", 404)
    try:
        nombre = d.get("nombre", p["nombre"]).strip()
        precio = pesos_a_centavos(d["precio"]) if "precio" in d else p["precio"]
        costo = pesos_a_centavos(d["costo"]) if "costo" in d else p["costo"]
        minimo = int(d.get("stock_minimo", p["stock_minimo"]))
    except (ValueError, AttributeError):
        return err("Datos de producto invalidos")
    if not nombre or precio < 0 or costo < 0:
        return err("Datos de producto invalidos")
    db.execute(
        "UPDATE productos SET nombre=?,categoria=?,precio=?,costo=?,stock_minimo=? WHERE id=?",
        (nombre, d.get("categoria", p["categoria"]), precio, costo, minimo, pid),
    )
    db.commit()
    return jsonify(ok=True)


@bp.delete("/api/productos/<int:pid>")
def borrar_producto(pid):
    db = get_db()
    cur = db.execute("UPDATE productos SET activo=0 WHERE id=?", (pid,))
    db.commit()
    return (jsonify(ok=True), 200) if cur.rowcount else err("Producto no encontrado", 404)


@bp.post("/api/productos/<int:pid>/ajuste")
def ajustar_stock(pid):
    """Entrada (+) o salida/merma (-) de inventario."""
    d = request.get_json(silent=True) or {}
    try:
        cantidad = int(d["cantidad"])
    except (KeyError, ValueError, TypeError):
        return err("Cantidad invalida")
    if cantidad == 0:
        return err("Cantidad invalida")
    db = get_db()
    p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
    if not p:
        return err("Producto no encontrado", 404)
    if p["stock"] + cantidad < 0:
        return err("El ajuste dejaria el stock en negativo")
    db.execute("UPDATE productos SET stock=stock+? WHERE id=?", (cantidad, pid))
    db.execute(
        "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
        (pid, cantidad, d.get("motivo") or ("entrada" if cantidad > 0 else "merma")),
    )
    db.commit()
    return jsonify(stock=p["stock"] + cantidad)


# ---------- Ventas ----------
@bp.post("/api/ventas")
def crear_venta():
    d = request.get_json(silent=True) or {}
    items = d.get("items") or []
    if not items:
        return err("El carrito esta vacio")
    db = get_db()
    lineas, total = [], 0
    pedidos = {}
    try:
        for it in items:
            cant = int(it["cantidad"])
            if cant <= 0:
                raise ValueError
            pedidos[int(it["producto_id"])] = pedidos.get(int(it["producto_id"]), 0) + cant
    except (KeyError, ValueError, TypeError):
        return err("Items invalidos")
    for pid, cant in pedidos.items():
        p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
        if not p:
            return err(f"Producto {pid} no encontrado", 404)
        if p["stock"] < cant:
            return err(f"Stock insuficiente de {p['nombre']} (hay {p['stock']})", 409)
        lineas.append((p, cant))
        total += p["precio"] * cant
    try:
        recibido = pesos_a_centavos(d["recibido"]) if "recibido" in d else total
    except ValueError:
        return err("Monto recibido invalido")
    if recibido < total:
        return err("El monto recibido es menor al total")
    cur = db.execute(
        "INSERT INTO ventas (total,recibido,cambio) VALUES (?,?,?)",
        (total, recibido, recibido - total),
    )
    vid = cur.lastrowid
    for p, cant in lineas:
        db.execute(
            "INSERT INTO venta_items (venta_id,producto_id,cantidad,precio,costo) VALUES (?,?,?,?,?)",
            (vid, p["id"], cant, p["precio"], p["costo"]),
        )
        db.execute("UPDATE productos SET stock=stock-? WHERE id=?", (cant, p["id"]))
        db.execute(
            "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
            (p["id"], -cant, f"venta #{vid}"),
        )
    db.commit()
    return jsonify(id=vid, total=total, recibido=recibido, cambio=recibido - total), 201


@bp.get("/api/ventas/<int:vid>")
def ver_venta(vid):
    db = get_db()
    v = db.execute("SELECT * FROM ventas WHERE id=?", (vid,)).fetchone()
    if not v:
        return err("Venta no encontrada", 404)
    items = db.execute(
        "SELECT i.cantidad,i.precio,p.nombre FROM venta_items i"
        " JOIN productos p ON p.id=i.producto_id WHERE i.venta_id=?",
        (vid,),
    ).fetchall()
    return jsonify(**dict(v), items=[dict(i) for i in items])


# ---------- Corte de caja y reportes ----------
@bp.get("/api/corte")
def corte():
    fecha = request.args.get("fecha") or date.today().isoformat()
    db = get_db()
    r = db.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(total),0) total FROM ventas WHERE date(fecha)=?",
        (fecha,),
    ).fetchone()
    utilidad = db.execute(
        "SELECT COALESCE(SUM((i.precio-i.costo)*i.cantidad),0) FROM venta_items i"
        " JOIN ventas v ON v.id=i.venta_id WHERE date(v.fecha)=?",
        (fecha,),
    ).fetchone()[0]
    top = db.execute(
        "SELECT p.nombre, SUM(i.cantidad) unidades, SUM(i.cantidad*i.precio) importe"
        " FROM venta_items i JOIN ventas v ON v.id=i.venta_id"
        " JOIN productos p ON p.id=i.producto_id WHERE date(v.fecha)=?"
        " GROUP BY p.id ORDER BY unidades DESC LIMIT 10",
        (fecha,),
    ).fetchall()
    ventas = db.execute(
        "SELECT id, fecha, total FROM ventas WHERE date(fecha)=? ORDER BY id DESC", (fecha,)
    ).fetchall()
    return jsonify(
        fecha=fecha,
        num_ventas=r["n"],
        total=r["total"],
        utilidad=utilidad,
        ticket_promedio=r["total"] // r["n"] if r["n"] else 0,
        top_productos=[dict(t) for t in top],
        ventas=[dict(v) for v in ventas],
    )


@bp.get("/api/reportes/stock-bajo")
def stock_bajo():
    rows = get_db().execute(
        "SELECT * FROM productos WHERE activo=1 AND stock<=stock_minimo ORDER BY stock"
    ).fetchall()
    return jsonify([dict(r) for r in rows])
