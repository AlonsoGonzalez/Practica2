import math
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, render_template, request

from .caja import requiere_turno
from .db import begin, get_db
from .validar import MAX_CANTIDAD, MAX_ENTERO, MAX_LINEAS, centavos, datos, entero, opcional, texto

bp = Blueprint("pos", __name__)


def err(msg, code=400):
    return jsonify(error=msg), code


def pesos_a_centavos(valor):
    """Convierte 18.5 / '18.50' a 1850 sin errores de punto flotante (ValueError si es invalido)."""
    return centavos(valor)


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
    rows = [dict(r) for r in get_db().execute(sql, params).fetchall()]
    if g.usuario["rol"] != "dueno":  # el cajero no ve costos
        for r in rows:
            r.pop("costo")
    return jsonify(rows)


@bp.post("/api/productos")
def crear_producto():
    d = datos()
    try:
        nombre, codigo = texto(d["nombre"], 120, True), texto(d["codigo"], 50, True)
        categoria = texto(d.get("categoria") or "General", 60)
        precio = pesos_a_centavos(d["precio"])
        costo = pesos_a_centavos(opcional(d, "costo", 0))
        stock = entero(opcional(d, "stock", 0), 0, MAX_ENTERO)
        minimo = entero(opcional(d, "stock_minimo", 5), 0, MAX_ENTERO)
        retornable = 1 if d.get("retornable") else 0
        casco = pesos_a_centavos(opcional(d, "casco", 0)) if retornable else 0
    except (KeyError, ValueError, AttributeError):
        return err("Revisa los datos del producto: nombre, código y precio son obligatorios y los números no pueden ser negativos.")
    if precio < 0 or costo < 0 or casco < 0:
        return err("Revisa los datos del producto: nombre, código y precio son obligatorios y los números no pueden ser negativos.")
    db = get_db()
    begin()
    previo = db.execute("SELECT id, activo FROM productos WHERE codigo=?", (codigo,)).fetchone()
    if previo and previo["activo"]:
        return err("Ya existe un producto con ese código.", 409)
    if previo:  # estaba borrado: se reactiva conservando su historial
        pid = previo["id"]
        db.execute(
            "UPDATE productos SET nombre=?,categoria=?,precio=?,costo=?,stock=?,stock_minimo=?,"
            "retornable=?,casco=?,vacios=0,en_calle=0,activo=1 WHERE id=?",
            (nombre, categoria, precio, costo, stock, minimo, retornable, casco, pid),
        )
    else:
        pid = db.execute(
            "INSERT INTO productos (codigo,nombre,categoria,precio,costo,stock,stock_minimo,retornable,casco)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (codigo, nombre, categoria, precio, costo, stock, minimo, retornable, casco),
        ).lastrowid
    if stock:
        db.execute(
            "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
            (pid, stock, "inventario inicial"),
        )
    db.commit()
    return jsonify(id=pid), 201


@bp.put("/api/productos/<int:pid>")
def editar_producto(pid):
    d = datos()
    db = get_db()
    p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
    if not p:
        return err("No se encontró ese producto.", 404)
    try:
        nombre = texto(d.get("nombre", p["nombre"]), 120, True)
        categoria = texto(d.get("categoria", p["categoria"]) or "General", 60)
        precio = pesos_a_centavos(d["precio"]) if "precio" in d else p["precio"]
        costo = pesos_a_centavos(d["costo"]) if "costo" in d else p["costo"]
        minimo = entero(opcional(d, "stock_minimo", p["stock_minimo"]), 0, MAX_ENTERO)
        retornable = (1 if d["retornable"] else 0) if "retornable" in d else p["retornable"]
        casco = pesos_a_centavos(d["casco"]) if "casco" in d else p["casco"]
    except (ValueError, AttributeError):
        return err("Revisa los datos del producto: nombre, código y precio son obligatorios y los números no pueden ser negativos.")
    if precio < 0 or costo < 0 or casco < 0:
        return err("Revisa los datos del producto: nombre, código y precio son obligatorios y los números no pueden ser negativos.")
    db.execute(
        "UPDATE productos SET nombre=?,categoria=?,precio=?,costo=?,stock_minimo=?,retornable=?,casco=?"
        " WHERE id=?",
        (nombre, categoria, precio, costo, minimo, retornable,
         casco if retornable else 0, pid),
    )
    db.commit()
    return jsonify(ok=True)


