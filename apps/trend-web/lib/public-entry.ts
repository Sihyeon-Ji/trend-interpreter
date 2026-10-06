import type { TermRecord } from "./types";

const approved = (value: string | undefined) => value === "verified_auto" || value === "verified_human";

export function isPublicRecord(record: TermRecord): boolean {
  const current = record.meanings.filter((m) => m.valid_to == null).at(-1);
  return record.term.status === "verified" && !!current && approved(current.verification);
}

export function publicRecord(record: TermRecord): TermRecord {
  return { ...record, meanings: record.meanings.filter((m) => approved(m.verification)), gate_reasons: undefined };
}
