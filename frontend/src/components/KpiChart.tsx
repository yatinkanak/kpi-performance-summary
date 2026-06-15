import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { KpiSeries } from "../api/client";

// Historical quarters plotted as a solid line; QTD snapshots (current quarter)
// appended as a dashed trajectory so the intra-quarter pace is visible at the tail.
export default function KpiChart({ series }: { series: KpiSeries }) {
  const data = [
    ...series.historical.map((p) => ({ label: p.fiscal_period, historical: p.value })),
    ...series.qtd.map((p) => ({ label: `QTD ${p.as_of}`, qtd: p.value })),
  ];

  return (
    <ResponsiveContainer width="100%" height={360}>
      <LineChart data={data} margin={{ top: 10, right: 20, bottom: 40, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" angle={-40} textAnchor="end" height={70} fontSize={12} />
        <YAxis fontSize={12} width={70} />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="historical"
          name={`${series.kpi} (historical)`}
          stroke="#0969da"
          strokeWidth={2}
          connectNulls
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="qtd"
          name="QTD"
          stroke="#bf3989"
          strokeWidth={2}
          strokeDasharray="5 4"
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
