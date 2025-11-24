Project layout (key parts) and how they connect:

- backend/
  - survival_km.py (V2) / survival_km_v3.py (V3): generate CSV/JSON + push to Worker/D1 when ENABLE_D1_INGEST=true.
  - .env.weth_usdc / .env.aero_weth: runtime config (pair, cache prefix, RPC batch, ingest URL).
  - cache/: local price cache JSON used by scripts.

- worker/
  - src/index.ts: Hono Worker exposing /ingest (POST) and /latest (GET). Reads/writes D1 (binding DB). Adds CORS + x-generated-at header for FE.
  - cloudflare/schema.sql: D1 table rec_runs (pair, lookback, interval_sec, generated_at, payload JSON).
  - wrangler.toml: Worker config + D1 binding.

- frontend/
  - public/data/manifest.json: lists datasets; URLs point to Worker /latest with pair/interval/kind.
  - src/api/data.ts: fetches recommendations/prices from Worker, reads x-generated-at header.
  - src/App.tsx + components: render charts/tables and show “Updated” chip.
  - .env.development / .env.production: VITE_DATA_BASE (Worker base URL).

- Root docs
  - project.md: how to run scripts, ingest, deploy Worker.
  - @structure.md: this overview.

Flow (correlation):
1) Backend script runs with env → fetches prices, computes recs → saves CSV/JSON and POSTs payload to Worker /ingest.
2) Worker stores payload in D1 (rec_runs) with generated_at.
3) Frontend (via manifest) calls Worker /latest?pair=...&kind=... → gets payload + x-generated-at → renders data and timestamp.
