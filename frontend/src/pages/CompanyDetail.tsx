import { Link, useParams } from "react-router-dom";
import { useCompany, useCompanySummary } from "../api/client";
import { fmtPct, fmtValue, pctColor } from "../lib/format";

export default function CompanyDetail() {
  const { ticker = "" } = useParams();
  const { data: company } = useCompany(ticker);
  const { data: summary, isLoading } = useCompanySummary(ticker);

  if (isLoading) return <p className="muted">Loading…</p>;
  if (!summary) return <p>Company not found.</p>;

  return (
    <div>
      <Link to="/" className="muted">
        ← All companies
      </Link>
      <h1>
        {summary.company_name} <span className="badge">{summary.ticker}</span>
      </h1>
      <p className="muted">
        {summary.sector}
        {summary.last_updated &&
          ` · last updated ${new Date(summary.last_updated).toLocaleDateString()}`}
      </p>

      <h2>At a glance</h2>
      <div className="grid">
        {summary.kpis.map((k) => {
          const kpiRef = company?.kpis.find((x) => x.name === k.kpi)?.id ?? k.kpi;
          return (
            <Link
              key={k.kpi}
              to={`/company/${ticker}/kpi/${encodeURIComponent(String(kpiRef))}`}
              className="card"
            >
              <div className="muted">{k.kpi}</div>
              <div className="summary-val">{fmtValue(k.latest_value, k.unit)}</div>
              <div className="muted">{k.latest_period}</div>
              <div style={{ marginTop: 8, display: "flex", gap: 12, fontSize: 13 }}>
                <span style={{ color: pctColor(k.qoq_pct) }}>QoQ {fmtPct(k.qoq_pct)}</span>
                <span style={{ color: pctColor(k.yoy_pct) }}>YoY {fmtPct(k.yoy_pct)}</span>
              </div>
              {k.qtd_value != null && (
                <div className="muted" style={{ marginTop: 6 }}>
                  QTD {fmtValue(k.qtd_value, k.unit)} · as of {k.qtd_as_of}
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
