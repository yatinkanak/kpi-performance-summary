import { useState } from "react";
import { Link } from "react-router-dom";
import { useSearch } from "../api/client";

export default function SearchBar() {
  const [q, setQ] = useState("");
  const { data } = useSearch(q);
  const show = q.length >= 2 && data;

  return (
    <div className="searchbox">
      <input
        placeholder="Search sectors, companies, KPIs…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {show && (
        <div className="results" onClick={() => setQ("")}>
          {data.companies.length > 0 && <div className="group">Companies</div>}
          {data.companies.map((c) => (
            <Link key={c.ticker} to={`/company/${c.ticker}`}>
              {c.name} <span className="muted">· {c.ticker} · {c.sector}</span>
            </Link>
          ))}
          {data.sectors.length > 0 && <div className="group">Sectors</div>}
          {data.sectors.map((s) => (
            <div key={s.id} style={{ padding: "6px 12px" }}>
              {s.name} <span className="muted">· {s.company_count} companies</span>
            </div>
          ))}
          {data.kpis.length > 0 && <div className="group">KPIs</div>}
          {data.kpis.map((k) => (
            <div key={k.id} style={{ padding: "6px 12px" }}>
              {k.name} <span className="muted">· {k.unit}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
