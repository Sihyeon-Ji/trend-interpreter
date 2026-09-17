import { describe, expect, it } from "vitest";
import { SCENARIO_DAYS, scenarioRadius } from "../src/lib/scenario";

describe("illustrative expansion envelope", () => {
  it("starts with a fixed seed and expands monotonically", () => {
    expect(scenarioRadius(0, "baseline", 30)).toBe(2);
    let previous = 0;
    for (let day = 0; day <= SCENARIO_DAYS; day++) {
      const radius = scenarioRadius(day, "baseline", 30);
      expect(radius).toBeGreaterThanOrEqual(previous);
      previous = radius;
    }
  });
  it("makes higher response assumptions reduce the same-day envelope", () => {
    expect(scenarioRadius(30, "baseline", 90)).toBeLessThan(
      scenarioRadius(30, "baseline", 10),
    );
  });
  it("applies pace controls without interpreting them as disease parameters", () => {
    expect(scenarioRadius(30, "slow", 0)).toBeLessThan(
      scenarioRadius(30, "baseline", 0),
    );
    expect(scenarioRadius(30, "baseline", 0)).toBeLessThan(
      scenarioRadius(30, "fast", 0),
    );
  });
  it("bounds invalid or out-of-range timeline and response inputs", () => {
    expect(scenarioRadius(-20, "baseline", 30)).toBe(2);
    expect(scenarioRadius(Infinity, "baseline", NaN)).toBe(2);
    expect(scenarioRadius(1000, "baseline", -100)).toBe(
      scenarioRadius(60, "baseline", 0),
    );
    expect(scenarioRadius(60, "baseline", 200)).toBe(
      scenarioRadius(60, "baseline", 100),
    );
  });
});
