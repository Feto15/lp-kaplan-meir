"""
Ingest price rows (e.g., from Solana data source) into Worker/D1 via /append_prices.

Assumsi sumber data sudah menyediakan deret waktu harga (timestamp + price) dalam JSON
atau file lokal, sehingga script ini tidak melakukan RPC Solana langsung.

Env vars:
  WORKER_BASE_URL      : base URL Worker (https://...workers.dev) atau derive dari WORKER_INGEST_URL
  WORKER_INGEST_URL    : legacy ingest URL; dipakai untuk derive base URL jika WORKER_BASE_URL kosong
  PAIR_LABEL           : label pair yang akan dipakai sebagai kolom `pair` di tabel prices
  PRICE_SOURCE_URL     : optional; endpoint HTTP yang mengembalikan array objek {timestamp|ts, price, block?}
  PRICE_SOURCE_FILE    : optional; path file JSON/CSV dengan kolom timestamp|ts dan price

Prioritas sumber data: PRICE_SOURCE_URL jika ada; kalau tidak, PRICE_SOURCE_FILE.
Timestamp boleh ISO atau epoch ms/seconds; script normalisasi ke epoch ms.
"""

import json
import os
import sys
from typing import Dict, List, Optional

import pandas as pd
import requests

WORKER_BASE_URL = os.getenv("WORKER_BASE_URL", "").rstrip("/")
WORKER_INGEST_URL = os.getenv("WORKER_INGEST_URL", "").rstrip("/")
PAIR_LABEL = os.getenv("PAIR_LABEL", "").strip() or "UNKNOWN_PAIR"
PRICE_SOURCE_URL = os.getenv("PRICE_SOURCE_URL", "").strip()
PRICE_SOURCE_FILE = os.getenv("PRICE_SOURCE_FILE", "").strip()


def worker_base_url() -> str:
    if WORKER_BASE_URL:
        return WORKER_BASE_URL
    if WORKER_INGEST_URL:
        return WORKER_INGEST_URL.rsplit("/", 1)[0]
    raise RuntimeError("Set WORKER_BASE_URL atau WORKER_INGEST_URL terlebih dahulu.")


def load_from_url(url: str) -> List[Dict]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        raise RuntimeError("Response bukan array.")
    return data  # type: ignore[return-value]


def load_from_file(path: str) -> List[Dict]:
    if not os.path.exists(path):
        raise RuntimeError(f"File tidak ditemukan: {path}")
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
        return df.to_dict(orient="records")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        raise RuntimeError("File tidak berisi array.")
    return data  # type: ignore[return-value]


def normalize_rows(raw_rows: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw_rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    elif "ts" in df.columns:
        # asumsi ms jika > 10^12, else sec
        df["timestamp"] = pd.to_datetime(df["ts"].apply(_ts_to_datetime), utc=True, errors="coerce")
    else:
        raise RuntimeError("Tidak ada kolom timestamp/ts.")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "block" in df.columns:
        df["block"] = pd.to_numeric(df["block"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _ts_to_datetime(val: object) -> Optional[pd.Timestamp]:
    try:
        num = float(val)
    except Exception:
        return pd.NaT
    # detect ms vs sec
    if num > 1e12:
        return pd.to_datetime(num, unit="ms", utc=True, errors="coerce")
    return pd.to_datetime(num, unit="s", utc=True, errors="coerce")


def serialize_numeric_ts(df: pd.DataFrame) -> List[Dict]:
    rows: List[Dict] = []
    for row in df.to_dict(orient="records"):
        ts = row.get("timestamp")
        ts_ms: Optional[int] = None
        if hasattr(ts, "timestamp"):
            ts_ms = int(ts.timestamp() * 1000)
        if ts_ms is None:
            continue
        rec: Dict = {"ts": ts_ms, "price": float(row.get("price", 0))}
        blk = row.get("block")
        if blk is not None and not pd.isna(blk):
            rec["block"] = int(blk)
        rows.append(rec)
    return rows


def append_prices(rows: List[Dict]) -> None:
    base_url = worker_base_url()
    payload = {"pair": PAIR_LABEL, "rows": rows}
    resp = requests.post(f"{base_url}/append_prices", json=payload, timeout=30)
    resp.raise_for_status()


def main() -> None:
    start = pd.Timestamp.utcnow()
    if PRICE_SOURCE_URL:
        raw = load_from_url(PRICE_SOURCE_URL)
    elif PRICE_SOURCE_FILE:
        raw = load_from_file(PRICE_SOURCE_FILE)
    else:
        raise RuntimeError("Set salah satu PRICE_SOURCE_URL atau PRICE_SOURCE_FILE.")

    df = normalize_rows(raw)
    if df.empty:
        print("[ingest-solana] Tidak ada baris harga setelah normalisasi.")
        return

    rows = serialize_numeric_ts(df)
    if not rows:
        print("[ingest-solana] Tidak ada baris valid untuk append.")
        return

    append_prices(rows)
    elapsed = (pd.Timestamp.utcnow() - start).total_seconds()
    print(f"[ingest-solana] Appended {len(rows)} rows to Worker/D1 for pair={PAIR_LABEL}. Elapsed: {elapsed:.2f} sec.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"[ingest-solana] ERROR: {exc}")
        sys.exit(1)
