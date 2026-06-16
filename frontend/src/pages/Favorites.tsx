import { Link } from "react-router-dom";
import { useFavorites } from "../api/client";
import { fmtPct, fmtValue, pctColor } from "../lib/format";
import FavoriteButton from "../components/FavoriteButton";

export default function Favorites() {
  const { data: favorites, isLoading } = useFavorites();

  return (
    <div>
      <h1>Favorites</h1>
      <p className="muted">KPIs you've bookmarked across companies.</p>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : !favorites || favorites.length === 0 ? (
        <p className="muted">
          No favorites yet. Open a KPI and tap the ☆ to bookmark it.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 32 }}></th>
              <th>Company</th>
              <th>Sector</th>
              <th>KPI</th>
              <th className="num">Latest</th>
              <th>Period</th>
              <th className="num">QoQ</th>
              <th className="num">YoY</th>
              <th className="num">QTD</th>
              <th>Added</th>
            </tr>
          </thead>
          <tbody>
            {favorites.map((f) => {
              const m = f.metrics;
              return (
                <tr key={`${f.ticker}-${f.kpi_id}`}>
                  <td className="num">
                    <FavoriteButton ticker={f.ticker} kpi={f.kpi} />
                  </td>
                  <td className="company-cell">
                    <Link to={`/company/${f.ticker}`}>{f.company_name}</Link>
                    <div>
                      <span className="badge">{f.ticker}</span>
                    </div>
                  </td>
                  <td className="muted">{f.sector}</td>
                  <td>
                    <Link to={`/company/${f.ticker}/kpi/${f.kpi_id}`}>{f.kpi}</Link>
                  </td>
                  <td className="num">{fmtValue(m?.latest_value, f.unit)}</td>
                  <td className="muted">{m?.latest_period ?? "—"}</td>
                  <td className="num" style={{ color: pctColor(m?.qoq_pct) }}>
                    {fmtPct(m?.qoq_pct)}
                  </td>
                  <td className="num" style={{ color: pctColor(m?.yoy_pct) }}>
                    {fmtPct(m?.yoy_pct)}
                  </td>
                  <td className="num">
                    {m?.qtd_value != null ? (
                      <span title={m.qtd_as_of ? `as of ${m.qtd_as_of}` : undefined}>
                        {fmtValue(m.qtd_value, f.unit)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="muted">
                    {new Date(f.created_at).toLocaleDateString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
