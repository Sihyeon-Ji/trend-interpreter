import type { NextRequest } from "next/server";
import { loadWatchStates } from "@/lib/lab/o-report-data";

/* 지켜보는 밈 가운데 지금 목록 밖에 있는 것의 지금 단계·쓸 때 조심 — 읽기 전용. 지켜보는 목록은 브라우저에만 있으므로
   브라우저가 id 만 보낸다(최대 60개). 사전에서 빠진 밈은 gone 으로 알린다. */
export async function GET(req: NextRequest) {
  const ids = (req.nextUrl.searchParams.get("ids") ?? "").split(",").map((s) => s.trim()).filter(Boolean).slice(0, 60);
  const locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  if (!ids.length) return Response.json([]);
  const states = await loadWatchStates(ids, locale);
  return Response.json(states, { headers: { "cache-control": "private, max-age=60" } });
}
