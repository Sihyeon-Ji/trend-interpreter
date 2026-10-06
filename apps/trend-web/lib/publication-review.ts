import type { Evidence, Meaning, MeaningDraft, MeaningText, Term } from "./types";

export type BatchStatus = "draft" | "approved" | "rejected" | "published" | "conflict" | "failed";
export type BatchSummary = {
  batch_id: string; payload_sha256: string; status: BatchStatus; created_at: string;
  reviewed_by: string | null; reviewed_at: string | null; failure_code: string | null; item_count: number;
};
export type BatchComparison = {
  batch: {
    batch_id: string; snapshot_id: string; snapshot_sha256: string; model_id: string; prompt_version: string; rule_version: string;
    items: {
      term_id: string; expected_meaning_id: string | null;
      new_term: { canonical: string; lang: string; aliases: string[] } | null;
      meaning: MeaningDraft | null; evidences: Evidence[]; citations: string[];
      translations: Record<string, MeaningText>; country_notes: Record<string, unknown>;
      fit: unknown; derived_from_sha256: string | null;
    }[];
  };
  payload_sha256: string; status: BatchStatus; reviewed_by: string | null; reviewed_at: string | null;
  failure_code: string | null; validation: Record<string, string[]>;
  current: Record<string, {
    term: Term | null; meaning: Meaning | null; translations: Record<string, MeaningText>;
    country_notes: Record<string, unknown>; evidences: Evidence[]; fit: unknown; baseline_changed: boolean;
  }>;
};

export function batchDecision(raw: unknown): {
  payload_sha256: string; decision: "approve" | "reject"; allow_gate_exceptions: boolean;
} | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const body = raw as Record<string, unknown>;
  if (typeof body.payload_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(body.payload_sha256)) return null;
  if (body.decision !== "approve" && body.decision !== "reject") return null;
  if (body.allow_gate_exceptions !== undefined && typeof body.allow_gate_exceptions !== "boolean") return null;
  // Reviewer identity is supplied by the signed server session, never by the browser.
  return { payload_sha256: body.payload_sha256, decision: body.decision, allow_gate_exceptions: body.allow_gate_exceptions === true };
}
