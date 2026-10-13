import { expect, test } from "@playwright/test";
import { matchesExceptRegion, packRows, toRow, unpackRows, type DictionaryRow } from "../lib/dictionary/rows";
import { SAMPLE_RECORDS } from "../lib/sample/dictionary";
import type { TermUsage } from "../lib/types";

const row: DictionaryRow = {
  term_id: "t1", canonical: "럭키비키", lang: "ko", aliases: ["원영적 사고"], expansion: null,
  definition: "나쁜 일도 결국 잘된 일이라고 여기는 태도.", meaning_lang: null, category: "slang", diffusion: "mainstream",
  lifecycle: "steady", regions: ["KR"], last_used: "2026-09-30T08:02:56Z", changed: "2026-09-30", risk_level: null,
  risk_checked_at: null, generations: ["20s"], alt: null, reading: null, name: null,
};

test("dictionary rows survive the compact transport unchanged and drop the repeated field names", () => {
  const packed = packRows([row, { ...row, term_id: "t2", risk_level: "caution", risk_checked_at: "2026-10-05" }]);
  expect(unpackRows(packed)).toEqual([row, { ...row, term_id: "t2", risk_level: "caution", risk_checked_at: "2026-10-05" }]);
  expect(JSON.stringify(packed)).not.toContain("definition");
});

test("generation filtering uses measured ages instead of a model's meaning", () => {
  const estimated: TermUsage = { segment: { segment_id: "JP-20s", generation: "20s", region: "JP" }, first_seen: "2026-01-01", share: 1, source: "model" };
  const measured: TermUsage = { segment: { segment_id: "JP-30s", generation: "30s", region: "JP" }, first_seen: "2026-01-02", share: 1, source: "datalab" };
  const record = { ...SAMPLE_RECORDS[0], usage: [estimated] };
  expect(toRow(record, "ko").generations).toEqual([]);
  expect(toRow({ ...record, usage: [estimated, measured] }, "ko").generations).toEqual(["30s"]);
});

test("a headword reading follows the screen language and can be searched", () => {
  const record = { ...SAMPLE_RECORDS[0], readings: { ja: "ラッキービッキー", en: "Lucky Vicky" } };
  expect(toRow(record, "ja").reading).toBe("ラッキービッキー");
  expect(toRow(record, "en").reading).toBe("Lucky Vicky");
  expect(toRow(record, "ko").reading).toBeNull();
  const filters = { q: "ラッキー", regions: [], kind: "", lang: "", risk: "" };
  expect(matchesExceptRegion({ ...row, reading: "ラッキービッキー" }, filters)).toBe(true);
  expect(matchesExceptRegion(row, filters)).toBe(false);
});

test("a word from abroad shows its original name on that language's screen, without a reading", () => {
  const record = { ...SAMPLE_RECORDS[0], names: { ja: "牛丼" }, readings: { ja: "キュドン", en: "gyudong" } };
  const ja = toRow(record, "ja");
  expect([ja.name, ja.reading]).toEqual(["牛丼", null]);           // 원어 이름이 있으면 읽기는 붙이지 않는다
  expect(toRow(record, "en")).toMatchObject({ name: null, reading: "gyudong" });
  expect(matchesExceptRegion({ ...row, name: "牛丼" }, { q: "牛丼", regions: [], kind: "", lang: "", risk: "" })).toBe(true);
});
