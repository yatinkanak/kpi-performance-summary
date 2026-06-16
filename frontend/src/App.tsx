import { Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CompaniesTable from "./pages/CompaniesTable";
import CompanyDetail from "./pages/CompanyDetail";
import Favorites from "./pages/Favorites";
import KpiDetail from "./pages/KpiDetail";
import SearchBar from "./components/SearchBar";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          KPI Performance Summary
        </Link>
        <nav className="nav">
          <Link to="/">Dashboard</Link>
          <Link to="/table">Table</Link>
          <Link to="/favorites">Favorites</Link>
        </nav>
        <SearchBar />
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/table" element={<CompaniesTable />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/company/:ticker" element={<CompanyDetail />} />
          <Route path="/company/:ticker/kpi/:kpiId" element={<KpiDetail />} />
        </Routes>
      </main>
    </div>
  );
}
