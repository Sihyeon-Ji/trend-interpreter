export const SCENARIO_DAYS = 60;
export type ScenarioPace = "slow" | "baseline" | "fast";
export interface ScenarioSettings {
  day: number;
  pace: ScenarioPace;
  response: number;
  origin: { longitude: number; latitude: number; name: string; code: string };
}

const PACE_DEGREES_PER_DAY: Record<ScenarioPace, number> = {
  slow: 0.35,
  baseline: 0.65,
  fast: 1,
};
export function scenarioRadius(
  day: number,
  pace: ScenarioPace,
  response: number,
): number {
  const boundedDay = Math.max(
    0,
    Math.min(SCENARIO_DAYS, Number.isFinite(day) ? day : 0),
  );
  const responseFactor =
    1 -
    Math.max(0, Math.min(100, Number.isFinite(response) ? response : 0)) *
      0.007;
  return 2 + boundedDay * PACE_DEGREES_PER_DAY[pace] * responseFactor;
}

export const SCENARIO_METHOD =
  "An illustrative surface-expansion model, not an epidemiological forecast. Day 0 starts at a user-selected country reference point. A geodesic envelope expands at a chosen visual pace and is clipped to land. Response strength reduces that illustrative expansion. It does not use population, transport, case counts, incubation periods, or disease-specific transmission parameters. No infected population or pandemic probability is calculated.";
