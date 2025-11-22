# Survival Rate Kaplan-Meier – Aerodrome ETH/USDC (Base)

Program Python untuk menghitung survival probability harga dalam rentang tick (Uniswap V3) menggunakan Kaplan-Meier estimator, berbasis data historis dari **Aerodrome subgraph (Base)**.

## Fitur utama
- Ambil data harga pool Aerodrome WETH/USDbC (pair `0xb4885bc63399bf5518b994c1d0c153334ee579d0`, chain `base`) dari Aerodrome subgraph (GraphQL) dengan retry + backoff sederhana.
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
export AERODROME_SUBGRAPH_URL="https://<subgraph-endpoint>"
# opsional: override jika perlu
# export AERODROME_PAIR_ADDRESS="0xb4885bc63399bf5518b994c1d0c153334ee579d0"
# export AERODROME_PRICE_FIELD="token0Price"  # atau token1Price sesuai orientasi harga di subgraph

python3 survival_km.py
```
Hasil CSV tersimpan di `survival_eth_usdc.csv`, dan output rekomendasi dicetak di terminal.
