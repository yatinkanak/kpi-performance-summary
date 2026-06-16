import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock the data layer so we test the toggle's rendering/interaction, not the network.
vi.mock("../api/client", () => ({
  useFavorites: vi.fn(),
  useAddFavorite: vi.fn(),
  useRemoveFavorite: vi.fn(),
}));
import { useAddFavorite, useFavorites, useRemoveFavorite } from "../api/client";
import FavoriteButton from "./FavoriteButton";

const addMutate = vi.fn();
const removeMutate = vi.fn();

const FAV = {
  ticker: "ACME",
  company_name: "Acme Corp",
  sector: "Tech",
  kpi: "Revenue",
  kpi_id: 1,
  unit: "$MM",
  created_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  addMutate.mockReset();
  removeMutate.mockReset();
  vi.mocked(useAddFavorite).mockReturnValue({ mutate: addMutate, isPending: false } as never);
  vi.mocked(useRemoveFavorite).mockReturnValue({ mutate: removeMutate, isPending: false } as never);
});

describe("FavoriteButton", () => {
  it("shows a hollow star and adds when not favorited", () => {
    vi.mocked(useFavorites).mockReturnValue({ data: [] } as never);
    render(<FavoriteButton ticker="ACME" kpi="Revenue" />);

    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent("☆");
    expect(btn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(btn);
    expect(addMutate).toHaveBeenCalledWith({ ticker: "ACME", kpi: "Revenue" });
    expect(removeMutate).not.toHaveBeenCalled();
  });

  it("shows a filled star and removes when already favorited", () => {
    vi.mocked(useFavorites).mockReturnValue({ data: [FAV] } as never);
    render(<FavoriteButton ticker="ACME" kpi="Revenue" />);

    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent("★");
    expect(btn).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(btn);
    expect(removeMutate).toHaveBeenCalledWith({ ticker: "ACME", kpi: "Revenue" });
    expect(addMutate).not.toHaveBeenCalled();
  });

  it("matches on both ticker AND kpi, not just one", () => {
    vi.mocked(useFavorites).mockReturnValue({ data: [FAV] } as never);
    // Same ticker, different KPI -> should read as not favorited.
    render(<FavoriteButton ticker="ACME" kpi="Margin" />);
    expect(screen.getByRole("button")).toHaveTextContent("☆");
  });

  it("is disabled while a mutation is pending", () => {
    vi.mocked(useFavorites).mockReturnValue({ data: [] } as never);
    vi.mocked(useAddFavorite).mockReturnValue({ mutate: addMutate, isPending: true } as never);
    render(<FavoriteButton ticker="ACME" kpi="Revenue" />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
