import { Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CompanyDetail from "./pages/CompanyDetail";
import KpiDetail from "./pages/KpiDetail";
import SearchBar from "./components/SearchBar";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          KPI Performance Summary
        </Link>
        <SearchBar />
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/company/:ticker" element={<CompanyDetail />} />
          <Route path="/company/:ticker/kpi/:kpiId" element={<KpiDetail />} />
        </Routes>
      </main>
    </div>
  );
}
