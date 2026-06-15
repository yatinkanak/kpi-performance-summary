import { describe, expect, it } from "vitest";
import { fmtValue, fmtPct, pctColor } from "./format";

describe("fmtValue", () => {
  it("renders an em dash for null/undefined", () => {
    expect(fmtValue(null, "$MM")).toBe("—");
    expect(fmtValue(undefined, "units")).toBe("—");
  });

  it("formats currency units", () => {
    expect(fmtValue(12.5, "$")).toBe("$12.5");
    expect(fmtValue(640, "$MM")).toBe("$640MM");
  });

  it("appends arbitrary units", () => {
    expect(fmtValue(42, "units")).toBe("42 units");
  });

  it("drops decimals and adds thousands separators for large numbers", () => {
    expect(fmtValue(1234567, "units")).toBe("1,234,567 units");
  });

  it("keeps up to two decimals for small numbers", () => {
    expect(fmtValue(3.14159, "$")).toBe("$3.14");
  });
});

describe("fmtPct", () => {
  it("renders an em dash for null/undefined", () => {
    expect(fmtPct(null)).toBe("—");
    expect(fmtPct(undefined)).toBe("—");
  });

  it("prefixes a + for positive values and one decimal", () => {
    expect(fmtPct(25)).toBe("+25.0%");
  });

  it("keeps the - for negative values", () => {
    expect(fmtPct(-3.2)).toBe("-3.2%");
  });

  it("shows zero without a sign", () => {
    expect(fmtPct(0)).toBe("0.0%");
  });
});

describe("pctColor", () => {
  it("is grey for missing values", () => {
    expect(pctColor(null)).toBe("#888");
  });

  it("is green for non-negative and red for negative", () => {
    expect(pctColor(0)).toBe("#1a7f37");
    expect(pctColor(5)).toBe("#1a7f37");
    expect(pctColor(-1)).toBe("#cf222e");
  });
});
