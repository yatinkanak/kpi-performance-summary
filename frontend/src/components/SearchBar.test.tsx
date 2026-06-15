import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock the data hook so we test SearchBar's rendering/interaction, not the network.
vi.mock("../api/client", () => ({ useSearch: vi.fn() }));
import { useSearch } from "../api/client";
import SearchBar from "./SearchBar";

const RESULT = {
  companies: [{ ticker: "ACME", name: "Acme Corp", sector: "Tech" }],
  sectors: [{ id: 1, name: "Tech", company_count: 2 }],
  kpis: [{ id: 3, name: "Total Revenue ($MM)", unit: "$MM" }],
};

const renderBar = () =>
  render(
    <MemoryRouter>
      <SearchBar />
    </MemoryRouter>,
  );
const typeQuery = (value: string) =>
  fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value } });

describe("SearchBar", () => {
  beforeEach(() => vi.mocked(useSearch).mockReset());

  it("shows no results until at least 2 characters are typed", () => {
    vi.mocked(useSearch).mockReturnValue({ data: RESULT } as never);
    renderBar();
    expect(screen.queryByText("Companies")).not.toBeInTheDocument();
    typeQuery("a");
    expect(screen.queryByText("Companies")).not.toBeInTheDocument();
  });

  it("renders grouped results with a working company link", () => {
    vi.mocked(useSearch).mockReturnValue({ data: RESULT } as never);
    renderBar();
    typeQuery("ac");

    expect(screen.getByText("Companies")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Acme Corp/ })).toHaveAttribute(
      "href",
      "/company/ACME",
    );
    expect(screen.getByText("Sectors")).toBeInTheDocument();
    expect(screen.getByText("KPIs")).toBeInTheDocument();
  });

  it("hides empty groups", () => {
    vi.mocked(useSearch).mockReturnValue({
      data: { ...RESULT, sectors: [], kpis: [] },
    } as never);
    renderBar();
    typeQuery("ac");

    expect(screen.getByText("Companies")).toBeInTheDocument();
    expect(screen.queryByText("Sectors")).not.toBeInTheDocument();
    expect(screen.queryByText("KPIs")).not.toBeInTheDocument();
  });
});