@bp.delete("/api/productos/<int:pid>")
def borrar_producto(pid):
    db = get_db()
    cur = db.execute("UPDATE productos SET activo=0 WHERE id=?", (pid,))
    db.commit()
    return (jsonify(ok=True), 200) if cur.rowcount else err("No se encontró ese producto.", 404)


@bp.post("/api/productos/<int:pid>/ajuste")
def ajustar_stock(pid):
    """Entrada (+) o salida/merma (-) de inventario."""
    d = datos()
    try:
        cantidad = entero(d["cantidad"], -MAX_ENTERO, MAX_ENTERO)
    except (KeyError, ValueError):
        return err("La cantidad no es válida. Escribe un número entero mayor que cero.")
    if cantidad == 0:
        return err("La cantidad no es válida. Escribe un número entero mayor que cero.")
    db = get_db()
    begin()
    p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
    if not p:
        return err("No se encontró ese producto.", 404)
    if p["stock"] + cantidad < 0 or p["stock"] + cantidad > MAX_ENTERO:
        return err("Ese ajuste dejaría el inventario en un número imposible (menor que cero o demasiado grande).")
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
    d = datos()
    items = d.get("items")
    if not isinstance(items, list) or not items:
        return err("El ticket está vacío. Agrega al menos un producto.")
    if len(items) > MAX_LINEAS:
        return err("El ticket tiene demasiadas líneas. Cóbralo en dos partes.")
    metodo = d.get("metodo", "efectivo")
    if metodo not in ("efectivo", "fiado"):
        return err("El método de pago no es válido.")
    db = get_db()
    begin()  # bloquea escrituras de otros cajeros hasta terminar: nadie vende la misma ultima pieza
    turno, falla = requiere_turno(db)
    if falla:
        return falla
    pedidos = {}  # producto_id -> [cantidad, envases_devueltos]
    try:
        for it in items:
            cant = entero(it["cantidad"], 1, MAX_CANTIDAD)
            dev = entero(it.get("envases_devueltos", 0), 0, cant)
            acc = pedidos.setdefault(entero(it["producto_id"], 1), [0, 0])
            acc[0] += cant
            acc[1] += dev
    except (KeyError, ValueError, TypeError, AttributeError):
        return err("Hay un producto del ticket con datos no válidos.")
    lineas, subtotal, casco_total = [], 0, 0
    for pid, (cant, dev) in pedidos.items():
        p = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (pid,)).fetchone()
        if not p:
            return err("Uno de los productos del ticket ya no existe. Quítalo del ticket.", 404)
        if p["stock"] < cant:
            return err(f"No alcanza el inventario de {p['nombre']}: quedan {p['stock']} y quieres vender {cant}.", 409)
        if dev and not p["retornable"]:
            return err(f"{p['nombre']} no es un producto retornable.")
        casco = (cant - dev) * p["casco"] if p["retornable"] else 0
        lineas.append((p, cant, dev, casco))
        subtotal += p["precio"] * cant
        casco_total += casco
    total = subtotal + casco_total

    cliente = None
    if metodo == "fiado":
        cliente = db.execute(
            "SELECT * FROM clientes WHERE id=? AND activo=1", (d.get("cliente_id"),)
        ).fetchone() if isinstance(d.get("cliente_id"), (int, str)) and not isinstance(d.get("cliente_id"), bool) else None
        if not cliente:
            return err("Para vender a fiado elige primero un cliente.", 400)
        if cliente["limite"] and cliente["saldo"] + total > cliente["limite"]:
            def m(c): return "$%.2f" % (c / 100)
            return err(f"No se puede fiar: {cliente['nombre']} ya debe {m(cliente['saldo'])}, esta venta es de {m(total)} "
                       f"y su límite de crédito es {m(cliente['limite'])}. Le quedan {m(max(0, cliente['limite'] - cliente['saldo']))} disponibles.", 409)
        recibido = 0
    else:
        try:
            recibido = pesos_a_centavos(d["recibido"]) if "recibido" in d else total
        except ValueError:
            return err("El monto recibido no es válido.")
        if recibido < total:
            return err("El dinero recibido no alcanza para pagar el total.")
    cambio = recibido - total if metodo == "efectivo" else 0
    cur = db.execute(
        "INSERT INTO ventas (total,recibido,cambio,metodo,cliente_id,casco,usuario_id,turno_id)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (total, recibido, cambio, metodo, cliente["id"] if cliente else None, casco_total,
         g.usuario["id"], turno["id"]),
    )
    vid = cur.lastrowid
    for p, cant, dev, casco in lineas:
        db.execute(
            "INSERT INTO venta_items (venta_id,producto_id,cantidad,precio,costo) VALUES (?,?,?,?,?)",
            (vid, p["id"], cant, p["precio"], p["costo"]),
        )
        db.execute("UPDATE productos SET stock=stock-? WHERE id=?", (cant, p["id"]))
        db.execute(
            "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
            (p["id"], -cant, f"venta #{vid}"),
        )
        if p["retornable"]:
            db.execute(
                "UPDATE productos SET vacios=vacios+?, en_calle=en_calle+? WHERE id=?",
                (dev, cant - dev, p["id"]),
            )
            if casco:
                db.execute(
                    "INSERT INTO casco_mov (producto_id,cantidad,monto,turno_id) VALUES (?,?,?,?)",
                    (p["id"], cant - dev, casco, turno["id"]),
                )
    if cliente:
        db.execute("UPDATE clientes SET saldo=saldo+? WHERE id=?", (total, cliente["id"]))
    db.commit()
    return jsonify(id=vid, total=total, casco=casco_total, recibido=recibido, cambio=cambio), 201


