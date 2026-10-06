import { expect, test } from "@playwright/test";
import { isPublicRecord, publicRecord } from "../lib/public-entry";
import { SAMPLE_RECORDS } from "../lib/sample/dictionary";

test("public data requires both a verified term and an approved current meaning", () => {
  const record = SAMPLE_RECORDS.find((r) => r.term.term_id === "t_luckyvicky")!;
  expect(isPublicRecord(record)).toBe(true);
  expect(isPublicRecord({ ...record, term: { ...record.term, status: "needs_review" } })).toBe(false);
  const current = record.meanings.find((m) => m.valid_to == null)!;
  expect(isPublicRecord({ ...record, meanings: [{ ...current, verification: "unverified" }] })).toBe(false);
  expect(isPublicRecord({ ...record, meanings: [] })).toBe(false);
});

test("public history never contains an unapproved draft", () => {
  const record = SAMPLE_RECORDS.find((r) => r.term.term_id === "t_luckyvicky")!;
  const current = record.meanings.find((m) => m.valid_to == null)!;
  const withDraft = {
    ...record,
    meanings: [{ ...current, meaning_id: "unapproved-old-draft", verification: "unverified" as const, valid_to: current.valid_from }, ...record.meanings],
    gate_reasons: ["private review reason"],
  };
  const published = publicRecord(withDraft);
  expect(published.meanings.some((m) => m.meaning_id === "unapproved-old-draft")).toBe(false);
  expect(published.gate_reasons).toBeUndefined();
  expect(withDraft.meanings.some((m) => m.meaning_id === "unapproved-old-draft")).toBe(true);
});
