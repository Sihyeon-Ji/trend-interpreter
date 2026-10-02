import { NextResponse, type NextRequest } from "next/server";
import { loadSearchIndex } from "@/lib/lab/f-report/search-server";

/** 찾기 칸의 색인(읽기 전용). 브라우저는 백엔드에 직접 가지 않는다 — 서버가 사전을 받아 이름·다른 표기·뜻 한 줄만 돌려준다. */
export async function GET(req: NextRequest) {
  const locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  const items = await loadSearchIndex(locale);
  if (!items) return NextResponse.json({ error: "unavailable" }, { status: 503 });
  return NextResponse.json(items, { headers: { "cache-control": "public, max-age=60" } });
}
