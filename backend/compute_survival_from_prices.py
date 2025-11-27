"""
Compute survival/recommendation payload from historical prices stored in D1 (via Worker).

Expected flow:
- Prices sudah diappend ke tabel `prices` lewat Worker `/append_prices`.
- Script ini menarik window harga (lookback) via Worker `/prices`, hitung survival (Kaplan-Meier)
  memakai util yang sama dengan survival_km.py, lalu push hasil ke Worker `/ingest_survival`.

Env penting:
  WORKER_BASE_URL   : URL base Worker (mis. https://lp.example.workers.dev)
  PAIR_LABEL        : label pair di kolom `pair` tabel prices/survival_runs (wajib)
  LOOKBACK_HOURS    : berapa jam harga yang dibaca untuk hitung survival (default 48)
  SAMPLE_INTERVAL_SEC: interval sampling yang diasumsikan (default 600)
  POOL_TYPE         : "v2" / "v3" / lainnya (untuk meta)
  AERODROME_PAIR_ADDRESS: optional, untuk meta pair_address (fallback ke PAIR_LABEL)
"""

import os
import time
from typing import Dict, List

import pandas as pd
import numpy as np
import requests

from survival_km import compute_ticks, generate_recommendation

WORKER_BASE_URL = os.getenv("WORKER_BASE_URL", "").rstrip("/")
PAIR_LABEL = os.getenv("PAIR_LABEL", "").strip()
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "48"))
INTERVAL_SEC = int(os.getenv("SAMPLE_INTERVAL_SEC", "600"))
POOL_TYPE = os.getenv("POOL_TYPE", "v2").strip() or "v2"
PAIR_ADDRESS = os.getenv("AERODROME_PAIR_ADDRESS", "").strip().lower()


def require_worker_base() -> str:
    if not WORKER_BASE_URL:
        raise RuntimeError("WORKER_BASE_URL belum di-set (contoh: https://lp.example.workers.dev)")
    return WORKER_BASE_URL


def effective_pair_label() -> str:
    if PAIR_LABEL:
        return PAIR_LABEL
    if PAIR_ADDRESS:
        return PAIR_ADDRESS.replace("0x", "")[:6]
    raise RuntimeError("PAIR_LABEL belum di-set dan tidak ada AERODROME_PAIR_ADDRESS untuk fallback")


def meta_payload(pair_label: str) -> Dict[str, str]:
    pair_address = PAIR_ADDRESS if PAIR_ADDRESS else pair_label
    return {
        "pair_label": pair_label,
        "pair_address": pair_address.lower(),
        "pool_type": POOL_TYPE,
    }


def fetch_prices_from_worker(pair_label: str, lookback_hours: int) -> pd.DataFrame:
    base_url = require_worker_base()
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - lookback_hours * 3600 * 1000
    params = {"pair": pair_label, "start_ts": start_ms, "end_ts": end_ms}
    resp = requests.get(f"{base_url}/prices", params=params, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"Gagal fetch harga dari Worker: {resp.status_code} {resp.text}")
    payload = resp.json()
    rows: List[Dict] = payload.get("data", [])
    if not rows:
        raise RuntimeError("Tidak ada data harga dikembalikan Worker.")
    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    elif "ts" in df.columns:
        df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True, errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        raise RuntimeError("Data harga kosong setelah parsing.")
    return df


def serialize_prices_iso(df: pd.DataFrame) -> List[Dict]:
    records: List[Dict] = []
    for row in df.to_dict(orient="records"):
        ts = row.get("timestamp")
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        rec: Dict = {"timestamp": ts_str, "price": float(row.get("price", 0))}
        blk = row.get("block")
        if blk is not None and not (isinstance(blk, float) and pd.isna(blk)):
            try:
                rec["block"] = int(blk)
            except Exception:  # noqa: BLE001
                pass
        records.append(rec)
    return records


def dataframe_to_records(df: pd.DataFrame) -> List[Dict]:
    clean = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
    return clean.to_dict(orient="records")


def push_survival_to_worker(pair_label: str, lookback_hours: int, interval_sec: int, payload: Dict) -> None:
    base_url = require_worker_base()
    body = {
        "pair": pair_label,
        "lookback": lookback_hours,
        "interval_sec": interval_sec,
        "generated_at": int(time.time() * 1000),
        "payload": payload,
    }
    resp = requests.post(f"{base_url}/ingest_survival", json=body, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"Gagal push survival ke Worker: {resp.status_code} {resp.text}")


def main() -> None:
    start_ts = time.time()
    pair_label = effective_pair_label()
    print(f"Fetching prices from Worker for pair={pair_label}, lookback={LOOKBACK_HOURS}h...")
    price_df = fetch_prices_from_worker(pair_label, LOOKBACK_HOURS)
    print(f"Fetched {len(price_df)} price rows.")

    print("Computing ticks and survival...")
    df_ticks = compute_ticks(price_df)
    recs_df = generate_recommendation(df_ticks)

    meta = meta_payload(pair_label)
    recommendations = {"meta": meta, "data": dataframe_to_records(recs_df)}
    prices_payload = {"meta": meta, "data": serialize_prices_iso(price_df)}
    survival_payload = {
        "recommendations": recommendations,
        "prices": prices_payload,
    }
    push_survival_to_worker(pair_label, LOOKBACK_HOURS, INTERVAL_SEC, survival_payload)
    elapsed = time.time() - start_ts
    print(f"Done. Survival payload pushed to Worker. Elapsed: {elapsed:.2f} sec.")


if __name__ == "__main__":
    main()
