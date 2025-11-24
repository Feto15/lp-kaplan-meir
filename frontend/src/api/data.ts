import type { Manifest, PricePoint, PriceResponse, Recommendation, RecommendationResponse } from "../types";

const DEFAULT_RECOMMENDATION_URL = "/data/recommendations.json";
const DEFAULT_PRICE_URL = "/data/price.json";
const DATA_BASE = (import.meta.env.VITE_DATA_BASE || "").replace(/\/+$/, "");

const resolveUrl = (path: string): string => {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  return `${DATA_BASE}${path}`;
};

async function fetchWithFallback(primary: string, fallback?: string): Promise<Response> {
  const primaryUrl = resolveUrl(primary);
  try {
    const res = await fetch(primaryUrl);
    if (res.ok) return res;
    if (!fallback || fallback === primary) throw new Error(`Request failed: ${res.status}`);
  } catch (err) {
    if (!fallback || fallback === primary) throw err;
  }

  const fbUrl = resolveUrl(fallback);
  const resFallback = await fetch(fbUrl);
  if (!resFallback.ok) {
    throw new Error(`Fallback request failed: ${resFallback.status} ${resFallback.statusText}`);
  }
  return resFallback;
}

export async function fetchManifest(): Promise<Manifest> {
  const res = await fetch("/data/manifest.json");
  if (!res.ok) {
    throw new Error(`Gagal mengambil manifest: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as Manifest;
}

const parseNumber = (value: unknown): number => {
  if (value === undefined || value === null || value === "" || value === "nan") {
    return Number.NaN;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NaN;
};

export async function fetchRecommendations(
  url: string = DEFAULT_RECOMMENDATION_URL,
  fallbackUrl: string = DEFAULT_RECOMMENDATION_URL,
): Promise<RecommendationResponse> {
  const res = await fetchWithFallback(url, fallbackUrl);
  const generatedAtHeader = res.headers.get("x-generated-at");
  const generatedAt = generatedAtHeader ? Number(generatedAtHeader) : undefined;
  const json = await res.json();
  
  let rawData: Array<Record<string, unknown>> = [];
  let meta: RecommendationResponse["meta"] = undefined;

  if (Array.isArray(json)) {
    rawData = json as Array<Record<string, unknown>>;
  } else if (typeof json === "object" && json !== null && "data" in json) {
    rawData = (json as { data: Array<Record<string, unknown>> }).data;
    meta = (json as { meta: RecommendationResponse["meta"] }).meta;
  }

  const data = rawData
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

  return { meta, data, generatedAt };
}

export async function fetchPrices(
  url: string = DEFAULT_PRICE_URL,
  fallbackUrl: string = DEFAULT_PRICE_URL,
): Promise<PriceResponse> {
  const res = await fetchWithFallback(url, fallbackUrl);
  const generatedAtHeader = res.headers.get("x-generated-at");
  const generatedAt = generatedAtHeader ? Number(generatedAtHeader) : undefined;
  const json = await res.json();

  let rawData: Array<Record<string, unknown>> = [];

  if (Array.isArray(json)) {
    rawData = json as Array<Record<string, unknown>>;
  } else if (typeof json === "object" && json !== null && "data" in json) {
    rawData = (json as { data: Array<Record<string, unknown>> }).data;
  }

  const data = rawData
    .map((row) => ({
      timestamp: String(row.timestamp ?? ""),
      price: parseNumber(row.price),
      block: row.block ? Number(row.block) : undefined,
    }))
    .filter((row) => row.timestamp && Number.isFinite(row.price));

  return { data, generatedAt };
}
