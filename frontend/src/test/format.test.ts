import { describe, expect, it } from "vitest";
import { IN_REASONS, MOVEMENT_META, OUT_REASONS } from "../lib/constants";
import { formatINR, formatPct } from "../lib/format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR(184500)).toBe("₹1,84,500");
    expect(formatINR(1234567.5, { decimals: 2 })).toBe("₹12,34,567.50");
  });
  it("formats compact lakh / crore values", () => {
    expect(formatINR(184000, { compact: true })).toBe("₹1.84 L");
    expect(formatINR(12000000, { compact: true })).toBe("₹1.2 Cr");
    expect(formatINR(45200, { compact: true })).toBe("₹45.2K");
    expect(formatINR(950, { compact: true })).toBe("₹950");
  });
});

describe("formatPct", () => {
  it("adds sign and uses a true minus", () => {
    expect(formatPct(12.44)).toBe("+12.4%");
    expect(formatPct(-3.1)).toBe("−3.1%");
    expect(formatPct(null)).toBe("—");
  });
});

describe("movement types", () => {
  it("IN and OUT reasons have the right direction", () => {
    IN_REASONS.forEach((t) => expect(MOVEMENT_META[t].dir).toBe("IN"));
    OUT_REASONS.forEach((t) => expect(MOVEMENT_META[t].dir).toBe("OUT"));
    expect(MOVEMENT_META.SALE.label).toBe("Sale");
  });
});
