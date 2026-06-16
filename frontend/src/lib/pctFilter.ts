// Comparator-based filtering for QoQ/YoY percent metrics (used by the companies table).

export type Comparator = "" | "gte" | "lte";
export type PctFilter = { mode: Comparator; value: string };

export const NO_FILTER: PctFilter = { mode: "", value: "" };

// A filter is active only once a comparator AND a parseable threshold are set.
export function isActive(f: PctFilter): boolean {
  return f.mode !== "" && f.value.trim() !== "" && !Number.isNaN(parseFloat(f.value));
}

// Rows with a null metric never satisfy an active filter on that metric.
export function passes(pct: number | null | undefined, f: PctFilter): boolean {
  if (!isActive(f)) return true;
  if (pct === null || pct === undefined) return false;
  const threshold = parseFloat(f.value);
  return f.mode === "gte" ? pct >= threshold : pct <= threshold;
}
