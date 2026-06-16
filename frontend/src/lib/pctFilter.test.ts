import { describe, expect, it } from "vitest";
import { NO_FILTER, isActive, passes, type PctFilter } from "./pctFilter";

const f = (mode: "gte" | "lte", value: string): PctFilter => ({ mode, value });

describe("isActive", () => {
  it("is inactive without a comparator", () => {
    expect(isActive(NO_FILTER)).toBe(false);
    expect(isActive({ mode: "", value: "5" })).toBe(false);
  });

  it("is inactive when the threshold is blank or non-numeric", () => {
    expect(isActive({ mode: "gte", value: "" })).toBe(false);
    expect(isActive({ mode: "gte", value: "   " })).toBe(false);
    expect(isActive({ mode: "gte", value: "abc" })).toBe(false);
  });

  it("is active with a comparator and a parseable number", () => {
    expect(isActive(f("gte", "0"))).toBe(true);
    expect(isActive(f("lte", "-5"))).toBe(true);
  });
});

describe("passes", () => {
  it("passes everything when the filter is inactive", () => {
    expect(passes(null, NO_FILTER)).toBe(true);
    expect(passes(123, NO_FILTER)).toBe(true);
  });

  it("excludes null/undefined metrics when the filter is active", () => {
    expect(passes(null, f("gte", "0"))).toBe(false);
    expect(passes(undefined, f("lte", "0"))).toBe(false);
  });

  it("applies >= for gte (inclusive)", () => {
    expect(passes(10, f("gte", "10"))).toBe(true);
    expect(passes(9.9, f("gte", "10"))).toBe(false);
  });

  it("applies <= for lte (inclusive)", () => {
    expect(passes(-5, f("lte", "0"))).toBe(true);
    expect(passes(0, f("lte", "0"))).toBe(true);
    expect(passes(0.1, f("lte", "0"))).toBe(false);
  });
});
