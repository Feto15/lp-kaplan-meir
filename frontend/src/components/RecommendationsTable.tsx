import {
  Box,
  Card,
  CardHeader,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import type { Recommendation } from "../types";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import InfoIcon from "@mui/icons-material/Info";

interface Props {
  data: Recommendation[];
}

const formatPrice = (val: number) => {
  if (val === 0) return "0";
  if (val < 1) return val.toPrecision(4);
  return val.toFixed(2);
};

export function RecommendationsTable({ data }: Props) {
  const theme = useTheme();
  const sorted = [...data].sort((a, b) => {
    if (a.horizon_hours === b.horizon_hours) return a.W - b.W;
    return a.horizon_hours - b.horizon_hours;
  });

  return (
    <Card sx={{ display: "flex", flexDirection: "column" }}>
      <CardHeader
        title="Strategy Recommendations"
        subheader="Analysis based on survival probability"
        titleTypographyProps={{ variant: "h6", fontWeight: "bold" }}
      />
      <TableContainer sx={{ overflowX: "auto" }}>
        <Table size="small" sx={{ minWidth: 650 }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold", pl: 2 }}>Horizon</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }}>Window (W)</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }}>Status</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }}>Survival Prob.</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }}>Price Range</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }}>Sample Size</TableCell>
              <TableCell sx={{ bgcolor: "background.paper", fontWeight: "bold" }} align="center">
                Info
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((row, idx) => {
              const isAccepted = row.status === "ACCEPTED";
              return (
                <TableRow
                  key={`${row.horizon_hours}-${row.W}-${idx}`}
                  hover
                  sx={{
                    "&:last-child td, &:last-child th": { border: 0 },
                    bgcolor: isAccepted ? "rgba(16, 185, 129, 0.04)" : "transparent",
                  }}
                >
                  <TableCell sx={{ fontWeight: "medium", pl: 2 }}>{row.horizon_hours}h</TableCell>
                  <TableCell>{row.W}</TableCell>
                  <TableCell>
                    <Chip
                      icon={isAccepted ? <CheckCircleIcon /> : <CancelIcon />}
                      label={row.status}
                      color={isAccepted ? "success" : "default"}
                      size="small"
                      variant={isAccepted ? "filled" : "outlined"}
                      sx={{ fontWeight: "bold", minWidth: 100 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: "flex", flexDirection: "column" }}>
                      <Typography variant="body2" fontWeight="bold" color={isAccepted ? "success.main" : "text.primary"}>
                        {(row.km_surv * 100).toFixed(1)}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        CI: {row.km_ci_low.toFixed(2)}-{row.km_ci_high.toFixed(2)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: "flex", flexDirection: "column" }}>
                      <Typography variant="body2">
                        {formatPrice(row.price_from)} - {formatPrice(row.price_to)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.percent_range_total.toFixed(2)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: "flex", flexDirection: "column" }}>
                      <Typography variant="body2">{row.count_total} total</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.count_full_followup} full
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip
                      title={row.reason}
                      arrow
                      placement="left"
                      componentsProps={{
                        tooltip: {
                          sx: {
                            bgcolor: theme.palette.background.paper,
                            border: `1px solid ${theme.palette.divider}`,
                            color: theme.palette.text.primary,
                            boxShadow: theme.shadows[4],
                            p: 1.5,
                          },
                        },
                      }}
                    >
                      <InfoIcon color="action" fontSize="small" sx={{ cursor: "help" }} />
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Card>
  );
}
