import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { KpiSeries } from "../api/client";

// Stub recharts (SVG doesn't lay out under jsdom) and capture the data passed to
// LineChart so we can assert KpiChart's own merge logic, not the chart rendering.
vi.mock("recharts", () => {
  const Pass = ({ children }: { children?: unknown }) => <div>{children as never}</div>;
  return {
    ResponsiveContainer: Pass,
    LineChart: ({ data, children }: { data: unknown; children?: unknown }) => (
      <div data-testid="chart" data-points={JSON.stringify(data)}>
        {children as never}
      </div>
    ),
    Line: () => null,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});
import KpiChart from "./KpiChart";

const series: KpiSeries = {
  ticker: "ACME",
  company_name: "Acme Corp",
  kpi: "Total Revenue ($MM)",
  unit: "$MM",
  historical: [
    { fiscal_period: "2024Q4", period_start: "", period_end: "", est_type: "historical", value: 160 },
    { fiscal_period: "2025Q1", period_start: "", period_end: "", est_type: "historical", value: 200 },
  ],
  qtd: [
    { fiscal_period: "2025Q2", period_start: "", period_end: "", est_type: "qtd", value: 90, as_of: "2025-05-15" },
  ],
};

describe("KpiChart", () => {
  it("merges historical (solid) and QTD (dashed) into labeled points", () => {
    render(<KpiChart series={series} />);
    const points = JSON.parse(screen.getByTestId("chart").dataset.points as string);
    expect(points).toEqual([
      { label: "2024Q4", historical: 160 },
      { label: "2025Q1", historical: 200 },
      { label: "QTD 2025-05-15", qtd: 90 },
    ]);
  });
});
