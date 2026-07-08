import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "fiscal.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS fiscal_profile (
            id INTEGER PRIMARY KEY,
            cuit TEXT NOT NULL,
            razon_social TEXT,
            condicion TEXT,
            categoria_monotributo TEXT,
            tiene_inmuebles INTEGER DEFAULT 0,
            tiene_vehiculos INTEGER DEFAULT 0,
            tiene_inversiones INTEGER DEFAULT 0,
            opera_cripto INTEGER DEFAULT 0,
            opera_cedears INTEGER DEFAULT 0,
            usa_broker INTEGER DEFAULT 0,
            tiene_caja_ahorro_usd INTEGER DEFAULT 0,
            periodo_fiscal TEXT,
            notas TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS arca_cache (
            id INTEGER PRIMARY KEY,
            automation TEXT NOT NULL,
            periodo TEXT,
            data TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            period TEXT,
            content TEXT,
            file_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY,
            role TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS obligations (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            applies_to TEXT,
            notes TEXT
        );
    """)

    migrations = [
        # future ALTER TABLE statements here
    ]
    for m in migrations:
        try:
            c.execute(m)
        except Exception:
            pass

    conn.commit()
    conn.close()
