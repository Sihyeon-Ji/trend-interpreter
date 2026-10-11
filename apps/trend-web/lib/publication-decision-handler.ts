import type { ApiRequestInit } from "./api-transport";
import type { Viewer } from "./reviewer-access";
import { batchDecision } from "./publication-review";

export function createBatchDecisionHandler(
  viewer: () => Promise<Viewer | null>,
  tokenValue: () => string | undefined,
  fetcher: (path: string, init: ApiRequestInit) => Promise<Response>,
) {
  return async function POST(req: Request, { params }: { params: Promise<{ batchId: string }> }) {
    const headers = { "Cache-Control": "private, no-store" };
    const account = await viewer();
    if (!account) return Response.json({ error: "authentication_required" }, { status: 401, headers });
    if (!account.reviewer) return Response.json({ error: "reviewer_required" }, { status: 403, headers });
    if (account.readOnly) return Response.json({ error: "readonly_account" }, { status: 403, headers });
    // Production proxies can give Next.js an internal URL while preserving the public Host.
    const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? new URL(req.url).host;
    let sameOrigin = false;
    try {
      const origin = new URL(req.headers.get("origin") ?? "");
      sameOrigin = ["https:", "http:"].includes(origin.protocol) && origin.host === host;
    } catch { /* Missing or malformed origins fail closed. */ }
    if (!sameOrigin) {
      return Response.json({ error: "same_origin_required" }, { status: 403, headers });
    }
    const token = tokenValue();
    if (!token) return Response.json({ error: "review_server_unavailable" }, { status: 503, headers });
    let body;
    try { body = batchDecision(await req.json()); } catch { body = null; }
    if (!body) return Response.json({ error: "invalid_decision" }, { status: 400, headers });
    const { batchId } = await params;
    try {
      const response = await fetcher(`/review/batches/${encodeURIComponent(batchId)}/decision`, {
        method: "POST", headers: { "content-type": "application/json", "x-frontend-token": token },
        body: JSON.stringify({ ...body, by: account.user }), cache: "no-store",
      });
      if (!response.ok) return Response.json({ error: response.status === 409 ? "review_conflict" : "review_failed" }, { status: response.status, headers });
      return Response.json(await response.json(), { headers });
    } catch {
      return Response.json({ error: "review_server_unavailable" }, { status: 502, headers });
    }
  };
}
