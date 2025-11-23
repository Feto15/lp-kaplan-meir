import { Box, Card, CardContent, CardHeader, Chip, Stack, Typography, useTheme } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Recommendation } from "../types";

interface Props {
  horizon: number;
  data: Recommendation[];
}

export function SurvivalChart({ horizon, data }: Props) {
  const theme = useTheme();
  const filtered = data
    .filter((row) => row.horizon_hours === horizon)
    .sort((a, b) => a.W - b.W);

  return (
    <Card sx={{ height: 350, display: "flex", flexDirection: "column" }}>
      <CardHeader
        title={`${horizon}h Horizon`}
        subheader="Survival Probability by Window Size"
        titleTypographyProps={{ variant: "h6", fontWeight: "bold" }}
        action={
          <Stack direction="row" spacing={1}>
            <Chip
              label="Target ≥ 60%"
              size="small"
              color="success"
              variant="outlined"
              sx={{ borderRadius: 1 }}
            />
          </Stack>
        }
      />
      <CardContent sx={{ flex: 1, minHeight: 0, pb: 1 }}>
        {filtered.length === 0 ? (
          <Box display="flex" alignItems="center" justifyContent="center" height="100%">
            <Typography variant="body2" color="text.secondary">
              No data available for this horizon.
            </Typography>
          </Box>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filtered} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis
                dataKey="W"
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                dy={10}
                label={{ value: "Window Size (W)", position: "insideBottom", offset: -5, fill: theme.palette.text.secondary, fontSize: 10 }}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.05)" }}
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: 8,
                  boxShadow: theme.shadows[4],
                }}
                labelStyle={{ color: theme.palette.text.secondary, marginBottom: 4 }}
                formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, "Survival Probability"]}
                labelFormatter={(v) => `Window Size: ${v}`}
              />
              <ReferenceLine y={0.6} stroke={theme.palette.success.main} strokeDasharray="3 3" />
              <Bar dataKey="km_surv" radius={[4, 4, 0, 0]}>
                {filtered.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.km_surv >= 0.6
                        ? theme.palette.success.main
                        : theme.palette.warning.main
                    }
                    fillOpacity={entry.km_surv >= 0.6 ? 0.8 : 0.5}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
