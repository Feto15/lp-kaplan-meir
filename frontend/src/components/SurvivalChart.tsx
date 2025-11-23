import { Card, CardContent, CardHeader, Chip, Stack } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
  const filtered = data
    .filter((row) => row.horizon_hours === horizon)
    .sort((a, b) => a.W - b.W);

  return (
    <Card sx={{ height: 320 }}>
      <CardHeader
        title={`Survival @ ${horizon}h`}
        subheader="km_surv per window (W)"
        action={
          <Stack direction="row" spacing={1}>
            <Chip label=">=0.60 target" size="small" color="primary" variant="outlined" />
          </Stack>
        }
      />
      <CardContent sx={{ height: 220 }}>
        {filtered.length === 0 ? (
          <span>Tidak ada data untuk horizon ini.</span>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filtered}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="W" />
              <YAxis domain={[0, 1]} tickFormatter={(v) => v.toFixed(2)} />
              <Tooltip formatter={(v: number) => v.toFixed(4)} />
              <Bar dataKey="km_surv" fill="#2e7d32" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
