/* 문구 승인 기록의 규칙과 요청 모양 (Plan 20 ⑤). 묶음 규칙은 백엔드 storage/approvals.py 의 group·copy_issues 와 같다 —
   초안 화면은 이것으로 단추를 막고(막힘), 서버는 받은 결과를 믿지 않고 사전으로 다시 검사한다. 브라우저·서버 어디서나 쓴다(훅 없음). */
import { WRITE_REGIONS } from "./reader";
import type { ApprovalGroup, CopyCheck } from "./types";

/** 승인할 수 없게 막는 규칙 코드 — 사용 자제·저속한 말투·욕설과 선정 표현 */
export const BLOCKING = ["avoid", "crude", "unsafe"] as const;
/** 읽어 보고 정할 규칙 표시 */
export const FLAGS = ["caution", "sensitive", "undecided", "fading", "not_in_region", "no_script"] as const;
const ORDER: readonly string[] = [...BLOCKING, ...FLAGS];
export const isBlocking = (code: string) => (BLOCKING as readonly string[]).includes(code);

export type Fit = "ok" | "off" | "unsure";

/** 문구 하나의 규칙 코드 — 문구에 든 밈의 문제와 욕설·선정(unsafe). 막는 것 먼저, 같은 코드는 한 번 */
export function copyIssues(check: CopyCheck | null | undefined): string[] {
  if (!check) return [];
  const found = new Set<string>(check.memes.flatMap((m) => m.issues.map((i) => i.code)));
  if (check.unsafe) found.add("unsafe");
  return ORDER.filter((c) => found.has(c));
}

/** 묶음과 이유 — 규칙 코드와 AI 의견(받지 못했으면 null)으로만. 점수로 줄 세우지 않는다 */
export function groupOf(issues: string[][], fit: Fit | null | undefined): { group: ApprovalGroup; reasons: string[] } {
  const seen = new Set(issues.flat());
  const reasons = ORDER.filter((c) => seen.has(c));
  if (fit !== "ok") reasons.push(fit === "off" ? "fit_off" : fit === "unsure" ? "fit_unsure" : "fit_none");
  if (reasons.some(isBlocking)) return { group: "blocked", reasons };
  return reasons.length ? { group: "read", reasons } : { group: "clean", reasons: [] };
}

/** 다시 검사하는 글 — 본문과 해시태그(백엔드 generate.copy_text 와 같다) */
export const fullText = (c: { text: string; hashtags?: string[] | null }) =>
  [c.text, (c.hashtags ?? []).map((h) => `#${h}`).join(" ")].filter(Boolean).join("\n\n");

export type ApprovalCopyIn = { platform: "instagram" | "x"; text: string; hashtags: string[] };
export type ApprovalRequest = {
  market: string; term_id: string; product: string; copies: ApprovalCopyIn[];
  fit: Fit | null; fit_note: string | null; fit_copy: number | null; decision: "approve" | null;
};

const str = (v: unknown, n: number) => (typeof v === "string" ? v.trim().slice(0, n) : "");
const FITS: readonly string[] = ["ok", "off", "unsure"];

/** 승인 요청 본문 — 브라우저가 보낸 것을 아는 칸만 새로 만든다. 누가 요청했는지(by)는 받지 않는다(라우트가 세션에서 넣는다).
 *  묶음·검사 결과도 받지 않는다 — 서버가 다시 검사한다. 모양이 틀리면 null */
export function approvalRequest(raw: unknown): ApprovalRequest | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  const market = str(r.market, 12).toUpperCase();
  const termId = str(r.term_id, 121);
  if (!WRITE_REGIONS.includes(market) || !/^[A-Za-z0-9_.:-]{1,120}$/.test(termId)) return null;
  if (!Array.isArray(r.copies) || r.copies.length < 1 || r.copies.length > 6) return null;
  const copies: ApprovalCopyIn[] = [];
  for (const c of r.copies as unknown[]) {
    if (!c || typeof c !== "object") return null;
    const x = c as Record<string, unknown>;
    const text = typeof x.text === "string" ? x.text.trim() : "";
    if ((x.platform !== "instagram" && x.platform !== "x") || !text || text.length > 1000) return null;
    const tags = Array.isArray(x.hashtags) ? x.hashtags : [];
    copies.push({ platform: x.platform, text, hashtags: tags.filter((h): h is string => typeof h === "string").map((h) => h.trim().slice(0, 60)).filter(Boolean).slice(0, 10) });
  }
  const fitCopy = typeof r.fit_copy === "number" && Number.isInteger(r.fit_copy) && r.fit_copy >= 0 && r.fit_copy < copies.length ? r.fit_copy : null;
  const fit = fitCopy != null && typeof r.fit === "string" && FITS.includes(r.fit) ? (r.fit as Fit) : null;
  if (r.decision != null && r.decision !== "approve") return null;
  return {
    market, term_id: termId, product: str(r.product, 200), copies,
    fit, fit_note: fit ? str(r.fit_note, 300) || null : null, fit_copy: fit ? fitCopy : null,
    decision: r.decision === "approve" ? "approve" : null,
  };
}

/** 관리 화면의 결정 — 승인·반려와 메모(500자). 결정한 사람은 받지 않는다 */
export function approvalDecision(raw: unknown): { decision: "approve" | "reject"; memo: string } | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  if (r.decision !== "approve" && r.decision !== "reject") return null;
  if (r.memo != null && typeof r.memo !== "string") return null;
  return { decision: r.decision, memo: str(r.memo, 500) };
}
