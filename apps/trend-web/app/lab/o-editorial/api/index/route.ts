import type { NextRequest } from "next/server";
import { dictionaryIndex } from "@/lib/lab/o-editorial/data";
import { getLocale } from "@/lib/locale";

/* 머리 찾기 칸의 바로 보기용 색인 — 읽기 전용. 확인된 밈의 이름·다른 표기·뜻 한 줄·쓸 때 조심·단계만 넘긴다(근거는 싣지 않는다).
   화면 언어는 ?l= (브라우저 캐시가 언어마다 따로 남게), 없으면 쿠키. 사전을 못 받으면 502 — 칸은 평범한 찾기 폼으로 돌아간다. */
export async function GET(req: NextRequest) {
  const l = req.nextUrl.searchParams.get("l");
  const index = await dictionaryIndex(l === "en" || l === "ko" ? l : await getLocale());
  if (!index) return Response.json({ error: "unavailable" }, { status: 502 });
  return Response.json(index, { headers: { "cache-control": "private, max-age=300" } });
}