@bp.get("/api/ventas/<int:vid>")
def ver_venta(vid):
    db = get_db()
    v = db.execute("SELECT * FROM ventas WHERE id=?", (vid,)).fetchone()
    if not v:
        return err("No se encontró esa venta.", 404)
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
    try:
        fecha = date.fromisoformat(fecha).isoformat()
    except ValueError:
        return err("La fecha no es válida. Usa el formato AAAA-MM-DD.")
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
    fiado = db.execute(
        "SELECT COALESCE(SUM(total),0) FROM ventas WHERE date(fecha)=? AND metodo='fiado'", (fecha,)
    ).fetchone()[0]
    abonos = db.execute(
        "SELECT COALESCE(SUM(monto),0) FROM abonos WHERE date(fecha)=?", (fecha,)
    ).fetchone()[0]
    cascos = db.execute(
        "SELECT COALESCE(SUM(CASE WHEN monto>0 THEN monto END),0) cobrado,"
        " COALESCE(-SUM(CASE WHEN monto<0 THEN monto END),0) reembolsado"
        " FROM casco_mov WHERE date(fecha)=?",
        (fecha,),
    ).fetchone()
    por_usuario = db.execute(
        "SELECT COALESCE(u.nombre,'(sin usuario)') nombre, COUNT(*) ventas, SUM(v.total) total"
        " FROM ventas v LEFT JOIN usuarios u ON u.id=v.usuario_id WHERE date(v.fecha)=?"
        " GROUP BY v.usuario_id ORDER BY total DESC",
        (fecha,),
    ).fetchall()
    return jsonify(
        fecha=fecha,
        por_usuario=[dict(u) for u in por_usuario],
        turnos=[dict(t) for t in db.execute(
            "SELECT t.id, u.nombre cajero, t.abierto, t.cerrado, t.fondo, t.esperado, t.contado, t.diferencia"
            " FROM turnos t JOIN usuarios u ON u.id=t.usuario_id WHERE date(t.abierto)=? ORDER BY t.id", (fecha,))],
        num_ventas=r["n"],
        total=r["total"],
        fiado=fiado,
        abonos=abonos,
        cascos_cobrados=cascos["cobrado"],
        cascos_reembolsados=cascos["reembolsado"],
        efectivo_en_caja=r["total"] - fiado + abonos - cascos["reembolsado"],
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


# ---------- Envases retornables y casco ----------
def _retornable(db, pid):
    return db.execute(
        "SELECT * FROM productos WHERE id=? AND activo=1 AND retornable=1", (pid,)
    ).fetchone()


def _cantidad(d):
    try:
        return entero(d["cantidad"], 1, MAX_ENTERO)
    except (KeyError, ValueError):
        return None


@bp.post("/api/productos/<int:pid>/devolucion")
def devolucion_envases(pid):
    """Un cliente regresa envases vacios: se le reembolsa el casco."""
    n = _cantidad(datos())
    db = get_db()
    begin()
    p = _retornable(db, pid)
    if not p:
        return err("No se encontró ese producto retornable.", 404)
    if n is None:
        return err("La cantidad no es válida. Escribe un número entero mayor que cero.")
    turno, falla = requiere_turno(db)
    if falla:
        return falla
    if n > p["en_calle"]:
        return err(f"Solo hay {p['en_calle']} envases de este producto fuera de la tienda con casco pagado.", 409)
    reembolso = n * p["casco"]
    db.execute("UPDATE productos SET en_calle=en_calle-?, vacios=vacios+? WHERE id=?", (n, n, pid))
    db.execute(
        "INSERT INTO casco_mov (producto_id,cantidad,monto,turno_id) VALUES (?,?,?,?)",
        (pid, -n, -reembolso, turno["id"]),
    )
    db.commit()
    return jsonify(reembolso=reembolso)


@bp.post("/api/productos/<int:pid>/canje-proveedor")
def canje_proveedor(pid):
    """Se entregan envases vacios al repartidor y se reciben llenos."""
    n = _cantidad(datos())
    db = get_db()
    begin()
    p = _retornable(db, pid)
    if not p:
        return err("No se encontró ese producto retornable.", 404)
    if n is None:
        return err("La cantidad no es válida. Escribe un número entero mayor que cero.")
    if n > p["vacios"]:
        return err(f"Solo hay {p['vacios']} envases vacíos en la tienda para entregar.", 409)
    db.execute("UPDATE productos SET vacios=vacios-?, stock=stock+? WHERE id=?", (n, n, pid))
    db.execute(
        "INSERT INTO movimientos (producto_id,cantidad,motivo) VALUES (?,?,?)",
        (pid, n, "canje de envases con proveedor"),
    )
    db.commit()
    return jsonify(stock=p["stock"] + n, vacios=p["vacios"] - n)


@bp.get("/api/reportes/envases")
def reporte_envases():
    rows = get_db().execute(
        "SELECT id,nombre,casco,stock,vacios,en_calle,en_calle*casco AS casco_en_calle"
        " FROM productos WHERE activo=1 AND retornable=1 ORDER BY nombre"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------- Fiado ----------
@bp.get("/api/clientes")
def listar_clientes():
    rows = get_db().execute(
        "SELECT * FROM clientes WHERE activo=1 ORDER BY saldo DESC, nombre"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/clientes")
def crear_cliente():
    d = datos()
    try:
        nombre = texto(d.get("nombre"), 80)
        telefono = texto(d.get("telefono"), 30)
        limite = pesos_a_centavos(opcional(d, "limite", 0))
    except ValueError:
        return err("Revisa los datos del cliente: el nombre es obligatorio y el límite no puede ser negativo.")
    if not nombre or limite < 0:
        return err("Revisa los datos del cliente: el nombre es obligatorio y el límite no puede ser negativo.")
    db = get_db()
    cur = db.execute(
        "INSERT INTO clientes (nombre,telefono,limite) VALUES (?,?,?)",
        (nombre, telefono, limite),
    )
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@bp.get("/api/clientes/<int:cid>")
def ver_cliente(cid):
    db = get_db()
    c = db.execute("SELECT * FROM clientes WHERE id=? AND activo=1", (cid,)).fetchone()
    if not c:
        return err("No se encontró ese cliente.", 404)
    ventas = db.execute(
        "SELECT id,fecha,total FROM ventas WHERE cliente_id=? ORDER BY id DESC", (cid,)
    ).fetchall()
    abonos = db.execute(
        "SELECT id,fecha,monto FROM abonos WHERE cliente_id=? ORDER BY id DESC", (cid,)
    ).fetchall()
    return jsonify(**dict(c), ventas=[dict(v) for v in ventas], abonos=[dict(a) for a in abonos])


@bp.post("/api/clientes/<int:cid>/abono")
def abonar(cid):
    d = datos()
    try:
        monto = pesos_a_centavos(d["monto"])
    except (KeyError, ValueError):
        return err("El monto no es válido.")
    db = get_db()
    begin()
    c = db.execute("SELECT * FROM clientes WHERE id=? AND activo=1", (cid,)).fetchone()
    if not c:
        return err("No se encontró ese cliente.", 404)
    if monto <= 0:
        return err("El monto no es válido.")
    if monto > c["saldo"]:
        return err("El abono es mayor a lo que el cliente debe.", 409)
    turno, falla = requiere_turno(db)
    if falla:
        return falla
    db.execute("INSERT INTO abonos (cliente_id,monto,turno_id) VALUES (?,?,?)", (cid, monto, turno["id"]))
    db.execute("UPDATE clientes SET saldo=saldo-? WHERE id=?", (monto, cid))
    db.commit()
    return jsonify(saldo=c["saldo"] - monto)


# ---------- Sugerencia de pedido ----------
@bp.get("/api/sugerencia-pedido")
def sugerencia_pedido():
    """Cuanto pedir para cubrir `cobertura` dias segun el promedio vendido en `historial` dias."""
    try:
        historial = min(3650, max(1, entero(request.args.get("historial", 14))))
        cobertura = min(365, max(1, entero(request.args.get("cobertura", 7))))
    except ValueError:
        return err("Los parámetros no son válidos.")
    desde = (date.today() - timedelta(days=historial - 1)).isoformat()
    rows = get_db().execute(
        "SELECT p.*, COALESCE(SUM(i.cantidad),0) vendido FROM productos p"
        " LEFT JOIN (SELECT i.producto_id, i.cantidad FROM venta_items i"
        "            JOIN ventas v ON v.id=i.venta_id WHERE date(v.fecha)>=?) i"
        "   ON i.producto_id=p.id"
        " WHERE p.activo=1 GROUP BY p.id",
        (desde,),
    ).fetchall()
    sugerencias, total = [], 0
    for r in rows:
        promedio = r["vendido"] / historial
        objetivo = math.ceil(promedio * cobertura) + r["stock_minimo"]
        pedir = max(0, objetivo - r["stock"])
        if not pedir:
            continue
        dias_stock = round(r["stock"] / promedio, 1) if promedio else None
        costo = pedir * r["costo"]
        total += costo
        sugerencias.append(dict(
            id=r["id"], nombre=r["nombre"], categoria=r["categoria"], stock=r["stock"],
            promedio_diario=round(promedio, 2), dias_de_stock=dias_stock,
            pedir=pedir, costo_estimado=costo, retornable=bool(r["retornable"]),
        ))
    sugerencias.sort(key=lambda x: (x["dias_de_stock"] is None, x["dias_de_stock"] or 0))
    return jsonify(historial=historial, cobertura=cobertura, total_estimado=total, items=sugerencias)
