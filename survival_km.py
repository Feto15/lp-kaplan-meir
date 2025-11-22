import math
import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from lifelines import KaplanMeierFitter


# Konfigurasi sumber data via RPC Base (gratis).
RPC_URL = os.getenv("AERODROME_RPC_URL", "https://mainnet.base.org").strip()
# Pair Aerodrome WETH/USDbC di Base.
PAIR_ADDRESS = os.getenv(
    "AERODROME_PAIR_ADDRESS", "0xb4885bc63399bf5518b994c1d0c153334ee579d0"
).lower()
# Token asumsi (bisa dikonfirmasi via token0/token1).
TOKEN0_DECIMALS = int(os.getenv("AERODROME_TOKEN0_DECIMALS", "18"))  # WETH
TOKEN1_DECIMALS = int(os.getenv("AERODROME_TOKEN1_DECIMALS", "6"))   # USDbC
# Target harga: WETH dalam USDbC => price = reserve1/reserve0 * 10^(dec0-dec1)

# Estimasi block time Base (detik) untuk konversi waktu->block.
BASE_BLOCK_TIME_SEC = float(os.getenv("BASE_BLOCK_TIME_SEC", "2"))
# Berapa jam data yang diambil ke belakang dari block terbaru.
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "72"))
# Interval sampling harga (detik).
SAMPLE_INTERVAL_SEC = int(os.getenv("SAMPLE_INTERVAL_SEC", "300"))

WINDOWS = [100, 200, 300, 500]
HORIZONS = [6, 12, 24, 48]
CSV_OUTPUT = "survival_eth_usdc.csv"


