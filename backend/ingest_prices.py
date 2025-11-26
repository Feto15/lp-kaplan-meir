"""
Ingest-only script to fetch prices from RPC and push to Worker/D1 via /append_prices.

Supports both V2 (getReserves) and V3/CL (slot0) by switching POOL_TYPE env:
  POOL_TYPE=v2 (default) uses survival_km.py utilities.
  POOL_TYPE=v3 uses survival_km_v3.py utilities.

Env vars:
  WORKER_BASE_URL     : base URL Worker (https://...workers.dev) or leave empty to derive from WORKER_INGEST_URL
  WORKER_INGEST_URL   : legacy ingest URL; base URL diambil dari sini jika WORKER_BASE_URL kosong
  PAIR_LABEL          : label pair untuk kolom `pair` di tabel prices (default: cache prefix dari pair address)
  AERODROME_PAIR_ADDRESS : alamat pair on-chain
  LOOKBACK_HOURS      : berapa jam ke belakang (default 48)
  SAMPLE_INTERVAL_SEC : interval sampling detik (default 600)
  USE_CACHE           : reuse cache lokal (true/false, default false)
  RPC_BATCH_SIZE/RPC_BATCH_SLEEP: batching RPC (default 10 / 0.5 jika tidak di-set).
"""

import os
import sys
from typing import Dict, List, Optional, Tuple, Type

import pandas as pd
import requests

# Ensure batch defaults even if env kosong (biar tidak tergantung util lain).
if "RPC_BATCH_SIZE" not in os.environ:
    os.environ["RPC_BATCH_SIZE"] = "100"
if "RPC_BATCH_SLEEP" not in os.environ:
    os.environ["RPC_BATCH_SLEEP"] = "0.5"

POOL_TYPE = os.getenv("POOL_TYPE", "v2").lower().strip() or "v2"
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "48"))
SAMPLE_INTERVAL_SEC = int(os.getenv("SAMPLE_INTERVAL_SEC", "600"))
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL", "").rstrip("/")
WORKER_INGEST_URL = os.getenv("WORKER_INGEST_URL", "").rstrip("/")
PAIR_LABEL_ENV = os.getenv("PAIR_LABEL", "").strip()

# Late imports based on pool type
if POOL_TYPE == "v3":
    import survival_km_v3 as skm  # type: ignore
else:
    import survival_km as skm  # type: ignore


def worker_base_url() -> str:
    if WORKER_BASE_URL:
        return WORKER_BASE_URL
    if WORKER_INGEST_URL:
        return WORKER_INGEST_URL.rsplit("/", 1)[0]
    raise RuntimeError("Set WORKER_BASE_URL atau WORKER_INGEST_URL terlebih dahulu.")


def pair_label() -> str:
    if PAIR_LABEL_ENV:
        return PAIR_LABEL_ENV
    # fallback: prefix from pair address util
    addr = getattr(skm, "PAIR_ADDRESS", "").lower()
    return skm.cache_prefix_for_pair(addr)  # type: ignore


def fetch_prices() -> pd.DataFrame:
    base_url = worker_base_url()
    label = pair_label()
    # get_price_data util mendukung param worker_base_url untuk incremental berdasarkan last_ts
    return skm.get_price_data(
        pair_address=getattr(skm, "PAIR_ADDRESS", None),
        lookback_hours=LOOKBACK_HOURS,
        sample_interval_sec=SAMPLE_INTERVAL_SEC,
        use_cache=None,  # ikuti USE_CACHE_DEFAULT dari util
        worker_base_url=base_url,
    )


def serialize_prices_numeric_ts(df: pd.DataFrame) -> List[Dict]:
    return skm._serialize_prices_numeric_ts(df)  # type: ignore


def append_prices(rows: List[Dict]) -> None:
    base_url = worker_base_url()
    label = pair_label()
    payload = {"pair": label, "rows": rows}
    resp = requests.post(f"{base_url}/append_prices", json=payload, timeout=20)
    resp.raise_for_status()


def main() -> None:
    start_ts = pd.Timestamp.utcnow()
    print(f"[ingest] pool_type={POOL_TYPE}, lookback={LOOKBACK_HOURS}h, interval={SAMPLE_INTERVAL_SEC}s")
    df = fetch_prices()
    if df.empty:
        print("[ingest] Tidak ada data harga yang diambil.")
        return
    rows = serialize_prices_numeric_ts(df)
    if not rows:
        print("[ingest] Tidak ada baris yang valid untuk diappend.")
        return
    append_prices(rows)
    elapsed = (pd.Timestamp.utcnow() - start_ts).total_seconds()
    print(f"[ingest] Appended {len(rows)} price rows to Worker/D1 for pair={pair_label()}. Elapsed: {elapsed:.2f} sec.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"[ingest] ERROR: {exc}")
        sys.exit(1)
