import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'General',
    precio INTEGER NOT NULL CHECK (precio >= 0),   -- centavos
    costo INTEGER NOT NULL DEFAULT 0 CHECK (costo >= 0),
    stock INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 5,
    activo INTEGER NOT NULL DEFAULT 1,
    retornable INTEGER NOT NULL DEFAULT 0,
    casco INTEGER NOT NULL DEFAULT 0,       -- deposito por envase, centavos
    vacios INTEGER NOT NULL DEFAULT 0,      -- envases vacios en tienda
    en_calle INTEGER NOT NULL DEFAULT 0     -- envases con casco pagado fuera de la tienda
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
    hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('dueno','cajero')),
    activo INTEGER NOT NULL DEFAULT 1,
    sesion_version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS licencia (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    clave TEXT NOT NULL,
    activada TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL DEFAULT '',
    limite INTEGER NOT NULL DEFAULT 0,      -- 0 = sin limite
    saldo INTEGER NOT NULL DEFAULT 0,       -- lo que debe, centavos
    activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS abonos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    monto INTEGER NOT NULL CHECK (monto > 0)
);
CREATE TABLE IF NOT EXISTS casco_mov (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL,
    monto INTEGER NOT NULL                  -- + cobrado, - reembolsado
);
CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    total INTEGER NOT NULL,
    recibido INTEGER NOT NULL,
    cambio INTEGER NOT NULL,
    metodo TEXT NOT NULL DEFAULT 'efectivo',
    cliente_id INTEGER REFERENCES clientes(id),
    casco INTEGER NOT NULL DEFAULT 0,
    usuario_id INTEGER REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS venta_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER NOT NULL REFERENCES ventas(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio INTEGER NOT NULL,
    costo INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL,
    motivo TEXT NOT NULL
);
"""

# (codigo, nombre, categoria, precio, costo, stock, minimo) -- precios en centavos
SEED = [
    ("7501055300075", "Coca-Cola 600 ml", "Refrescos", 1800, 1350, 48, 12),
    ("7501055303670", "Coca-Cola 2 L", "Refrescos", 3500, 2800, 24, 6),
    ("7501055365013", "Coca-Cola 3 L", "Refrescos", 4800, 3900, 18, 6),
    ("7501055310289", "Coca-Cola Lata 355 ml", "Refrescos", 1600, 1200, 48, 12),
    ("7501055363064", "Coca-Cola Zero 600 ml", "Refrescos", 1800, 1350, 24, 6),
    ("7501055300181", "Coca-Cola Vidrio 355 ml", "Refrescos", 1500, 1100, 36, 12),
    ("7501055302208", "Fanta Naranja 600 ml", "Refrescos", 1800, 1350, 24, 6),
    ("7501055301546", "Sprite 600 ml", "Refrescos", 1800, 1350, 24, 6),
    ("7501055316342", "Fresca 600 ml", "Refrescos", 1800, 1350, 12, 6),
    ("7501055344025", "Ciel Agua 1 L", "Agua", 1400, 900, 36, 12),
    ("7501055340584", "Ciel Agua 600 ml", "Agua", 1000, 600, 48, 12),
    ("7501055352051", "Powerade Mora Azul 600 ml", "Bebidas deportivas", 2000, 1450, 18, 6),
    ("7501055365341", "Del Valle Naranja 413 ml", "Jugos", 1500, 1050, 18, 6),
    ("7501000112890", "Sabritas Original 45 g", "Botanas", 1800, 1400, 20, 6),
    ("7501000614172", "Galletas Marias Gamesa", "Galletas", 2200, 1700, 15, 5),
    ("7501030400016", "Pan Bimbo Blanco Grande", "Panaderia", 4500, 3800, 8, 4),
    ("7501020520071", "Leche Lala Entera 1 L", "Lacteos", 2800, 2400, 20, 8),
    ("7501011111117", "Huevo (kg)", "Abarrotes", 4200, 3600, 10, 4),
    ("7501022222224", "Arroz 1 kg", "Abarrotes", 2600, 2100, 12, 5),
    ("7501033333331", "Frijol 1 kg", "Abarrotes", 3400, 2800, 12, 5),
    ("7501044444448", "Aceite Vegetal 1 L", "Abarrotes", 4200, 3500, 10, 4),
    ("7501055300600", "Coca-Cola Retornable 600 ml", "Refrescos", 1300, 1000, 48, 12),
]

# codigo -> casco (centavos) de los envases retornables
RETORNABLES = {"7501055300181": 600, "7501055300600": 800}

# columnas agregadas despues de la primera version (migracion de bases existentes)
MIGRACIONES = {
    "productos": ["retornable INTEGER NOT NULL DEFAULT 0", "casco INTEGER NOT NULL DEFAULT 0",
                  "vacios INTEGER NOT NULL DEFAULT 0", "en_calle INTEGER NOT NULL DEFAULT 0"],
    "ventas": ["cliente_id INTEGER REFERENCES clientes(id)", "casco INTEGER NOT NULL DEFAULT 0",
               "usuario_id INTEGER REFERENCES usuarios(id)"],
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    for tabla, cols in MIGRACIONES.items():
        existentes = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabla})")}
        for col in cols:
            if col.split()[0] not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col}")
    if conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO productos (codigo,nombre,categoria,precio,costo,stock,stock_minimo)"
            " VALUES (?,?,?,?,?,?,?)",
            SEED,
        )
        for codigo, casco in RETORNABLES.items():
            conn.execute("UPDATE productos SET retornable=1, casco=? WHERE codigo=?", (casco, codigo))
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
