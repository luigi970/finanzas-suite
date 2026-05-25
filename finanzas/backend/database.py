import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "finanzas.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,  -- bank | crypto | broker | cash | other
            color       TEXT DEFAULT '#6366f1',
            active      INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS positions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            asset        TEXT NOT NULL,       -- ARS, USD, BTC, AAPL, YPF, USDT, etc.
            asset_type   TEXT NOT NULL,       -- fiat | crypto | stablecoin | stock | cedear | fixed_term | fund
            quantity     REAL NOT NULL DEFAULT 0,
            -- Solo para fixed_term / fund:
            start_date   TEXT,
            end_date     TEXT,
            rate         REAL,               -- tasa anual %
            auto_renew   INTEGER DEFAULT 0,
            notes        TEXT,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            date         TEXT NOT NULL,
            description  TEXT,
            amount       REAL NOT NULL,
            currency     TEXT NOT NULL,
            type         TEXT NOT NULL,      -- income | expense | transfer
            category     TEXT,
            source       TEXT DEFAULT 'manual',  -- manual | pdf | csv | image | text
            raw_text     TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_cache (
            asset        TEXT PRIMARY KEY,
            price_usd    REAL,
            price_ars    REAL,
            updated_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    # Migrations: add columns to existing tables without breaking existing data
    for sql in [
        "ALTER TABLE positions ADD COLUMN avg_price REAL",
        "ALTER TABLE transactions ADD COLUMN unit_price REAL",
        "ALTER TABLE transactions ADD COLUMN realized_pnl REAL",
        "ALTER TABLE transactions ADD COLUMN fee REAL",
        "ALTER TABLE transactions ADD COLUMN fee_currency TEXT",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column already exists
    conn.close()
