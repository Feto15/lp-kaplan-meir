import argparse
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from lifelines import KaplanMeierFitter

# Konfigurasi sumber data via RPC (default Base).
RPC_URL = os.getenv("AERODROME_RPC_URL", "https://mainnet.base.org").strip()
# Pair default (bisa diganti via env).
PAIR_ADDRESS = os.getenv(
    "AERODROME_PAIR_ADDRESS", "0xb4885bc63399bf5518b994c1d0c153334ee579d0"
).lower()

# Desimal default jika auto-detect gagal.
DEFAULT_TOKEN0_DECIMALS = 18
DEFAULT_TOKEN1_DECIMALS = 6
TOKEN0_DECIMALS_ENV = os.getenv("AERODROME_TOKEN0_DECIMALS")
TOKEN1_DECIMALS_ENV = os.getenv("AERODROME_TOKEN1_DECIMALS")
INVERT_PRICE = os.getenv("INVERT_PRICE", "false").lower() == "true"

BASE_BLOCK_TIME_SEC = float(os.getenv("BASE_BLOCK_TIME_SEC", "2"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "48"))
SAMPLE_INTERVAL_SEC = int(os.getenv("SAMPLE_INTERVAL_SEC", "600"))
BATCH_SIZE = int(os.getenv("RPC_BATCH_SIZE", "10"))
BATCH_SLEEP = float(os.getenv("RPC_BATCH_SLEEP", "0.5"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PREFIX_ENV = os.getenv("CACHE_PREFIX")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
USE_CACHE_DEFAULT = os.getenv("USE_CACHE", "false").lower() == "true"
PAIR_LABEL = os.getenv("PAIR_LABEL", "").strip()
WORKER_INGEST_URL = os.getenv("WORKER_INGEST_URL", "").strip()
ENABLE_D1_INGEST = os.getenv("ENABLE_D1_INGEST", "false").lower() == "true"
WORKER_BASE_URL = os.getenv("WORKER_BASE_URL", "").strip()

WINDOWS = [100, 200, 300, 500]
HORIZONS = [6, 12, 24, 48]

BLOCK_CACHE: Dict[int, Dict] = {}
SLOT0_CACHE: Dict[int, int] = {}
DECIMALS_CACHE: Dict[str, Tuple[int, int]] = {}


def rpc_call(method: str, params: List, max_retries: int = 5) -> Dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
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


def _call_eth_call(to: str, data: str, block: str = "latest") -> Optional[str]:
    params = [{"to": to, "data": data}, block]
    res = rpc_call("eth_call", params)
    if not res or res == "0x":
        return None
    return res


def get_block(number: str) -> Dict:
    if number != "latest":
        try:
            num_int = int(number, 16)
        except ValueError:
            num_int = None
        if num_int is not None and num_int in BLOCK_CACHE:
            return BLOCK_CACHE[num_int]
    blk = rpc_call("eth_getBlockByNumber", [number, False])
    if number != "latest":
        try:
            num_int = int(number, 16)
            BLOCK_CACHE[num_int] = blk
        except ValueError:
            pass
    return blk


def get_latest_block() -> Tuple[int, int]:
    blk = get_block("latest")
    num = _hex_to_int(blk["number"])
    ts = _hex_to_int(blk["timestamp"])
    return num, ts


def find_block_for_timestamp(target_ts: int, latest_num: int, latest_ts: int) -> int:
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


def call_slot0(pair: str, block_num: int) -> Optional[int]:
    """Ambil sqrtPriceX96 dari slot0 (pool V3/CL)."""
    if block_num in SLOT0_CACHE:
        return SLOT0_CACHE[block_num]
    data = "0x3850c7bd"  # slot0()
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
    try:
        sqrt_price_x96 = int(res[2:66], 16)
        SLOT0_CACHE[block_num] = sqrt_price_x96
        return sqrt_price_x96
    except Exception:  # noqa: BLE001
        return None


def ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def cache_prefix_for_pair(pair_address: str) -> str:
    if CACHE_PREFIX_ENV and CACHE_PREFIX_ENV.strip():
        return CACHE_PREFIX_ENV.strip()
    sanitized = pair_address.lower().replace("0x", "")
    return f"cache_{sanitized[:6]}_{sanitized[-4:]}"


def cache_filepath(pair_address: str, lookback_hours: int, sample_interval_sec: int) -> str:
    ensure_cache_dir()
    prefix = cache_prefix_for_pair(pair_address)
    filename = f"{prefix}_v3_LOOKBACK{lookback_hours}_INTERVAL{sample_interval_sec}.json"
    return os.path.join(CACHE_DIR, filename)


def output_paths(pair_address: str) -> Tuple[str, str]:
    prefix = cache_prefix_for_pair(pair_address)
    csv_path = os.path.join(BASE_DIR, f"{prefix}_v3_survival.csv")
    json_path = os.path.join(BASE_DIR, f"{prefix}_v3_recommendations.json")
    return csv_path, json_path


def build_meta(pair_address: str) -> Dict[str, str]:
    label = PAIR_LABEL if PAIR_LABEL else cache_prefix_for_pair(pair_address)
    return {"pair_label": label, "pair_address": pair_address.lower(), "pool_type": "v3"}


def _read_address_from_data(data: str) -> Optional[str]:
    if not data or len(data) < 66:
        return None
    return "0x" + data[-40:]


def get_pair_tokens(pair_address: str) -> Tuple[Optional[str], Optional[str]]:
    pair = pair_address.lower()
    token0_data = _call_eth_call(pair, "0x0dfe1681")  # token0()
    token1_data = _call_eth_call(pair, "0xd21220a7")  # token1()
    return _read_address_from_data(token0_data), _read_address_from_data(token1_data)


def get_token_decimals(token_address: str) -> Optional[int]:
    data = _call_eth_call(token_address.lower(), "0x313ce567")  # decimals()
    if not data or len(data) < 66:
        return None
    try:
        return int(data[2:66], 16)
    except Exception:  # noqa: BLE001
        return None


def resolve_decimals(pair_address: str) -> Tuple[int, int]:
    pair = pair_address.lower()
    if pair in DECIMALS_CACHE:
        return DECIMALS_CACHE[pair]

    dec0 = None
    dec1 = None
    try:
        if TOKEN0_DECIMALS_ENV is not None:
            dec0 = int(TOKEN0_DECIMALS_ENV)
    except ValueError:
        dec0 = None
    try:
        if TOKEN1_DECIMALS_ENV is not None:
            dec1 = int(TOKEN1_DECIMALS_ENV)
    except ValueError:
        dec1 = None

    token0_addr, token1_addr = get_pair_tokens(pair)
    if dec0 is None and token0_addr:
        dec0 = get_token_decimals(token0_addr)
    if dec1 is None and token1_addr:
        dec1 = get_token_decimals(token1_addr)

    dec0 = dec0 if dec0 is not None else DEFAULT_TOKEN0_DECIMALS
    dec1 = dec1 if dec1 is not None else DEFAULT_TOKEN1_DECIMALS
    DECIMALS_CACHE[pair] = (dec0, dec1)
    return dec0, dec1


def load_cached_prices(path: str, start_ts: int, end_ts: int) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        loaded = pd.read_json(path)
        if isinstance(loaded, pd.DataFrame) and "timestamp" in loaded.columns:
            df = loaded
        else:
            df = pd.DataFrame(loaded.get("data", []))  # type: ignore[arg-type]
    except ValueError:
        return pd.DataFrame()
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    start_dt = pd.to_datetime(start_ts, unit="s", utc=True)
    end_dt = pd.to_datetime(end_ts, unit="s", utc=True)
    df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def save_cached_prices(df: pd.DataFrame, path: str) -> None:
    ensure_cache_dir()
    payload = {"meta": build_meta(PAIR_ADDRESS), "data": df.to_dict(orient="records")}
    pd.Series(payload).to_json(path, date_format="iso")


def get_price_data(
    pair_address: str = PAIR_ADDRESS,
    lookback_hours: int = LOOKBACK_HOURS,
    sample_interval_sec: int = SAMPLE_INTERVAL_SEC,
    use_cache: Optional[bool] = None,
    invert_price: bool = False,
    worker_base_url: Optional[str] = None,
    pair_label: Optional[str] = None,
) -> pd.DataFrame:
    """
    Ambil data harga historis via RPC (slot0) dengan sampling interval tetap.
    Harga dihitung: price = (sqrtPriceX96^2 / 2^192) * 10^(dec0-dec1)
    """
    pair_address = pair_address.lower()
    dec0, dec1 = resolve_decimals(pair_address)
    print(f"Using token decimals: token0={dec0}, token1={dec1}")
    use_cache_flag = USE_CACHE_DEFAULT if use_cache is None else use_cache
    invert_flag = INVERT_PRICE or invert_price
    cache_path = cache_filepath(pair_address, lookback_hours, sample_interval_sec)
    approx_now = int(time.time())
    approx_start_ts = approx_now - lookback_hours * 3600
    cached_df = load_cached_prices(cache_path, approx_start_ts, approx_now)
    if invert_flag and not cached_df.empty:
        cached_df = cached_df.copy()
        cached_df["price"] = 1 / cached_df["price"]
    if use_cache_flag and not cached_df.empty:
        print(f"Loading price data from cache: {cache_path}")
        return cached_df.reset_index(drop=True)

    last_ts_sec: Optional[int] = None
    if worker_base_url:
        try:
            pair_for_last = pair_label if pair_label else cache_prefix_for_pair(pair_address)
            resp = requests.get(
                f"{worker_base_url.rstrip('/')}/last_ts",
                params={"pair": pair_for_last},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                last_raw = int(data.get("last_ts"))
                last_ts_sec = int(last_raw / 1000) if last_raw > 1e12 else last_raw
                print(f"Found last_ts from D1 via Worker: {last_raw} (sec={last_ts_sec})")
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to fetch last_ts from Worker: {exc}")

    latest_num, latest_ts = get_latest_block()
    records: List[Dict] = []
    now = latest_ts
    start_ts = now - lookback_hours * 3600
    if last_ts_sec and last_ts_sec < now:
        aligned = last_ts_sec + sample_interval_sec
        target_ts = aligned if aligned >= start_ts else start_ts
        start_ts = min(start_ts, target_ts)
    else:
        target_ts = start_ts
    cached_df = load_cached_prices(cache_path, start_ts, now)
    if invert_flag and not cached_df.empty:
        cached_df = cached_df.copy()
        cached_df["price"] = 1 / cached_df["price"]
    if not cached_df.empty:
        print(f"Using cached history to minimize RPC calls ({len(cached_df)} rows)")

    call_counter = 0
    existing_ts: set[int] = set()
    if not cached_df.empty:
        existing_ts = {int(ts.timestamp()) for ts in cached_df["timestamp"]}

    while target_ts <= now:
        if target_ts in existing_ts:
            target_ts += sample_interval_sec
            continue
        blk_num = find_block_for_timestamp(target_ts, latest_num, latest_ts)
        sqrt_price_x96 = call_slot0(pair_address, blk_num)
        if sqrt_price_x96:
            price = (sqrt_price_x96 ** 2) / (2 ** 192) * (10 ** (dec0 - dec1))
            if invert_flag and price:
                price = 1 / price
            records.append(
                {
                    "timestamp": pd.to_datetime(target_ts, unit="s", utc=True),
                    "price": price,
                    "block": blk_num,
                }
            )
        call_counter += 1
        if BATCH_SIZE > 0 and call_counter % BATCH_SIZE == 0:
            time.sleep(BATCH_SLEEP)
        target_ts += sample_interval_sec

    df_parts = []
    if not cached_df.empty:
        df_parts.append(cached_df)
    if records:
        df_parts.append(pd.DataFrame(records))

    df = pd.concat(df_parts, ignore_index=True) if df_parts else pd.DataFrame()
    
    # Ensure we have the required columns
    if not df.empty and "timestamp" not in df.columns:
        print(f"[ERROR] DataFrame missing 'timestamp' column. Available columns: {list(df.columns)}")
        raise RuntimeError("DataFrame missing required 'timestamp' column")
    
    df = df.dropna()
    if not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    
    if df.empty:
        raise RuntimeError("Tidak ada data harga yang berhasil diambil dari RPC.")
    
    # Only save if we have valid data with timestamp column
    if "timestamp" in df.columns:
        save_cached_prices(df, cache_path)
        print(f"Saved updated price data to cache: {cache_path}")
    
    return df


def compute_ticks(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["price"] > 0].reset_index(drop=True)
    df["log_price"] = np.log(df["price"])
    df["tick"] = np.floor(df["log_price"] / math.log(1.0001)).astype(int)
    return df


def compute_survival(df: pd.DataFrame, W: int, horizon_hours: int) -> Optional[Dict]:
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

    ci_table = kmf.confidence_interval_
    ci_at = (
        ci_table.reindex(ci_table.index.union([horizon_hours]))
        .sort_index()
        .ffill()
        .loc[horizon_hours]
    )
    ci_low = float(ci_at.iloc[0])
    ci_high = float(ci_at.iloc[1])

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
        empirical_full = row["empirical_full"]
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


def save_recommendations_json(df: pd.DataFrame, path: str) -> Dict:
    ensure_cache_dir()
    payload = {"meta": build_meta(PAIR_ADDRESS), "data": df.to_dict(orient="records")}
    pd.Series(payload).to_json(path, date_format="iso")
    return payload


def _serialize_prices(df: pd.DataFrame) -> List[Dict]:
    records: List[Dict] = []
    for row in df.to_dict(orient="records"):
        ts = row.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts_str = ts.isoformat()
        else:
            ts_str = str(ts)
        rec: Dict = {"timestamp": ts_str, "price": float(row.get("price", 0))}
        blk = row.get("block")
        if blk is not None and not (isinstance(blk, float) and math.isnan(blk)):
            try:
                rec["block"] = int(blk)
            except Exception:  # noqa: BLE001
                pass
        records.append(rec)
    return records


def _serialize_prices_numeric_ts(df: pd.DataFrame) -> List[Dict]:
    """Serialize price rows with numeric epoch milliseconds for incremental append."""
    records: List[Dict] = []
    # Check if DataFrame has required columns
    if df.empty or "timestamp" not in df.columns:
        print(f"[WARNING] DataFrame missing timestamp column or empty. Columns: {list(df.columns) if not df.empty else 'empty'}")
        return records
    
    for row in df.to_dict(orient="records"):
        ts = row.get("timestamp")
        if ts is None:
            continue
            
        ts_num: Optional[int] = None
        if hasattr(ts, "timestamp"):
            ts_num = int(ts.timestamp() * 1000)
        else:
            try:
                ts_num = int(pd.to_datetime(ts).timestamp() * 1000)
            except Exception:  # noqa: BLE001
                ts_num = None
        if ts_num is None:
            continue
        rec: Dict = {"ts": ts_num, "price": float(row.get("price", 0))}
        blk = row.get("block")
        if blk is not None and not (isinstance(blk, float) and math.isnan(blk)):
            try:
                rec["block"] = int(blk)
            except Exception:  # noqa: BLE001
                pass
        records.append(rec)
    return records


def _worker_base_url() -> Optional[str]:
    if WORKER_BASE_URL:
        return WORKER_BASE_URL.rstrip("/")
    if WORKER_INGEST_URL:
        return WORKER_INGEST_URL.rstrip("/").rsplit("/", 1)[0]
    return None


def _post_worker(url: str, payload: Dict, timeout: int = 15) -> None:
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()


def maybe_ingest_to_worker(
    recs_payload: Dict,
    price_df: pd.DataFrame,
    lookback_hours: int,
    interval_sec: int,
) -> None:
    if not ENABLE_D1_INGEST or not WORKER_INGEST_URL:
        return
    base_url = _worker_base_url()
    pair_label = PAIR_LABEL or cache_prefix_for_pair(PAIR_ADDRESS)

    body = {
        "pair": pair_label,
        "lookback": lookback_hours,
        "interval_sec": interval_sec,
        "generated_at": int(time.time() * 1000),
        "payload": {
            "recommendations": recs_payload,
            "prices": {"meta": build_meta(PAIR_ADDRESS), "data": _serialize_prices(price_df)},
        },
    }
    try:
        # Legacy ingest for backward compatibility.
        _post_worker(WORKER_INGEST_URL, body)
        print(f"Pushed payload to Worker D1 (legacy ingest) {WORKER_INGEST_URL}.")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to push payload to Worker D1 (legacy ingest): {exc}")

    if not base_url:
        return

    # Append raw prices incrementally (UPSERT on primary key).
    try:
        price_rows = _serialize_prices_numeric_ts(price_df)
        if price_rows:
            _post_worker(f"{base_url}/append_prices", {"pair": pair_label, "rows": price_rows})
            print(f"Appended {len(price_rows)} price rows to D1 via Worker.")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to append prices to D1: {exc}")

    # Ingest survival run keyed by lookback+interval.
    try:
        survival_payload = {
          "pair": pair_label,
          "lookback": lookback_hours,
          "interval_sec": interval_sec,
          "generated_at": int(time.time() * 1000),
          "payload": {
              "recommendations": recs_payload,
              "prices": {"meta": build_meta(PAIR_ADDRESS), "data": _serialize_prices(price_df)},
          },
        }
        _post_worker(f"{base_url}/ingest_survival", survival_payload)
        print(f"Pushed survival payload to Worker D1 ({base_url}/ingest_survival).")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to push survival payload to Worker D1: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute survival estimates for V3/CL price data (slot0).")
    parser.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        help="Load data from cache if available (env USE_CACHE=true also works).",
    )
    parser.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help="Force fresh fetch and refresh cache.",
    )
    parser.add_argument(
        "--invert-price",
        dest="invert_price",
        action="store_true",
        help="Invert price output (1/price).",
    )
    parser.set_defaults(use_cache=None)
    return parser.parse_args()


def main() -> None:
    start_total = time.time()
    args = parse_args()
    csv_output, json_output = output_paths(PAIR_ADDRESS)
    print("Fetching price data (slot0)...")
    start_fetch = time.time()
    raw_df = get_price_data(
        use_cache=args.use_cache,
        invert_price=args.invert_price,
        worker_base_url=WORKER_BASE_URL,
    )
    fetch_elapsed = time.time() - start_fetch
    print(f"Fetched {len(raw_df)} rows from slot0 sampling/cache in {fetch_elapsed:.2f} sec")

    print("Computing ticks...")
    df_ticks = compute_ticks(raw_df)
    print(f"Data after tick computation: {len(df_ticks)} rows")

    print("Computing survival and recommendations...")
    recs_df = generate_recommendation(df_ticks)
    recs_df.to_csv(csv_output, index=False)
    recs_payload = save_recommendations_json(recs_df, json_output)
    print(f"Saved recommendations to {csv_output} and {json_output}")
    maybe_ingest_to_worker(recs_payload, raw_df, LOOKBACK_HOURS, SAMPLE_INTERVAL_SEC)
    print()
    print_recommendations(recs_df)
    total_elapsed = time.time() - start_total
    print(f"Total execution time: {total_elapsed:.2f} sec")


if __name__ == "__main__":
    main()
