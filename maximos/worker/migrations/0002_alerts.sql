-- Lista corta de tickers que el usuario quiere vigilar para alertas de señal fuerte
-- (compra_fuerte / venta_fuerte). Se reemplaza entera cada vez que se guarda desde la UI,
-- no hay altas/bajas individuales — es una lista chica, manejada a mano.
CREATE TABLE IF NOT EXISTS alert_watchlist (
    ticker TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);
