import type { NextRequest } from "next/server";
import { loadPreview } from "@/lib/lab/o-report/data";

/* 미리보기 — 목록에서 밈을 누를 때 받는다(첫 화면이 밈마다 사전 항목을 받던 것, 09-29 검토). 읽기 전용.
   사전 항목(수십 KB, 커뮤니티 글 포함)을 화면에 필요한 칸만 추려 보낸다 — 커뮤니티 글은 브라우저에 가지 않는다. */
export async function GET(req: NextRequest, { params }: { params: Promise<{ termId: string }> }) {
  const { termId } = await params;
  const locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  try {
    const preview = await loadPreview(termId, locale);
    if (!preview) return Response.json({ error: "not_found" }, { status: 404 });
    return Response.json(preview, { headers: { "cache-control": "private, max-age=60" } });
  } catch {
    return Response.json({ error: "unavailable" }, { status: 503 });
  }
}
