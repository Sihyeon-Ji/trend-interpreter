import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api-fetch";
import { isSampleMode } from "@/lib/data";
import { L } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { samplePoster } from "@/lib/sample/poster";
import type { Feeling, FitCategory, ProductBrief } from "@/lib/types";

const MAX_BODY = 16 * 1024;   // 밈 id 셋과 제품 설명뿐 — 사진은 이 경로로 받지 않는다(만들기 화면은 추천에서 이미 읽은 설명을 넘긴다)
const CATEGORIES = Object.keys(L("ko").fitCategory) as FitCategory[];
const FEELINGS = Object.keys(L("ko").feeling) as Feeling[];
const text = (v: unknown, n: number) => (typeof v === "string" ? v.trim().slice(0, n) : "");
const list = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string").map((x) => x.trim().slice(0, 40)).filter(Boolean).slice(0, 5) : []);

/** 추천이 읽어 낸 제품 설명을 아는 칸만 다시 만든다(/api/generate 와 같은 거름). */
function cleanBrief(b: unknown): ProductBrief | null {
  if (!b || typeof b !== "object") return null;
  const x = b as Record<string, unknown>;
  const product = text(x.product, 120);
  if (!product) return null;
  return {
    product, category: CATEGORIES.includes(x.category as FitCategory) ? (x.category as FitCategory) : "lifestyle",
    feelings: list(x.feelings).filter((f): f is Feeling => FEELINGS.includes(f as Feeling)).slice(0, 3),
    values: list(x.values), scene: text(x.scene, 200), colors: list(x.colors), avoid: list(x.avoid),
  };
}

/** 시장별 포스터 시안 (Plan 20). 브라우저는 백엔드를 직접 부르지 않는다. 그림이 꺼져 있으면 백엔드가 구성안만 돌려준다. 결과는 저장하지 않는다. */
export async function POST(req: Request) {
  const length = req.headers.get("content-length");
  if (length === null) return NextResponse.json({ error: "failed" }, { status: 411 });
  if (!/^\d+$/.test(length) || Number(length) > MAX_BODY) return NextResponse.json({ error: "failed" }, { status: 413 });
  const body = (await req.json().catch(() => null)) as { market?: unknown; brief?: unknown; term_ids?: unknown } | null;
  const market = String(body?.market ?? "").toUpperCase();
  const brief = cleanBrief(body?.brief);
  const termIds = Array.isArray(body?.term_ids) ? body.term_ids.filter((x): x is string => typeof x === "string" && /^[\w.:-]{1,64}$/.test(x)).slice(0, 3) : [];
  if (!TARGET_REGIONS.includes(market) || !brief) return NextResponse.json({ error: "failed" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(samplePoster(market, brief));

  const out = new FormData();
  out.set("market", market);
  out.set("brief", JSON.stringify(brief));
  out.set("term_ids", termIds.join(","));
  let res: Response;
  try {
    res = await apiFetch("/campaign/poster", { method: "POST", body: out, cache: "no-store", signal: req.signal });
  } catch {
    return NextResponse.json({ error: req.signal.aborted ? "aborted" : "failed" }, { status: req.signal.aborted ? 499 : 502 });
  }
  if (!res.ok) return NextResponse.json({ error: res.status === 429 ? "busy" : "failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
