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
  useMediaQuery,
} from "@mui/material";
import Grid from "@mui/material/GridLegacy";
import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { fetchPrices, fetchRecommendations } from "./api/data";
import { PriceChart } from "./components/PriceChart";
import { RecommendationsTable } from "./components/RecommendationsTable";
import { SurvivalChart } from "./components/SurvivalChart";
import type { PricePoint, Recommendation } from "./types";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import DashboardIcon from "@mui/icons-material/Dashboard";

function App() {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");
  const [dataSource, setDataSource] = useState<string>("/data/recommendations.json");

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

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [r, p] = await Promise.all([fetchRecommendations(dataSource), fetchPrices()]);
        setRecs(r);
        setPrices(p);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gagal memuat data");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [dataSource]);

  const handleSourceChange = (event: SelectChangeEvent) => {
    setDataSource(event.target.value);
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
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <Select
                  value={dataSource}
                  onChange={handleSourceChange}
                  sx={{
                    color: "white",
                    ".MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.3)" },
                    "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.5)" },
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: "primary.main" },
                    ".MuiSvgIcon-root": { color: "white" },
                  }}
                >
                  <MenuItem value="/data/recommendations.json">Data Source 1</MenuItem>
                  <MenuItem value="/data/recommendations_v3.json">Data Source 2 (V3)</MenuItem>
                </Select>
              </FormControl>
              <Chip
                icon={<ShowChartIcon />}
                label="Base Mainnet"
                color="primary"
                variant="outlined"
                size="small"
              />
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
                      Data Sources
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Chip
                        label={dataSource.split("/").pop()}
                        size="small"
                        sx={{ fontFamily: "monospace" }}
                        color="primary"
                      />
                      <Chip label="price.json" size="small" sx={{ fontFamily: "monospace" }} />
                    </Stack>
                  </Paper>
                </Grid>
              </Grid>

              {/* Main Content */}
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <PriceChart data={prices} />
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
