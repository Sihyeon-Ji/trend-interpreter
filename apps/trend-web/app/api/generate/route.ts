import { apiFetch } from "@/lib/api-fetch";
import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { L } from "@/lib/labels";
import { WRITE_REGIONS } from "@/lib/reader";
import { sampleGenerate } from "@/lib/sample/generate";
import type { CampaignTone, Feeling, FitCategory, ProductBrief } from "@/lib/types";

const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
const MAX_BODY = 16 * 1024;   // 밈 id 몇 개와 제품 설명(수백 자)뿐이다
const CATEGORIES = Object.keys(L("ko").fitCategory) as FitCategory[];
const FEELINGS = Object.keys(L("ko").feeling) as Feeling[];

const text = (v: unknown, n: number) => (typeof v === "string" ? v.trim().slice(0, n) : "");
const list = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string").map((x) => x.trim().slice(0, 40)).filter(Boolean).slice(0, 5) : []);

/** 추천이 읽어 낸 제품 설명을 브라우저에서 다시 받는다 — 아는 칸만, 길이를 잘라 새로 만든다(검토 3차: 수백 KB 설명이 생성 프롬프트로 갔다).
 *  백엔드 ProductBrief 도 같은 길이로 자른다. */
function cleanBrief(b: unknown): ProductBrief | null {
  if (!b || typeof b !== "object") return null;
  const x = b as Record<string, unknown>;
  const product = text(x.product, 120);
  if (!product) return null;
  return {
    product,
    category: CATEGORIES.includes(x.category as FitCategory) ? (x.category as FitCategory) : "lifestyle",
    feelings: list(x.feelings).filter((f): f is Feeling => FEELINGS.includes(f as Feeling)).slice(0, 3),
    values: list(x.values),
    scene: text(x.scene, 200),
    colors: list(x.colors),
    avoid: list(x.avoid),
  };
}

/** 카피·대본·썸네일 만들기 (Plan 08). 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 한 번 거르고 넘긴다. 결과는 저장하지 않는다. */
export async function POST(req: Request) {
  const length = req.headers.get("content-length");
  if (length === null) return NextResponse.json({ error: "failed" }, { status: 411 });
  if (!/^\d+$/.test(length) || Number(length) > MAX_BODY) return NextResponse.json({ error: "failed" }, { status: 413 });
  const body = (await req.json().catch(() => null)) as { term_ids?: unknown; brief?: unknown; region?: string; tone?: string; lang?: string } | null;
  const termIds = Array.isArray(body?.term_ids) ? body.term_ids.filter((x): x is string => typeof x === "string" && x.length <= 64).slice(0, 3) : [];
  const region = String(body?.region ?? "").toUpperCase();
  const tone = (TONES.includes(body?.tone as CampaignTone) ? body?.tone : "friendly") as CampaignTone;
  const lang = body?.lang === "en" ? "en" : "ko";
  const brief = cleanBrief(body?.brief);
  if (!termIds.length) return NextResponse.json({ error: "need_pick" }, { status: 400 });
  if (!WRITE_REGIONS.includes(region) || !brief) return NextResponse.json({ error: "failed" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(sampleGenerate(termIds, region, tone));

  let res: Response;
  try {
    res = await apiFetch(`/generate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ term_ids: termIds, brief, region, tone, lang }),
      cache: "no-store",
      signal: req.signal,   // 화면에서 '그만두기' 를 누르거나 창을 닫으면 백엔드 요청도 끊는다
    });
  } catch {
    return NextResponse.json({ error: req.signal.aborted ? "aborted" : "failed" }, { status: req.signal.aborted ? 499 : 502 });
  }
  if (!res.ok) return NextResponse.json({ error: res.status === 429 ? "busy" : "failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
