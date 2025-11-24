import type { PricePoint, Recommendation } from "../types";

const DEFAULT_RECOMMENDATION_URL = "/data/recommendations.json";
const DEFAULT_PRICE_URL = "/data/price.json";

const parseNumber = (value: unknown): number => {
  if (value === undefined || value === null || value === "" || value === "nan") {
    return Number.NaN;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NaN;
};

export async function fetchRecommendations(
  url: string = DEFAULT_RECOMMENDATION_URL,
): Promise<Recommendation[]> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Gagal mengambil rekomendasi: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as Array<Record<string, unknown>>;
  return data
    .map((row) => ({
      W: parseNumber(row.W),
      horizon_hours: parseNumber(row.horizon_hours),
      status: String(row.status ?? ""),
      reason: String(row.reason ?? ""),
      count_total: parseNumber(row.count_total),
      count_full_followup: parseNumber(row.count_full_followup),
      empirical_full: parseNumber(row.empirical_full),
      km_surv: parseNumber(row.km_surv),
      km_ci_low: parseNumber(row.km_ci_low),
      km_ci_high: parseNumber(row.km_ci_high),
      tick_from: parseNumber(row.tick_from),
      tick_to: parseNumber(row.tick_to),
      price_from: parseNumber(row.price_from),
      price_to: parseNumber(row.price_to),
      percent_range_total: parseNumber(row.percent_range_total),
    }))
    .filter((row) => Number.isFinite(row.W) && Number.isFinite(row.horizon_hours));
}

export async function fetchPrices(url: string = DEFAULT_PRICE_URL): Promise<PricePoint[]> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Gagal mengambil price data: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as Array<Record<string, unknown>>;
  return data
    .map((row) => ({
      timestamp: String(row.timestamp ?? ""),
      price: parseNumber(row.price),
      block: row.block ? Number(row.block) : undefined,
    }))
    .filter((row) => row.timestamp && Number.isFinite(row.price));
}
