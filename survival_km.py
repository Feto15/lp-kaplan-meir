import math
import os
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from lifelines import KaplanMeierFitter


# Konfigurasi sumber data Aerodrome subgraph (Base).
# Wajib ganti SUBGRAPH_URL ke endpoint subgraph Aerodrome yang valid.
# Contoh (isi sesuai dokumentasi Aerodrome/Base):
# SUBGRAPH_URL = "https://api.studio.thegraph.com/query/<project-id>/aerodrome-base/version/latest"
SUBGRAPH_URL = os.getenv("AERODROME_SUBGRAPH_URL", "").strip()
# Pair address Aerodrome WETH/USDbC di Base (lowercase).
PAIR_ADDRESS = os.getenv(
    "AERODROME_PAIR_ADDRESS", "0xb4885bc63399bf5518b994c1d0c153334ee579d0"
).lower()
# Token mana yang dipakai sebagai base harga (token0 atau token1).
# Jika ingin harga WETH dalam USDbC dan WETH adalah token0, gunakan "token0Price".
# Sesuaikan dengan schema subgraph (token0Price/token1Price).
PRICE_FIELD = os.getenv("AERODROME_PRICE_FIELD", "token0Price")

WINDOWS = [100, 200, 300, 500]
HORIZONS = [6, 12, 24, 48]
CSV_OUTPUT = "survival_eth_usdc.csv"


def _require_subgraph_url() -> None:
    if not SUBGRAPH_URL:
        raise RuntimeError(
            "SUBGRAPH_URL kosong. Set env AERODROME_SUBGRAPH_URL atau edit konstanta SUBGRAPH_URL."
        )


def _run_subgraph_query(query: str, variables: Dict, max_retries: int = 5) -> Dict:
    """Execute GraphQL query with simple retry/backoff."""
    _require_subgraph_url()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "survival-km-script/1.0",
    }
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                SUBGRAPH_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(1.5 ** (attempt - 1))
    raise RuntimeError(f"Gagal query subgraph: {last_error}")


def get_price_data(
    pair_address: str = PAIR_ADDRESS,
    price_field: str = PRICE_FIELD,
    max_pages: int = 20,
    page_size: int = 500,
) -> pd.DataFrame:
    """
    Ambil data harga historis dari Aerodrome subgraph (Base).

    Menggunakan entitas pairHourData (schema Solidly/Aerodrome) atau swap snapshot
    bergantung ketersediaan field. Disini diasumsikan ada:
      - pairHourDatas dengan field: periodStartUnix, token0Price, token1Price
    """
    pair_address = pair_address.lower()
    field = price_field

    query = """
    query ($pair: String!, $skip: Int!, $first: Int!) {
      pairHourDatas(
        where: { pair: $pair }
        orderBy: periodStartUnix
        orderDirection: asc
        skip: $skip
        first: $first
      ) {
        periodStartUnix
        token0Price
        token1Price
        reserve0
        reserve1
      }
    }
    """

    rows: List[Dict] = []
    for page in range(max_pages):
        skip = page * page_size
        data = _run_subgraph_query(
            query, {"pair": pair_address, "skip": skip, "first": page_size}
        )
        items = data.get("pairHourDatas") or []
        if not items:
            break
        rows.extend(items)
        if len(items) < page_size:
            break

    if not rows:
        raise RuntimeError("pairHourDatas kosong dari subgraph.")

    records = []
    for item in rows:
        ts = item.get("periodStartUnix")
        if ts is None:
            continue
        try:
            ts_int = int(ts)
        except (TypeError, ValueError):
            continue

        price_val = item.get(field)
        alt_price = None
        if price_val is not None:
            try:
                alt_price = float(price_val)
            except (TypeError, ValueError):
                alt_price = None

        # Jika field utama kosong, coba derive dari reserve0/reserve1.
        if alt_price is None:
            r0 = item.get("reserve0")
            r1 = item.get("reserve1")
            try:
                if r0 is not None and r1 is not None and float(r0) > 0:
                    alt_price = float(r1) / float(r0)
            except (TypeError, ValueError, ZeroDivisionError):
                alt_price = None

        if alt_price is None:
            continue

        records.append(
            {
                "timestamp": pd.to_datetime(ts_int, unit="s", utc=True),
                "price": float(alt_price),
            }
        )

    df = pd.DataFrame(records).dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        raise RuntimeError("Parsed DataFrame kosong setelah pemrosesan subgraph.")
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
    print("Fetching price data from Aerodrome subgraph...")
    raw_df = get_price_data()
    print(f"Fetched {len(raw_df)} rows from subgraph")

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