def rpc_call(method: str, params: List, max_retries: int = 5) -> Dict:
    """Minimal JSON-RPC call dengan retry sederhana (rate limit 429)."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(RPC_URL, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data["result"]
        except requests.HTTPError as exc:  # type: ignore[attr-defined]
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status == 429 and attempt < max_retries:
                time.sleep(1.5 ** (attempt - 1))
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(1.5 ** (attempt - 1))
    raise RuntimeError(f"RPC call failed after retries: {last_error}")


def _hex_to_int(h: str) -> int:
    return int(h, 16)


def get_block(number: str) -> Dict:
    return rpc_call("eth_getBlockByNumber", [number, False])


def get_latest_block() -> Tuple[int, int]:
    blk = get_block("latest")
    num = _hex_to_int(blk["number"])
    ts = _hex_to_int(blk["timestamp"])
    return num, ts


def find_block_for_timestamp(target_ts: int, latest_num: int, latest_ts: int) -> int:
    """Approximate block number for a target timestamp using iterative adjustment."""
    guess = max(0, int(latest_num - (latest_ts - target_ts) / BASE_BLOCK_TIME_SEC))
    for _ in range(10):
        blk = get_block(hex(guess))
        blk_ts = _hex_to_int(blk["timestamp"])
        diff = blk_ts - target_ts
        if abs(diff) <= 30:
            return guess
        adjust = int(diff / BASE_BLOCK_TIME_SEC)
        if adjust == 0:
            adjust = 1 if diff > 0 else -1
        guess = max(0, guess - adjust)
    return guess


def call_get_reserves(pair: str, block_num: int) -> Optional[Tuple[float, float]]:
    """Call getReserves() at specific block."""
    data = "0x0902f1ac"
    params = [
        {
            "to": pair,
            "data": data,
        },
        hex(block_num),
    ]
    res = rpc_call("eth_call", params)
    if not res or res == "0x":
        return None
    # getReserves returns three uint112/uint32 packed: 32 bytes each
    try:
        reserve0 = int(res[2:66], 16)
        reserve1 = int(res[66:130], 16)
        return float(reserve0), float(reserve1)
    except Exception:  # noqa: BLE001
        return None


def get_price_data(
    pair_address: str = PAIR_ADDRESS,
    lookback_hours: int = LOOKBACK_HOURS,
    sample_interval_sec: int = SAMPLE_INTERVAL_SEC,
) -> pd.DataFrame:
    """
    Ambil data harga historis via RPC dengan sampling interval tetap.
    Mengambil harga WETH/USDbC: price = reserve1/reserve0 * 10^(dec0-dec1).
    """
    pair_address = pair_address.lower()
    latest_num, latest_ts = get_latest_block()

    records: List[Dict] = []
    now = latest_ts
    start_ts = now - lookback_hours * 3600

    target_ts = start_ts
    while target_ts <= now:
        blk_num = find_block_for_timestamp(target_ts, latest_num, latest_ts)
        reserves = call_get_reserves(pair_address, blk_num)
        if reserves:
            r0, r1 = reserves
            if r0 > 0 and r1 > 0:
                price = (r1 / r0) * 10 ** (TOKEN0_DECIMALS - TOKEN1_DECIMALS)
                records.append(
                    {
                        "timestamp": pd.to_datetime(target_ts, unit="s", utc=True),
                        "price": price,
                        "block": blk_num,
                    }
                )
        target_ts += sample_interval_sec

    df = pd.DataFrame(records).dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        raise RuntimeError("Tidak ada data harga yang berhasil diambil dari RPC.")
    return df


def compute_ticks(df: pd.DataFrame) -> pd.DataFrame:
    """Compute log price and Uniswap V3 tick."""
    df = df.copy()
    df = df[df["price"] > 0].reset_index(drop=True)
    df["log_price"] = np.log(df["price"])
    df["tick"] = np.floor(df["log_price"] / math.log(1.0001)).astype(int)
    return df


def compute_survival(df: pd.DataFrame, W: int, horizon_hours: int) -> Optional[Dict]:
    """Compute Kaplan-Meier survival metrics for a given tick window W and horizon."""
    if df.empty:
        return None

    timestamps = df["timestamp"].to_numpy()
    ticks = df["tick"].to_numpy()
    prices = df["price"].to_numpy()

    last_time = timestamps[-1]
    horizon_delta = np.timedelta64(int(horizon_hours * 3600), "s")

    durations: List[float] = []
    events: List[int] = []
    full_followup: List[bool] = []

    n = len(df)
    for i in range(n):
        t_start = timestamps[i]
        center_tick = ticks[i]
        lower = center_tick - W
        upper = center_tick + W
        limit_time = t_start + horizon_delta

        has_full = limit_time <= last_time
        exit_time = limit_time if has_full else last_time
        event = 0

        j = i + 1
        while j < n and timestamps[j] <= limit_time:
            if ticks[j] < lower or ticks[j] > upper:
                event = 1
                exit_time = timestamps[j]
                break
            j += 1

        duration_hours = (exit_time - t_start) / np.timedelta64(1, "h")
        durations.append(float(duration_hours))
        events.append(int(event))
        full_followup.append(has_full)

    durations_arr = np.array(durations, dtype=float)
    events_arr = np.array(events, dtype=int)
    follow_arr = np.array(full_followup, dtype=bool)

    kmf = KaplanMeierFitter()
    kmf.fit(durations_arr, event_observed=events_arr)
    km_surv = float(kmf.predict(horizon_hours))
    ci_df = kmf.confidence_interval_at_times([horizon_hours])
    ci_low = float(ci_df.iloc[0, 0])
    ci_high = float(ci_df.iloc[0, 1])

    count_total = len(durations_arr)
    count_full = int(follow_arr.sum())
    survivors_full = int(((events_arr == 0) & (durations_arr >= horizon_hours) & follow_arr).sum())
    empirical_full = float(survivors_full / count_full) if count_full else float("nan")

    center_tick = int(np.median(ticks))
    tick_from = center_tick - W
    tick_to = center_tick + W
    price_from = float(np.power(1.0001, tick_from))
    price_to = float(np.power(1.0001, tick_to))
    price_center = float(np.power(1.0001, center_tick))
    percent_range_total = (price_to - price_from) / price_center * 100

    return {
        "W": W,
        "horizon_hours": horizon_hours,
        "count_total": count_total,
        "count_full_followup": count_full,
        "empirical_full": empirical_full,
        "km_surv": km_surv,
        "km_ci_low": ci_low,
        "km_ci_high": ci_high,
        "tick_from": tick_from,
        "tick_to": tick_to,
        "price_from": price_from,
        "price_to": price_to,
        "percent_range_total": percent_range_total,
    }


def generate_recommendation(df: pd.DataFrame) -> pd.DataFrame:
    """Generate recommendation DataFrame across windows and horizons."""
    rows: List[Dict] = []
    for horizon in HORIZONS:
        for window in WINDOWS:
            metrics = compute_survival(df, window, horizon)
            if not metrics:
                continue
            accepted = (
                metrics["km_surv"] >= 0.6
                and metrics["count_total"] >= 200
                and metrics["count_full_followup"] >= 100
            )
            reasons = []
            reasons.append("km_surv >= 0.6" if metrics["km_surv"] >= 0.6 else "km_surv < 0.6")
            reasons.append(
                "count_total >= 200" if metrics["count_total"] >= 200 else "count_total < 200"
            )
            reasons.append(
                "count_full >= 100"
                if metrics["count_full_followup"] >= 100
                else "count_full < 100"
            )

            row = {
                **metrics,
                "status": "ACCEPTED" if accepted else "REJECTED",
                "reason": " & ".join(reasons),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def print_recommendations(df: pd.DataFrame) -> None:
    """Pretty-print recommendations similar to requested format."""
    if df.empty:
        print("No recommendations available (empty DataFrame).")
        return
    df_sorted = df.sort_values(["horizon_hours", "W"])
    for _, row in df_sorted.iterrows():
        print(f"H={int(row['horizon_hours'])}h Recommendation ({row['status']}):")
        print(f"    W={int(row['W'])} ticks per side")
        print(f"    reason: {row['reason']}")
        print("    metrics:")
        print(f"        count_total: {int(row['count_total'])}")
        print(f"        count_full_followup: {int(row['count_full_followup'])}")
        empirical_full = row['empirical_full']
        empirical_str = "nan" if math.isnan(empirical_full) else f"{empirical_full:.6f}"
        print(f"        empirical_full: {empirical_str}")
        print(
            f"        km_surv: {row['km_surv']:.6f}  CI [{row['km_ci_low']:.6f} .. {row['km_ci_high']:.6f}]"
        )
        print(f"    ticks (from..to): {int(row['tick_from'])} .. {int(row['tick_to'])}")
        print(
            "    price bounds (from..to): "
            f"{row['price_from']:.6f} .. {row['price_to']:.6f}"
        )
        print(f"    percent_range_total: {row['percent_range_total']:.5f}%\n")


def main() -> None:
    print("Fetching price data from Base RPC...")
    raw_df = get_price_data()
    print(f"Fetched {len(raw_df)} rows from RPC sampling")

    print("Computing ticks...")
    df_ticks = compute_ticks(raw_df)
    print(f"Data after tick computation: {len(df_ticks)} rows")

    print("Computing survival and recommendations...")
    recs_df = generate_recommendation(df_ticks)
    recs_df.to_csv(CSV_OUTPUT, index=False)
    print(f"Saved recommendations to {CSV_OUTPUT}")
    print()
    print_recommendations(recs_df)


if __name__ == "__main__":
    main()
