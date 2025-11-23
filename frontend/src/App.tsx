import { Box, Chip, CircularProgress, Container, Stack, Typography } from "@mui/material";
import Grid from "@mui/material/GridLegacy";
import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { fetchPrices, fetchRecommendations } from "./api/data";
import { PriceChart } from "./components/PriceChart";
import { RecommendationsTable } from "./components/RecommendationsTable";
import { SurvivalChart } from "./components/SurvivalChart";
import type { PricePoint, Recommendation } from "./types";

function App() {
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [r, p] = await Promise.all([fetchRecommendations(), fetchPrices()]);
        setRecs(r);
        setPrices(p);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat data");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const horizons = useMemo(
    () => Array.from(new Set(recs.map((r) => r.horizon_hours))).sort((a, b) => a - b),
    [recs],
  );
  const accepted = recs.filter((r) => r.status === "ACCEPTED").length;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={2} mb={3}>
        <Typography variant="h4" fontWeight="bold">
          Survival Dashboard
        </Typography>
        <Typography color="text.secondary">
          Visualisasi harga dan rekomendasi survival. Pastikan file data tersedia di{" "}
          <code>frontend/public/data/</code>:
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Chip label="/data/survival_eth_usdc.csv (rekomendasi)" />
          <Chip label="/data/price.json (harga dari cache)" />
        </Stack>
      </Stack>

      {loading ? (
        <Box display="flex" alignItems="center" justifyContent="center" minHeight={200}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Typography color="error">Error: {error}</Typography>
      ) : (
        <Stack spacing={3}>
          <Stack direction="row" spacing={2} flexWrap="wrap">
            <Chip label={`Total rekomendasi: ${recs.length}`} color="primary" variant="outlined" />
            <Chip label={`Accepted: ${accepted}`} color="success" variant="outlined" />
          </Stack>

          <Grid container spacing={2}>
            <Grid item xs={12} md={7}>
              <PriceChart data={prices} />
            </Grid>
            <Grid item xs={12} md={5}>
              <RecommendationsTable data={recs} />
            </Grid>
          </Grid>

          <Typography variant="h6">Survival per horizon</Typography>
          <Grid container spacing={2}>
            {horizons.map((h) => (
              <Grid item xs={12} md={6} key={h}>
                <SurvivalChart horizon={h} data={recs} />
              </Grid>
            ))}
          </Grid>
        </Stack>
      )}
    </Container>
  );
}

export default App;
