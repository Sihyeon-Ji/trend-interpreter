import type { NextRequest } from "next/server";
import { getCardsByIds } from "@/lib/lab/o-editorial-data";

/* 스크랩한 밈의 지금 상태 — 읽기 전용. 브라우저는 백엔드를 직접 부르지 않고 같은 사이트의 이 경로를 거친다.
   화면에 필요한 칸만 넘긴다: 근거(커뮤니티 글 제목이 들어 있다)는 브라우저로 보내지 않는다. */
export async function GET(req: NextRequest) {
  const ids = (req.nextUrl.searchParams.get("ids") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const cards = await getCardsByIds(ids);
  if (!cards) return Response.json({ error: "unavailable" }, { status: 502 });
  return Response.json(cards.map((c) => ({
    term_id: c.term_id, canonical: c.canonical, lang: c.lang, lifecycle: c.lifecycle, diffusion: c.diffusion ?? null,
    risk_level: c.risk_level ?? null, risk_checked_at: c.risk_checked_at ?? null,
  })), { headers: { "cache-control": "private, max-age=60" } });
}
