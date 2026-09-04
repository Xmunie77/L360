import { describe, expect, it } from "vitest";
import { ageFromDob } from "./AgeBadge";

const TODAY = new Date("2026-09-04T12:00:00");

describe("ageFromDob", () => {
  it("counts a birthday not yet reached this year", () => {
    expect(ageFromDob("2017-03-15", TODAY)).toBe("9");
    expect(ageFromDob("2017-12-01", TODAY)).toBe("8");
  });

  it("counts today's birthday as reached", () => {
    expect(ageFromDob("2018-09-04", TODAY)).toBe("8");
  });

  it("shows months under one year", () => {
    expect(ageFromDob("2026-01-20", TODAY)).toBe("7 mo");
  });

  it("returns null for empty, invalid and future dates", () => {
    expect(ageFromDob("", TODAY)).toBeNull();
    expect(ageFromDob("not-a-date", TODAY)).toBeNull();
    expect(ageFromDob("2030-01-01", TODAY)).toBeNull();
  });
});
