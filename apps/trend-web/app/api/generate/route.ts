import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { TARGET_REGIONS } from "@/lib/reader";
import { sampleGenerate } from "@/lib/sample/generate";
import type { CampaignTone, ProductBrief } from "@/lib/types";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];

/** 카피·대본·썸네일 만들기 (Plan 08). 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 한 번 거르고 넘긴다. 결과는 저장하지 않는다. */
export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { term_ids?: unknown; brief?: ProductBrief; region?: string; tone?: string; lang?: string } | null;
  const termIds = Array.isArray(body?.term_ids) ? body.term_ids.filter((x): x is string => typeof x === "string" && x.length <= 64).slice(0, 3) : [];
  const region = String(body?.region ?? "").toUpperCase();
  const tone = (TONES.includes(body?.tone as CampaignTone) ? body?.tone : "friendly") as CampaignTone;
  const lang = body?.lang === "en" ? "en" : "ko";
  if (!termIds.length) return NextResponse.json({ error: "need_pick" }, { status: 400 });
  if (!TARGET_REGIONS.includes(region) || !body?.brief) return NextResponse.json({ error: "failed" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(sampleGenerate(termIds, region, tone));

  let res: Response;
  try {
    res = await fetch(`${API}/generate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ term_ids: termIds, brief: body.brief, region, tone, lang }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "failed" }, { status: 502 });
  }
  if (!res.ok) return NextResponse.json({ error: "failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
