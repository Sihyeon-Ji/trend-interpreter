/* 검수 결정 요청의 모양. 브라우저가 보낸 본문을 같은 사이트의 app/api/review/[termId] 가 이것으로 거른 뒤 백엔드로 넘긴다.
   결정한 사람(by)은 여기서 받지 않는다 — 라우트가 세션에서 넣는다. 백엔드(api/app.py ReviewIn)와 같은 칸이다. */

export const REVIEW_DECISION_KINDS = ["new", "correction", "conflict", "retire"] as const;

export type ReviewDecisionBody = {
  decision: "approve" | "reject";
  meaning_id: string | null;   // 검수자가 본 뜻 — 그사이 새 판이 생겼으면 백엔드가 409
  kind: (typeof REVIEW_DECISION_KINDS)[number] | null;   // 검수자가 본 제안의 종류 — 승인의 뜻이 종류마다 달라 백엔드가 대기 제안과 맞춰 본다
  token: string | null;        // 검수자가 본 제안의 표 — 그사이 다른 제안이 올라왔으면 백엔드가 409
  choice: string | null;       // 위키끼리 다름: 고른 문서의 주소, 또는 "keep"(지금 뜻 그대로)
};

export type ReviewDecisionResult = { ok: true; body: ReviewDecisionBody } | { ok: false; error: string };

const BAD = "요청 형식이 잘못됐습니다.";

/** 모양이 맞으면 넘길 본문, 아니면 화면에 보일 까닭. choice 는 "keep" 이나 문서 주소(http·https)만, token 은 짧은 문자열만 받는다. */
export function reviewDecision(raw: unknown): ReviewDecisionResult {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { ok: false, error: BAD };
  const r = raw as Record<string, unknown>;
  const { decision } = r;
  const meaningId = r.meaning_id ?? null;
  const kind = r.kind ?? null;
  const token = r.token ?? null;
  const choice = r.choice ?? null;
  if (decision !== "approve" && decision !== "reject") return { ok: false, error: "결정은 승인 또는 제외만 기록합니다." };
  if (meaningId !== null && typeof meaningId !== "string") return { ok: false, error: BAD };
  if (kind !== null && !(typeof kind === "string" && (REVIEW_DECISION_KINDS as readonly string[]).includes(kind))) return { ok: false, error: BAD };
  if (token !== null && !(typeof token === "string" && token.length > 0 && token.length <= 64)) return { ok: false, error: BAD };
  if (choice !== null && !(choice === "keep" || (typeof choice === "string" && choice.length <= 2048 && /^https?:\/\/\S+$/.test(choice)))) {
    return { ok: false, error: BAD };
  }
  return { ok: true, body: { decision, meaning_id: meaningId, kind: kind as ReviewDecisionBody["kind"], token, choice } };
}
