CREATE TABLE IF NOT EXISTS screener_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    total INTEGER DEFAULT 0,
    processed INTEGER DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS screener_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    list_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal TEXT NOT NULL,
    score REAL NOT NULL,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(list_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_results_list_signal ON screener_results(list_id, signal);
CREATE INDEX IF NOT EXISTS idx_results_score ON screener_results(list_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_runs_list ON screener_runs(list_id, started_at DESC);
