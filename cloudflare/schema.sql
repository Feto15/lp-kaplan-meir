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
