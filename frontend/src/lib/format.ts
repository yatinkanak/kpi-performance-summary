export function fmtValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "—";
  const n =
    Math.abs(value) >= 1000
      ? value.toLocaleString(undefined, { maximumFractionDigits: 0 })
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (unit === "$") return `$${n}`;
  if (unit === "$MM") return `$${n}MM`;
  return `${n} ${unit}`;
}

export function fmtPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function pctColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "#888";
  return pct >= 0 ? "#1a7f37" : "#cf222e";
}
