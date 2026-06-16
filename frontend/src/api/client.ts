// Typed API client + TanStack Query hooks.
// In production these types are generated from the backend OpenAPI schema via
// `openapi-typescript`; hand-written here to keep the scaffold self-contained.
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API = `${BASE}/api/v1`;

export type Sector = { id: number; name: string; company_count: number };
export type Kpi = { id: number; name: string; unit: string; description?: string | null };
export type Company = { ticker: string; name: string; sector: string };
export type CompanyDetail = Company & { kpis: Kpi[]; last_updated?: string | null };

export type SeriesPoint = {
  fiscal_period: string;
  period_start: string;
  period_end: string;
  est_type: "historical" | "qtd";
  value: number;
  as_of?: string | null;
};
export type KpiSeries = {
  ticker: string;
  company_name: string;
  kpi: string;
  unit: string;
  historical: SeriesPoint[];
  qtd: SeriesPoint[];
  last_updated?: string | null;
  qtd_as_of?: string | null;
};
export type KpiSummary = {
  kpi: string;
  unit: string;
  latest_period?: string | null;
  latest_value?: number | null;
  qoq_pct?: number | null;
  yoy_pct?: number | null;
  qtd_value?: number | null;
  qtd_as_of?: string | null;
};
export type CompanySummary = {
  ticker: string;
  company_name: string;
  sector: string;
  last_updated?: string | null;
  kpis: KpiSummary[];
};
export type SearchResult = { sectors: Sector[]; companies: Company[]; kpis: Kpi[] };
export type Favorite = {
  ticker: string;
  company_name: string;
  sector: string;
  kpi: string;
  kpi_id: number;
  unit: string;
  created_at: string;
  metrics?: KpiSummary | null;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

// ---- hooks ----------------------------------------------------------------
export const useSectors = () =>
  useQuery({ queryKey: ["sectors"], queryFn: () => get<Sector[]>("/sectors") });

export const useCompanies = (search: string, sector?: string) =>
  useQuery({
    queryKey: ["companies", search, sector],
    queryFn: () =>
      get<Company[]>(
        `/companies?${new URLSearchParams({
          ...(search ? { search } : {}),
          ...(sector ? { sector } : {}),
        })}`,
      ),
  });

export const useCompany = (ticker: string) =>
  useQuery({
    queryKey: ["company", ticker],
    queryFn: () => get<CompanyDetail>(`/companies/${ticker}`),
    enabled: !!ticker,
  });

export const useCompanySummary = (ticker: string) =>
  useQuery({
    queryKey: ["summary", ticker],
    queryFn: () => get<CompanySummary>(`/companies/${ticker}/summary`),
    enabled: !!ticker,
  });

// Fetch the at-a-glance summary for many companies at once (one request each,
// sharing the same cache key as useCompanySummary). Drives the all-companies table.
export const useCompanySummaries = (tickers: string[]) =>
  useQueries({
    queries: tickers.map((ticker) => ({
      queryKey: ["summary", ticker],
      queryFn: () => get<CompanySummary>(`/companies/${ticker}/summary`),
      enabled: !!ticker,
    })),
  });

export const useKpiSeries = (
  ticker: string,
  kpiId: number | string,
  from?: string,
  to?: string,
) =>
  useQuery({
    queryKey: ["series", ticker, kpiId, from, to],
    queryFn: () =>
      get<KpiSeries>(
        `/companies/${ticker}/kpis/${kpiId}/series?${new URLSearchParams({
          ...(from ? { from } : {}),
          ...(to ? { to } : {}),
        })}`,
      ),
    enabled: !!ticker && kpiId !== "" && kpiId !== undefined,
  });

export const useSearch = (q: string) =>
  useQuery({
    queryKey: ["search", q],
    queryFn: () => get<SearchResult>(`/search?q=${encodeURIComponent(q)}`),
    enabled: q.length >= 2,
  });

// ---- favorites ------------------------------------------------------------
export const useFavorites = () =>
  useQuery({ queryKey: ["favorites"], queryFn: () => get<Favorite[]>("/favorites") });

export const useAddFavorite = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { ticker: string; kpi: string }) =>
      post<Favorite>("/favorites", v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });
};

export const useRemoveFavorite = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { ticker: string; kpi: string }) =>
      del(`/favorites?${new URLSearchParams({ ticker: v.ticker, kpi: v.kpi })}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });
};

export function exportUrl(ticker: string, kpiId: number | string, from?: string, to?: string) {
  const params = new URLSearchParams({ ...(from ? { from } : {}), ...(to ? { to } : {}) });
  return `${API}/companies/${ticker}/kpis/${kpiId}/series/export?${params}`;
}
