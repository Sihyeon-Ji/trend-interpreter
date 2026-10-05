import { expect, test } from "@playwright/test";
import { packRows, unpackRows, type DictionaryRow } from "../lib/dictionary/rows";

const row: DictionaryRow = {
  term_id: "t1", canonical: "럭키비키", lang: "ko", aliases: ["원영적 사고"], expansion: null,
  definition: "나쁜 일도 결국 잘된 일이라고 여기는 태도.", meaning_lang: null, category: "slang", diffusion: "mainstream",
  lifecycle: "steady", regions: ["KR"], last_used: "2026-09-30T08:02:56Z", changed: "2026-09-30", risk_level: null,
  risk_checked_at: null, generations: ["20s"], alt: null,
};

test("dictionary rows survive the compact transport unchanged and drop the repeated field names", () => {
  const packed = packRows([row, { ...row, term_id: "t2", risk_level: "caution", risk_checked_at: "2026-10-05" }]);
  expect(unpackRows(packed)).toEqual([row, { ...row, term_id: "t2", risk_level: "caution", risk_checked_at: "2026-10-05" }]);
  expect(JSON.stringify(packed)).not.toContain("definition");
});
