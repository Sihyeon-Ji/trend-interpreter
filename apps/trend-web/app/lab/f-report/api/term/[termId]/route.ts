import type { NextRequest } from "next/server";
import { getTermRecord } from "@/lib/data";
import { toDetail } from "@/lib/lab/f-report-detail";

/** 미리보기·지켜보기용 항목 요약(읽기 전용). 브라우저는 백엔드에 직접 가지 않는다 — 서버가 받아서 화면에 필요한 것만 돌려준다. */
export async function GET(req: NextRequest, { params }: { params: Promise<{ termId: string }> }) {
  const { termId } = await params;
  const locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  try {
    const record = await getTermRecord(termId);
    if (!record) return Response.json({ error: "not_found" }, { status: 404 });
    return Response.json(toDetail(record, locale), { headers: { "cache-control": "private, max-age=60" } });
  } catch {
    return Response.json({ error: "unavailable" }, { status: 503 });
  }
}
