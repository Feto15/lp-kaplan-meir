Project layout (key parts):

- backend/
  - survival_km.py (V2) / survival_km_v3.py (V3) + env templates (.env.weth_usdc, .env.aero_weth)
  - cache/ (JSON cache)
- frontend/
  - public/data/manifest.json (dataset sources to Worker)
  - src/ (App, fetch helpers, components)
  - .env.development / .env.production (VITE_DATA_BASE)
- worker/
  - src/index.ts (Hono handler with CORS, /latest, /ingest, /health)
- cloudflare/schema.sql (D1 table rec_runs)
- wrangler.toml (Worker+D1 binding)
- project.md (usage guide)
