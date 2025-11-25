import {
  AppBar,
  Box,
  Chip,
  CircularProgress,
  Container,
  createTheme,
  CssBaseline,
  FormControl,
  MenuItem,
  Paper,
  Select,
  type SelectChangeEvent,
  Stack,
  ThemeProvider,
  Toolbar,
  Typography,
} from "@mui/material";
import Grid from "@mui/material/GridLegacy";
import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { fetchManifest, fetchPrices, fetchRecommendations } from "./api/data";
import { PriceChart } from "./components/PriceChart";
import { RecommendationsTable } from "./components/RecommendationsTable";
import { SurvivalChart } from "./components/SurvivalChart";
import type { Dataset, PricePoint, Recommendation, RecommendationMeta } from "./types";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import DashboardIcon from "@mui/icons-material/Dashboard";

function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [meta, setMeta] = useState<RecommendationMeta | undefined>(undefined);

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: "dark", // Force dark mode for crypto dashboard look
          primary: {
            main: "#3b82f6",
          },
          secondary: {
            main: "#10b981",
          },
          background: {
            default: "#0f172a",
            paper: "#1e293b",
          },
          text: {
            primary: "#f8fafc",
            secondary: "#94a3b8",
          },
        },
        typography: {
          fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
          h4: {
            fontWeight: 700,
            letterSpacing: "-0.02em",
          },
          h6: {
            fontWeight: 600,
          },
        },
        components: {
          MuiCard: {
            styleOverrides: {
              root: {
                backgroundImage: "none",
                borderRadius: 12,
                border: "1px solid rgba(255, 255, 255, 0.1)",
              },
            },
          },
          MuiPaper: {
            styleOverrides: {
              root: {
                backgroundImage: "none",
              },
            },
          },
          MuiChip: {
            styleOverrides: {
              root: {
                borderRadius: 8,
              },
            },
          },
        },
      }),
    []
  );

  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  // Load manifest first
  useEffect(() => {
    const loadManifest = async () => {
      try {
        const manifest = await fetchManifest();
        setDatasets(manifest.datasets);
        if (manifest.datasets.length > 0) {
          setSelectedDatasetId(manifest.datasets[0].id);
        }
      } catch (err) {
        console.error("Failed to load manifest:", err);
        setError("Gagal memuat daftar dataset");
      }
    };
    void loadManifest();
  }, []);

  // Load data when selected dataset changes
  useEffect(() => {
    if (!selectedDatasetId) return;

    const loadData = async () => {
      setLoading(true);
      try {
        const dataset = datasets.find((d) => d.id === selectedDatasetId);
        if (!dataset) throw new Error("Dataset not found");

        const [recResponse, priceResponse] = await Promise.all([
          fetchRecommendations(dataset.recommendations),
          fetchPrices(dataset.price),
        ]);
        setRecs(recResponse.data);
        setMeta(recResponse.meta);
        setPrices(priceResponse.data);
        const recUpdated = recResponse.generatedAt ?? 0;
        const priceUpdated = priceResponse.generatedAt ?? 0;
        const maxUpdated = Math.max(recUpdated, priceUpdated);
        setLastUpdated(maxUpdated > 0 ? maxUpdated : null);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat data");
      } finally {
        setLoading(false);
      }
    };
    void loadData();
  }, [selectedDatasetId, datasets]);

  const handleSourceChange = (event: SelectChangeEvent) => {
    setSelectedDatasetId(event.target.value);
  };

  const horizons = useMemo(
    () => Array.from(new Set(recs.map((r) => r.horizon_hours))).sort((a, b) => a - b),
    [recs]
  );
  const accepted = recs.filter((r) => r.status === "ACCEPTED").length;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <AppBar position="static" color="transparent" elevation={0} sx={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
          <Toolbar>
            <DashboardIcon sx={{ mr: 2, color: "primary.main" }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: "bold" }}>
              Kaplan-Meier Survival Dashboard
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <Select
                  value={selectedDatasetId}
                  onChange={handleSourceChange}
                  displayEmpty
                  sx={{
                    color: "white",
                    ".MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.3)" },
                    "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.5)" },
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: "primary.main" },
                    ".MuiSvgIcon-root": { color: "white" },
                  }}
                >
                  {datasets.map((d) => (
                    <MenuItem key={d.id} value={d.id}>
                      {d.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Chip
                icon={<ShowChartIcon />}
                label={meta?.pair_label || "Base Mainnet"}
                color="primary"
                variant="outlined"
                size="small"
              />
              {lastUpdated && (
                <Chip
                  label={`Updated: ${new Date(lastUpdated).toLocaleString()}`}
                  color="secondary"
                  variant="outlined"
                  size="small"
                  sx={{ ml: 1 }}
                />
              )}
            </Stack>
          </Toolbar>
        </AppBar>

        <Container maxWidth="xl" sx={{ py: 4, flex: 1 }}>
          {loading ? (
            <Box display="flex" alignItems="center" justifyContent="center" minHeight="60vh">
              <CircularProgress size={60} thickness={4} />
            </Box>
          ) : error ? (
            <Paper sx={{ p: 4, textAlign: "center", bgcolor: "error.dark", color: "white" }}>
              <Typography variant="h5" gutterBottom>Error Loading Data</Typography>
              <Typography>{error}</Typography>
            </Paper>
          ) : (
            <Stack spacing={4}>
              {/* Summary Cards */}
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 3, height: "100%" }}>
                    <Typography color="text.secondary" variant="subtitle2" gutterBottom>
                      Total Recommendations
                    </Typography>
                    <Typography variant="h3" fontWeight="bold">
                      {recs.length}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 3, height: "100%" }}>
                    <Typography color="text.secondary" variant="subtitle2" gutterBottom>
                      Accepted Strategies
                    </Typography>
                    <Typography variant="h3" fontWeight="bold" color="success.main">
                      {accepted}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                    <Typography color="text.secondary" variant="subtitle2" gutterBottom>
                      Metadata
                    </Typography>
                    <Stack spacing={1}>
                      {meta ? (
                        <>
                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              Pair Address
                            </Typography>
                            <Typography variant="body2" fontFamily="monospace">
                              {meta.pair_address}
                            </Typography>
                          </Box>
                          <Stack direction="row" spacing={1}>
                            <Chip label={meta.pool_type} size="small" color="secondary" variant="outlined" />
                            <Chip label={meta.pair_label} size="small" color="primary" variant="outlined" />
                          </Stack>
                        </>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No metadata available
                        </Typography>
                      )}
                    </Stack>
                  </Paper>
                </Grid>
              </Grid>

              {/* Main Content */}
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <PriceChart
                    data={prices}
                    title={meta ? `${meta.pair_label} Price History` : "Price History"}
                  />
                </Grid>
              </Grid>

              <Box>
                <Typography variant="h5" gutterBottom sx={{ mb: 3, fontWeight: "bold" }}>
                  Survival Analysis by Horizon
                </Typography>
                <Grid container spacing={3}>
                  {horizons.map((h) => (
                    <Grid item xs={12} md={6} xl={3} key={h}>
                      <SurvivalChart horizon={h} data={recs} />
                    </Grid>
                  ))}
                </Grid>
              </Box>

              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <RecommendationsTable data={recs} />
                </Grid>
              </Grid>
            </Stack>
          )}
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
