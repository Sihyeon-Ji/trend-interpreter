/* 문구 승인 기록의 같은 사이트 라우트(app/api/approvals). 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 세션과 권한을 확인하고,
   본문을 거른 뒤 서버만 아는 토큰(FRONTEND_API_TOKEN)을 붙여 넘긴다. 요청한 사람·결정한 사람의 이름은 서명된 세션에서만 가져온다.
     요청       로그인한 계정만(익명 문구는 받지 않는다). 읽기 전용 계정은 보기만 한다
     바로 승인  검수자만(요청과 승인을 한 번에 적는다)
     결정       검수자만, 읽기 전용 계정은 못 한다
   예시 모드는 백엔드가 없다 — 권한 검사는 같게 하고, 규칙 검사는 예시 사전으로 해서 돌려주되 아무것도 적지 않는다(sample: true).
   응답에는 문구 본문을 싣지 않고, 이 라우트는 본문을 로그에 쓰지 않는다. */
import type { ApiRequestInit } from "./api-transport";
import { approvalDecision, approvalRequest, copyIssues, fullText, groupOf } from "./approval";
import type { Viewer } from "./reviewer-access";
import { isSameOrigin } from "./same-origin";
import type { ApprovalState, CopyCheck } from "./types";

type Deps = {
  viewer: () => Promise<Viewer | null>;
  token: () => string | undefined;
  fetcher: (path: string, init: ApiRequestInit) => Promise<Response>;
  sample: boolean;
  sampleCheck: (text: string, region: string) => CopyCheck;
};
type Ctx = { params: Promise<{ id: string }> };

const MAX_BODY = 48 * 1024;
const HEADERS = { "Cache-Control": "private, no-store" };
const fail = (error: string, status: number, extra: Record<string, unknown> = {}) => Response.json({ error, ...extra }, { status, headers: HEADERS });

function tooBig(req: Request): boolean {
  const length = req.headers.get("content-length");
  return length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BODY);
}

/** 백엔드 오류 → 화면이 언어별 문구로 옮기는 코드. 409 는 막힘·이미 결정함·본문 없음을 가른다 */
async function backendError(res: Response): Promise<Response> {
  if (res.status === 409) {
    const j = (await res.json().catch(() => ({}))) as { detail?: string; reasons?: string[] };
    const code = j.detail === "blocked" || j.detail === "decided" || j.detail === "expired" ? j.detail : "conflict";
    return fail(code, 409, { reasons: j.reasons ?? [] });
  }
  if (res.status === 404) return fail("missing", 404);
  if (res.status === 403) return fail("forbidden", 403);
  if (res.status === 429) return fail("busy", 429);
  return fail("failed", 502);
}

export function createApprovalHandlers(deps: Deps) {
  /** 초안 화면의 '검수 요청'·검수자의 바로 승인 */
  async function create(req: Request): Promise<Response> {
    const account = await deps.viewer();
    if (!account) return fail("signed_out", 401);
    if (account.readOnly) return fail("readonly", 403);
    if (!isSameOrigin(req)) return fail("same_origin_required", 403);
    if (tooBig(req)) return fail("too_big", 413);
    let body;
    try { body = approvalRequest(await req.json()); } catch { body = null; }
    if (!body) return fail("bad_request", 400);
    if (body.decision === "approve" && !account.reviewer) return fail("reviewer_required", 403);
    if (deps.sample) {
      const issues = body.copies.map((c) => copyIssues(deps.sampleCheck(fullText(c), body.market)));
      const { group, reasons } = groupOf(issues, body.fit);
      const approve = body.decision === "approve";
      if (approve && group === "blocked") return fail("blocked", 409, { reasons });
      const at = new Date().toISOString();
      const state: ApprovalState = {
        approval_id: `sample-${crypto.randomUUID().slice(0, 12)}`, market: body.market, status: approve ? "approved" : "pending", group, reasons,
        image_meme: false, requested_by: account.user, requested_at: at,
        decided_by: approve ? account.user : null, decided_at: approve ? at : null, memo: null, sample: true,
      };
      return Response.json(state, { headers: HEADERS });
    }
    const token = deps.token();
    if (!token) return fail("not_configured", 503);
    try {
      const res = await deps.fetcher("/approvals", {
        method: "POST", headers: { "content-type": "application/json", "x-frontend-token": token },
        body: JSON.stringify({ ...body, by: account.user }), cache: "no-store",
      });
      return res.ok ? Response.json(await res.json(), { headers: HEADERS }) : backendError(res);
    } catch {
      return fail("unreachable", 502);
    }
  }

  /** 요청의 지금 상태 — 요청한 사람(자기 것)이나 검수자만. 본문은 없다 */
  async function state(_req: Request, { params }: Ctx): Promise<Response> {
    const account = await deps.viewer();
    if (!account) return fail("signed_out", 401);
    const { id } = await params;
    if (deps.sample || !/^[A-Za-z0-9_-]{1,64}$/.test(id)) return fail("missing", 404);   // 예시 요청은 적지 않았다
    const token = deps.token();
    if (!token) return fail("not_configured", 503);
    try {
      const res = await deps.fetcher(`/approvals/${encodeURIComponent(id)}?viewer=${encodeURIComponent(account.user)}`, {
        headers: { "x-frontend-token": token }, cache: "no-store",
      });
      return res.ok ? Response.json(await res.json(), { headers: HEADERS }) : backendError(res);
    } catch {
      return fail("unreachable", 502);
    }
  }

  /** 관리 화면의 승인·반려 */
  async function decide(req: Request, { params }: Ctx): Promise<Response> {
    const account = await deps.viewer();
    if (!account) return fail("signed_out", 401);
    if (!account.reviewer) return fail("reviewer_required", 403);
    if (account.readOnly) return fail("readonly", 403);
    if (!isSameOrigin(req)) return fail("same_origin_required", 403);
    if (tooBig(req)) return fail("too_big", 413);
    let body;
    try { body = approvalDecision(await req.json()); } catch { body = null; }
    const { id } = await params;
    if (!body || !/^[A-Za-z0-9_-]{1,64}$/.test(id)) return fail("bad_request", 400);
    if (deps.sample) {
      const at = new Date().toISOString();
      return Response.json({ approval_id: id, status: body.decision === "approve" ? "approved" : "rejected", decided_by: account.user,
        decided_at: at, memo: body.memo || null, sample: true }, { headers: HEADERS });
    }
    const token = deps.token();
    if (!token) return fail("not_configured", 503);
    try {
      const res = await deps.fetcher(`/review/approvals/${encodeURIComponent(id)}/decision`, {
        method: "POST", headers: { "content-type": "application/json", "x-frontend-token": token },
        body: JSON.stringify({ ...body, by: account.user }), cache: "no-store",
      });
      return res.ok ? Response.json(await res.json(), { headers: HEADERS }) : backendError(res);
    } catch {
      return fail("unreachable", 502);
    }
  }

  return { create, state, decide };
}
