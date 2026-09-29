import { NextResponse, type NextRequest } from "next/server";
import { loadSearchIndex } from "@/lib/lab/o-report-data";

/* 프레임 찾기 칸의 색인 — 확인된 밈의 이름·다른 표기·뜻 한 줄만(사전 전체 2MB 대신 수십 KB). 처음 칸을 쓸 때 한 번 받는다. */
export async function GET(req: NextRequest) {
  const locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  const items = await loadSearchIndex(locale);
  if (!items) return NextResponse.json({ error: "dictionary unavailable" }, { status: 503 });
  return NextResponse.json(items, { headers: { "cache-control": "public, max-age=60" } });
}
