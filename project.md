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
# export AERODROME_TOKEN0_DECIMALS="18"   # WETH
# export AERODROME_TOKEN1_DECIMALS="6"    # USDbC
# export LOOKBACK_HOURS="48"              # default 48 jam (disarankan 24–72 jam)
# export SAMPLE_INTERVAL_SEC="600"        # default 10 menit (disarankan 300–600 detik)
# export RPC_BATCH_SIZE="25"              # jeda setiap N panggilan eth_call
# export RPC_BATCH_SLEEP="0.25"           # durasi sleep antar batch (detik)

python3 survival_km.py
cd ..
```
Hasil CSV tersimpan di `backend/survival_eth_usdc.csv` dan cache di `backend/cache/`. Untuk dipakai FE, salin ke `frontend/public/data/`:
```bash
cp backend/survival_eth_usdc.csv frontend/public/data/
cp backend/cache/eth_usdc_prices_LOOKBACK48_INTERVAL600.json frontend/public/data/price.json
```
