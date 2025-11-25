-- D1 schema for storing per-run JSON payloads (e.g., recommendations/prices).
CREATE TABLE IF NOT EXISTS rec_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT NOT NULL,
  lookback INTEGER NOT NULL,
  interval_sec INTEGER NOT NULL,
  generated_at INTEGER NOT NULL, -- epoch milliseconds of the data generation time
  payload TEXT NOT NULL,         -- raw JSON string
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000)
);

-- One row per slot (pair, interval, timestamp).
CREATE UNIQUE INDEX IF NOT EXISTS rec_runs_slot
  ON rec_runs(pair, interval_sec, generated_at);

-- For fast latest lookup per pair/interval.
CREATE INDEX IF NOT EXISTS rec_runs_latest
  ON rec_runs(pair, lookback, interval_sec, generated_at DESC);

-- Raw price snapshots (incremental ingest).
CREATE TABLE IF NOT EXISTS prices (
  pair TEXT NOT NULL,
  ts INTEGER NOT NULL,      -- epoch milliseconds (or seconds, consistent with ingest)
  price REAL NOT NULL,
  block INTEGER,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000),
  PRIMARY KEY(pair, ts)
);

-- Cached survival/recommendation runs keyed by lookback + interval.
CREATE TABLE IF NOT EXISTS survival_runs (
  pair TEXT NOT NULL,
  lookback INTEGER NOT NULL,
  interval_sec INTEGER NOT NULL,
  generated_at INTEGER NOT NULL,
  payload TEXT NOT NULL, -- JSON string { recommendations, prices, meta, ... }
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now') * 1000),
  PRIMARY KEY(pair, lookback, interval_sec, generated_at)
);

CREATE INDEX IF NOT EXISTS survival_runs_latest
  ON survival_runs(pair, lookback, interval_sec, generated_at DESC);
