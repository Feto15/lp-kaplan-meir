# Survival Rate Kaplan-Meier – Aerodrome ETH/USDC (Base)

Program Python untuk menghitung survival probability harga dalam rentang tick (Uniswap V3) menggunakan Kaplan-Meier estimator, berbasis data historis dari **RPC Base gratis (https://mainnet.base.org)**. Harga dihitung dari cadangan pool Aerodrome WETH/USDbC langsung via `eth_call`.

## Fitur utama
- Ambil data harga pool Aerodrome WETH/USDbC (pair `0xb4885bc63399bf5518b994c1d0c153334ee579d0`, chain `base`) via RPC gratis `https://mainnet.base.org`. Sampling cadangan `getReserves()` per interval waktu (default 600 detik; disarankan 300–600 detik).
- Normalisasi timestamp, urutkan ascending, hitung log-price dan tick (rumus Uniswap V3).
- Hitung durasi bertahan harga di dalam jendela tick ±W, lalu survival probability untuk horizon 6h, 12h, 24h, 48h via Kaplan-Meier (lifelines).
- Rekomendasi otomatis ACCEPT/REJECT berdasar batas: `km_surv >= 0.6`, `count_total >= 200`, `count_full >= 100`.
- Simpan hasil ke `survival_eth_usdc.csv` dan cetak ringkasan yang mudah dibaca.

## Prasyarat
- Python 3.9+.
- Paket: `requests`, `pandas`, `numpy`, `lifelines`.
  ```bash
  pip install requests pandas numpy lifelines
  ```

## Cara menjalankan
```bash
cd backend
export AERODROME_RPC_URL="https://mainnet.base.org"
# opsional: override jika perlu
# export AERODROME_PAIR_ADDRESS="0xb4885bc63399bf5518b994c1d0c153334ee579d0"
# export AERODROME_TOKEN0_DECIMALS="18"   # override desimal token0 (auto-detect jika kosong)
# export AERODROME_TOKEN1_DECIMALS="6"    # override desimal token1 (auto-detect jika kosong)
# export LOOKBACK_HOURS="48"              # default 48 jam (disarankan 24–72 jam)
# export SAMPLE_INTERVAL_SEC="600"        # default 10 menit (disarankan 300–600 detik)
# export RPC_BATCH_SIZE="25"              # jeda setiap N panggilan eth_call
# export RPC_BATCH_SLEEP="0.25"           # durasi sleep antar batch (detik)

python3 survival_km.py
cd ..
```
Hasil CSV/JSON sekarang memakai prefix pair: `backend/<prefix>_survival.csv`, `backend/<prefix>_recommendations.json`, dan cache di `backend/cache/<prefix>_LOOKBACK...json` (prefix otomatis berdasar alamat pair jika `CACHE_PREFIX` kosong). Untuk dipakai FE, salin ke `frontend/public/data/`:
```bash
cp backend/<prefix>_recommendations.json frontend/public/data/recommendations.json
cp backend/cache/<prefix>_LOOKBACK48_INTERVAL600.json frontend/public/data/price.json
```

### Pool V3/CL (slot0) – script terpisah
Untuk pool tipe V3/CL (mis. Pancake/Uniswap V3), gunakan `backend/survival_km_v3.py`:
```bash
cd backend
AERODROME_RPC_URL=https://bsc-dataseed.binance.org \
AERODROME_PAIR_ADDRESS=0x...pair_v3... \
CACHE_PREFIX=my_v3_pair \
LOOKBACK_HOURS=48 SAMPLE_INTERVAL_SEC=600 \
RPC_BATCH_SIZE=10 RPC_BATCH_SLEEP=0.5 \
python3 survival_km_v3.py --no-cache
```
Output: `backend/survival_eth_usdc_v3.csv`, `backend/survival_recommendations_v3.json`, dan cache `cache/<prefix>_v3_LOOKBACK...json`.
Hasil V3 juga memakai prefix: `backend/<prefix>_survival_v3.csv`, `backend/<prefix>_recommendations_v3.json`, cache `backend/cache/<prefix>_v3_LOOKBACK...json`.

## Cloudflare Worker + D1
- Worker entry: `worker/src/index.ts`, config `wrangler.toml`, DB `lp` (D1, id `6109bab0-f024-44f3-943e-c8319e605eb8`).
- Schema: `cloudflare/schema.sql` (tabel `rec_runs` dengan kolom `pair`, `interval_sec`, `generated_at`, `payload`).
- Endpoint:
  - `POST /ingest` dengan body `{ pair, lookback, interval_sec, generated_at, payload }` (payload berisi `{recommendations, prices}`).
  - `GET /latest?pair=...&interval_sec=...&kind=recommendations|prices` mengembalikan JSON + header `x-generated-at`.
  - `GET /health` untuk pengecekan liveness. CORS sudah diaktifkan.
- Deploy: `pnpm wrangler deploy`. Dev: `pnpm wrangler dev`. Apply schema: `pnpm wrangler d1 execute lp --remote --file cloudflare/schema.sql`.

## Env dan ingest otomatis
- Backend env contoh:
  - `backend/.env.weth_usdc`, `backend/.env.aero_weth` (ENABLE_D1_INGEST, WORKER_INGEST_URL, pair, interval, batch).
  - Auto-export sebelum run: `set -a; source .env.weth_usdc; set +a`.
- Jalankan:
  - V2: `python3 survival_km.py` (tanpa flag = top-up cache dan push D1).
  - V3: `python3 survival_km_v3.py` (pastikan pair CL/V3).
- FE env:
  - `frontend/.env.development` → `VITE_DATA_BASE=https://lp.kalarangga289.workers.dev`
  - `frontend/.env.production` sama, atau sesuaikan base URL Worker.
- Manifest: `frontend/public/data/manifest.json` menunjuk ke `/latest?...&kind=...` sehingga FE fetch dari Worker/D1.
- FE menampilkan “Updated” dari header `x-generated-at` jika fetch sukses.
