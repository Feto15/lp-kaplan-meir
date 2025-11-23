import { Card, CardContent, CardHeader, Typography } from "@mui/material";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "../types";

interface Props {
  data: PricePoint[];
}

const formatDate = (iso: string) => new Date(iso).toLocaleString();

export function PriceChart({ data }: Props) {
  return (
    <Card sx={{ height: 400 }}>
      <CardHeader title="Price History" subheader="From cache/price data" />
      <CardContent sx={{ height: 320 }}>
        {data.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Tidak ada data harga. Pastikan file JSON tersedia di /data/price.json.
          </Typography>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(v) => new Date(v).toLocaleDateString()}
                minTickGap={30}
              />
              <YAxis
                domain={["auto", "auto"]}
                tickFormatter={(v) => v.toFixed(2)}
              />
              <Tooltip
                labelFormatter={(v) => formatDate(String(v))}
                formatter={(v: number) => v.toFixed(4)}
              />
              <Line
                type="monotone"
                dataKey="price"
                stroke="#1976d2"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
