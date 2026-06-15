import { describe, expect, it } from "vitest";
import { exportUrl } from "./client";

describe("exportUrl", () => {
  it("builds the export path with no date params", () => {
    expect(exportUrl("ACME", 3)).toBe(
      "http://localhost:8000/api/v1/companies/ACME/kpis/3/series/export?",
    );
  });

  it("includes from/to when provided", () => {
    expect(exportUrl("ACME", "Total Revenue ($MM)", "2024-01-01", "2025-12-31")).toContain(
      "from=2024-01-01&to=2025-12-31",
    );
  });

  it("omits a param that is not provided", () => {
    const url = exportUrl("ACME", 3, "2024-01-01");
    expect(url).toContain("from=2024-01-01");
    expect(url).not.toContain("to=");
  });
});
