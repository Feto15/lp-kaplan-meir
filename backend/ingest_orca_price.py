"""
Fetch current price for a specific Orca Whirlpool pool and append it to Worker/D1 via /append_prices.

This script is polling-only (single snapshot per run); schedule it periodically to build history.

Env vars:
  WORKER_BASE_URL         : https://...workers.dev (atau derive dari WORKER_INGEST_URL)
  WORKER_INGEST_URL       : legacy ingest URL (dipakai jika WORKER_BASE_URL kosong)
  PAIR_LABEL              : label pair untuk kolom `pair` di tabel prices (wajib)
  ORCA_WHIRLPOOL_ADDRESS  : alamat Whirlpool (mis. Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE) (wajib)
  ORCA_API_URL            : opsional, default https://api.mainnet.orca.so/v1/whirlpool/list

Field harga diambil dari API Orca: jika tersedia `price`, gunakan itu; jika tidak, coba hitung
dari sqrtPriceX64 dan desimal token (tokenA/tokenB).
"""

import math
import os
import sys
import time
from typing import Dict, List, Optional

import requests

WORKER_BASE_URL = os.getenv("WORKER_BASE_URL", "").rstrip("/")
WORKER_INGEST_URL = os.getenv("WORKER_INGEST_URL", "").rstrip("/")
PAIR_LABEL = os.getenv("PAIR_LABEL", "").strip()
ORCA_WHIRLPOOL_ADDRESS = os.getenv("ORCA_WHIRLPOOL_ADDRESS", "").strip()
ORCA_API_URL = os.getenv("ORCA_API_URL", "https://api.mainnet.orca.so/v1/whirlpool/list").strip()


def worker_base_url() -> str:
    if WORKER_BASE_URL:
        return WORKER_BASE_URL
    if WORKER_INGEST_URL:
        return WORKER_INGEST_URL.rsplit("/", 1)[0]
    raise RuntimeError("Set WORKER_BASE_URL atau WORKER_INGEST_URL terlebih dahulu.")


def fetch_whirlpool_entry(address: str) -> Dict:
    resp = requests.get(ORCA_API_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    pools = None
    if isinstance(data, dict):
        pools = data.get("whirlpools") or data.get("data") or data.get("items")
    if pools is None:
        pools = data
    if not isinstance(pools, list):
        raise RuntimeError("Response Orca tidak berisi list whirlpools.")
    address_low = address.lower()
    for item in pools:
        addr = (
            str(item.get("address") or item.get("whirlpoolAddress") or "")
            .strip()
            .lower()
        )
        if addr == address_low:
            return item
    raise RuntimeError(f"Whirlpool {address} tidak ditemukan di response Orca.")


def compute_price_from_entry(entry: Dict) -> float:
    # Gunakan field price jika ada
    price_field = entry.get("price")
    if price_field is not None:
        try:
            return float(price_field)
        except Exception:  # noqa: BLE001
            pass

    sqrt_raw = entry.get("sqrtPrice") or entry.get("sqrtPriceX64")
    token_a = entry.get("tokenA") or {}
    token_b = entry.get("tokenB") or {}
    dec_a = int(token_a.get("decimals") or token_a.get("decimalPlaces") or 0)
    dec_b = int(token_b.get("decimals") or token_b.get("decimalPlaces") or 0)
    if sqrt_raw is None:
        raise RuntimeError("Tidak ada field price maupun sqrtPrice untuk dihitung.")
    try:
        sqrt_int = int(sqrt_raw)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Gagal parse sqrtPrice: {exc}") from exc
    # Konversi sqrtPriceX64 -> price tokenB per tokenA
    price = (sqrt_int / 2 ** 64) ** 2 * 10 ** (dec_a - dec_b)
    return float(price)


def append_prices(rows: List[Dict]) -> None:
    base_url = worker_base_url()
    payload = {"pair": PAIR_LABEL, "rows": rows}
    resp = requests.post(f"{base_url}/append_prices", json=payload, timeout=15)
    resp.raise_for_status()


def main() -> None:
    if not PAIR_LABEL:
        raise RuntimeError("PAIR_LABEL harus diisi.")
    if not ORCA_WHIRLPOOL_ADDRESS:
        raise RuntimeError("ORCA_WHIRLPOOL_ADDRESS harus diisi.")

    print(f"[ingest-orca] Fetching price for whirlpool={ORCA_WHIRLPOOL_ADDRESS} ...")
    entry = fetch_whirlpool_entry(ORCA_WHIRLPOOL_ADDRESS)
    price = compute_price_from_entry(entry)
    ts_ms = int(time.time() * 1000)
    rows = [{"ts": ts_ms, "price": price}]
    append_prices(rows)
    print(f"[ingest-orca] Appended price={price} at ts={ts_ms} for pair={PAIR_LABEL}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"[ingest-orca] ERROR: {exc}")
        sys.exit(1)
