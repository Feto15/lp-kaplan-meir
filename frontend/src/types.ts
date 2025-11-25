export interface PricePoint {
  timestamp: string;
  price: number;
  block?: number;
}

export interface Recommendation {
  W: number;
  horizon_hours: number;
  status: string;
  reason: string;
  count_total: number;
  count_full_followup: number;
  empirical_full: number;
  km_surv: number;
  km_ci_low: number;
  km_ci_high: number;
  tick_from: number;
  tick_to: number;
  price_from: number;
  price_to: number;
  percent_range_total: number;
}

export interface RecommendationMeta {
  pair_label: string;
  pair_address: string;
  pool_type: string;
}

export interface RecommendationResponse {
  meta?: RecommendationMeta;
  data: Recommendation[];
  generatedAt?: number;
}

export interface Dataset {
  id: string;
  name: string;
  recommendations: string;
  price: string;
  pair?: string;
  lookback?: number;
  interval_sec?: number;
}

export interface Manifest {
  datasets: Dataset[];
}

export interface PriceResponse {
  data: PricePoint[];
  generatedAt?: number;
}
