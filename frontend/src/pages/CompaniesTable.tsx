import { useState } from "react";
import { Link } from "react-router-dom";
import { useCompanies, useCompanySummaries, useSectors } from "../api/client";
import { fmtPct, fmtValue, pctColor } from "../lib/format";
import {
  NO_FILTER,
  isActive,
  passes,
  type Comparator,
  type PctFilter,
} from "../lib/pctFilter";
import FavoriteButton from "../components/FavoriteButton";

function PctControl({
  label,
  filter,
  onChange,
}: {
  label: string;
  filter: PctFilter;
  onChange: (f: PctFilter) => void;
}) {
  return (
    <>
      <label className="muted">{label}</label>
      <select
        value={filter.mode}
        onChange={(e) => onChange({ ...filter, mode: e.target.value as Comparator })}
      >
        <option value="">Any</option>
        <option value="gte">≥</option>
        <option value="lte">≤</option>
      </select>
      <input
        type="number"
        placeholder="%"
        style={{ width: 80 }}
        disabled={filter.mode === ""}
        value={filter.value}
        onChange={(e) => onChange({ ...filter, value: e.target.value })}
      />
    </>
  );
}

export default function CompaniesTable() {
  const [sector, setSector] = useState<string>("");
  const [qoq, setQoq] = useState<PctFilter>(NO_FILTER);
  const [yoy, setYoy] = useState<PctFilter>(NO_FILTER);
  const { data: sectors } = useSectors();
  const { data: companies, isLoading } = useCompanies("", sector || undefined);

  const tickers = (companies ?? []).map((c) => c.ticker);
  const summaries = useCompanySummaries(tickers);
  const filtering = isActive(qoq) || isActive(yoy);

  // Build the visible row groups up front so we can show an accurate empty state.
  const groups = (companies ?? []).map((c, i) => {
    const q = summaries[i];
    const kpis = (q?.data?.kpis ?? []).filter(
      (k) => passes(k.qoq_pct, qoq) && passes(k.yoy_pct, yoy),
    );
    return { company: c, loading: q?.isLoading ?? false, kpis };
  });
  // When filtering, hide companies that loaded with no matching KPI.
  const visible = groups.filter(
    (g) => g.loading || g.kpis.length > 0 || (!filtering && !g.loading),
  );

  return (
    <div>
      <h1>All companies — KPI overview</h1>
      <p className="muted">
        Latest value, QoQ %, YoY %, and current QTD for every KPI across all companies.
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
        <PctControl label="QoQ" filter={qoq} onChange={setQoq} />
        <PctControl label="YoY" filter={yoy} onChange={setYoy} />
        {filtering && (
          <button
            className="btn"
            onClick={() => {
              setQoq(NO_FILTER);
              setYoy(NO_FILTER);
            }}
          >
            Clear
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Sector</th>
              <th>KPI</th>
              <th className="num">Latest</th>
              <th>Period</th>
              <th className="num">QoQ</th>
              <th className="num">YoY</th>
              <th className="num">QTD</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  {filtering ? "No KPIs match the filters." : "No companies."}
                </td>
              </tr>
            )}
            {visible.map(({ company: c, loading, kpis }) => {
              const span = Math.max(kpis.length, 1);
              const companyCell = (
                <>
                  <td rowSpan={span} className="company-cell">
                    <Link to={`/company/${c.ticker}`}>{c.name}</Link>
                    <div>
                      <span className="badge">{c.ticker}</span>
                    </div>
                  </td>
                  <td rowSpan={span} className="muted">
                    {c.sector}
                  </td>
                </>
              );

              if (loading) {
                return (
                  <tr key={c.ticker}>
                    {companyCell}
                    <td colSpan={6} className="muted">
                      Loading…
                    </td>
                  </tr>
                );
              }
              if (kpis.length === 0) {
                return (
                  <tr key={c.ticker}>
                    {companyCell}
                    <td colSpan={6} className="muted">
                      No KPIs
                    </td>
                  </tr>
                );
              }

              return kpis.map((k, j) => (
                <tr key={`${c.ticker}-${k.kpi}`}>
                  {j === 0 && companyCell}
                  <td>
                    <FavoriteButton ticker={c.ticker} kpi={k.kpi} />{" "}
                    <Link to={`/company/${c.ticker}/kpi/${encodeURIComponent(k.kpi)}`}>
                      {k.kpi}
                    </Link>
                  </td>
                  <td className="num">{fmtValue(k.latest_value, k.unit)}</td>
                  <td className="muted">{k.latest_period ?? "—"}</td>
                  <td className="num" style={{ color: pctColor(k.qoq_pct) }}>
                    {fmtPct(k.qoq_pct)}
                  </td>
                  <td className="num" style={{ color: pctColor(k.yoy_pct) }}>
                    {fmtPct(k.yoy_pct)}
                  </td>
                  <td className="num">
                    {k.qtd_value != null ? (
                      <span title={k.qtd_as_of ? `as of ${k.qtd_as_of}` : undefined}>
                        {fmtValue(k.qtd_value, k.unit)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
