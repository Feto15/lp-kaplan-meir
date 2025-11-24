import { Box, Card, CardContent, CardHeader, Typography, useTheme } from "@mui/material";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "../types";

interface Props {
  data: PricePoint[];
  title?: string;
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export function PriceChart({ data, title = "Price History" }: Props) {
  const theme = useTheme();

  return (
    <Card sx={{ height: 450, display: "flex", flexDirection: "column" }}>
      <CardHeader
        title={title}
        subheader="Historical price movement from Aerodrome pool"
        titleTypographyProps={{ variant: "h6", fontWeight: "bold" }}
      />
      <CardContent sx={{ flex: 1, minHeight: 0, pb: 0 }}>
        {data.length === 0 ? (
          <Box
            display="flex"
            alignItems="center"
            justifyContent="center"
            height="100%"
            color="text.secondary"
          >
            <Typography variant="body2">
              No price data available. Ensure /data/price.json exists.
            </Typography>
          </Box>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={theme.palette.primary.main} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(v) =>
                  new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                }
                minTickGap={50}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                dy={10}
              />
              <YAxis
                domain={["auto", "auto"]}
                tickFormatter={(v) => v.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                dx={-10}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: 8,
                  boxShadow: theme.shadows[4],
                }}
                labelStyle={{ color: theme.palette.text.secondary, marginBottom: 4 }}
                itemStyle={{ color: theme.palette.primary.main, fontWeight: "bold" }}
                labelFormatter={(v) => formatDate(String(v))}
                formatter={(v: number) => [v.toFixed(2), "Price"]}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke={theme.palette.primary.main}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorPrice)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
