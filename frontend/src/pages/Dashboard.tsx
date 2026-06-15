import { useState } from "react";
import { Link } from "react-router-dom";
import { useCompanies, useSectors } from "../api/client";

export default function Dashboard() {
  const [sector, setSector] = useState<string>("");
  const { data: sectors } = useSectors();
  const { data: companies, isLoading } = useCompanies("", sector || undefined);

  return (
    <div>
      <h1>Public Investor KPI Dashboard</h1>
      <p className="muted">
        Browse companies by sector, then drill into KPI trends (history vs QTD).
      </p>

      <div className="toolbar">
        <label className="muted">Sector</label>
        <select value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="">All sectors</option>
          {sectors?.map((s) => (
            <option key={s.id} value={s.name}>
              {s.name} ({s.company_count})
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="grid">
          {companies?.map((c) => (
            <Link key={c.ticker} to={`/company/${c.ticker}`} className="card">
              <div className="summary-kpi">
                <strong>{c.name}</strong>
                <span className="badge">{c.ticker}</span>
              </div>
              <div className="muted">{c.sector}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
