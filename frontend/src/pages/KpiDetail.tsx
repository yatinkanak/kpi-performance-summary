import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { exportUrl, useKpiSeries } from "../api/client";
import KpiChart from "../components/KpiChart";

export default function KpiDetail() {
  const { ticker = "", kpiId = "" } = useParams();
  // Date-range filter is URL-driven so the view is shareable/bookmarkable.
  const [params, setParams] = useSearchParams();
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const [draft, setDraft] = useState({ from, to });

  const { data: series, isLoading } = useKpiSeries(ticker, kpiId, from || undefined, to || undefined);

  const apply = () => {
    const next: Record<string, string> = {};
    if (draft.from) next.from = draft.from;
    if (draft.to) next.to = draft.to;
    setParams(next);
  };

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!series) return <p>No data.</p>;

  return (
    <div>
      <Link to={`/company/${ticker}`} className="muted">
        ← {ticker}
      </Link>
      <h1>
        {series.company_name} — {series.kpi}
      </h1>
      <p className="muted">
        Unit: {series.unit}
        {series.last_updated &&
          ` · last updated ${new Date(series.last_updated).toLocaleDateString()}`}
        {series.qtd_as_of && ` · QTD as of ${series.qtd_as_of}`}
      </p>

      <div className="toolbar">
        <label className="muted">From</label>
        <input
          type="date"
          value={draft.from}
          onChange={(e) => setDraft({ ...draft, from: e.target.value })}
        />
        <label className="muted">To</label>
        <input
          type="date"
          value={draft.to}
          onChange={(e) => setDraft({ ...draft, to: e.target.value })}
        />
        <button className="btn" onClick={apply}>
          Apply
        </button>
        <a
          className="btn"
          href={exportUrl(ticker, kpiId, from || undefined, to || undefined)}
        >
          Export CSV
        </a>
      </div>

      <div className="card">
        <KpiChart series={series} />
      </div>
    </div>
  );
}
