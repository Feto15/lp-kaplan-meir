import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { Recommendation } from "../types";

interface Props {
  data: Recommendation[];
}

export function RecommendationsTable({ data }: Props) {
  const sorted = [...data].sort((a, b) => {
    if (a.horizon_hours === b.horizon_hours) return a.W - b.W;
    return a.horizon_hours - b.horizon_hours;
  });

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Recommendations
      </Typography>
      <TableContainer component={Paper} sx={{ maxHeight: 420 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>Horizon (h)</TableCell>
              <TableCell>W</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>km_surv</TableCell>
              <TableCell>CI</TableCell>
              <TableCell>Count</TableCell>
              <TableCell>Reason</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((row, idx) => (
              <TableRow key={`${row.horizon_hours}-${row.W}-${idx}`}>
                <TableCell>{row.horizon_hours}</TableCell>
                <TableCell>{row.W}</TableCell>
                <TableCell>
                  <Chip
                    label={row.status}
                    color={row.status === "ACCEPTED" ? "success" : "default"}
                    size="small"
                  />
                </TableCell>
                <TableCell>{row.km_surv.toFixed(4)}</TableCell>
                <TableCell>
                  [{row.km_ci_low.toFixed(4)} .. {row.km_ci_high.toFixed(4)}]
                </TableCell>
                <TableCell>
                  total {row.count_total} | full {row.count_full_followup}
                </TableCell>
                <TableCell style={{ maxWidth: 280 }}>{row.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
