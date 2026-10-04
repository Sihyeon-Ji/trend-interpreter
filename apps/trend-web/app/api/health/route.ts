import { NextResponse } from "next/server";

/* 웹 서버가 살아 있는지만 — 백엔드를 부르지 않는다. 컨테이너 상태 점검이 첫 화면(/)을 몇 초마다 그려
   대시보드·브리핑 API 를 끝없이 불렀다(10-04). */
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ ok: true });
}
