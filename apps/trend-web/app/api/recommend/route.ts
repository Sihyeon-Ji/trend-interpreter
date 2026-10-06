import { apiFetch } from "@/lib/api-fetch";
import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { TARGET_REGIONS } from "@/lib/reader";
import { sampleRecommend } from "@/lib/sample/recommend";
import { L } from "@/lib/labels";
import type { CampaignTone, FitCategory } from "@/lib/types";

const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
const CATEGORIES = Object.keys(L("ko").fitCategory) as FitCategory[];

/** 밈 추천 (Plan 07). 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 한 번 거르고 넘긴다.
 *  사진은 메모리에서만 다루고 저장·기록하지 않는다(요청 로그에도 남기지 않는다). */
export async function POST(req: Request) {
  // 본문을 읽기 전에 크기부터 — 길이를 밝히지 않거나 한도를 넘으면 받지 않는다(검토 2차)
  const length = Number(req.headers.get("content-length") ?? NaN);
  if (!Number.isFinite(length)) return NextResponse.json({ error: "bad_request" }, { status: 411 });
  if (length > MAX_IMAGE + 64 * 1024) return NextResponse.json({ error: "too_big" }, { status: 413 });
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  const text = String(form.get("text") ?? "").trim().slice(0, 500);
  const tone = (TONES.includes(form.get("tone") as CampaignTone) ? form.get("tone") : "friendly") as CampaignTone;
  const regions = String(form.get("regions") ?? "").split(",").map((r) => r.trim().toUpperCase()).filter((r) => TARGET_REGIONS.includes(r));
  const lang = form.get("lang") === "en" ? "en" : "ko";
  // 사전 항목의 '이 밈으로 만들기' 에서 먼저 고른 밈 id — 모양만 보고 넘긴다(있는지는 백엔드가 본다)
  const term = String(form.get("term") ?? "").trim();
  const pin = /^[\w.:-]{1,64}$/.test(term) ? term : "";
  // 만들기(Plan 20)에서 마케터가 고른 분야 — 모델이 읽은 분야보다 앞선다. 비면 제품에서 읽은 대로
  const category = CATEGORIES.find((c) => c === form.get("category")) ?? "";
  const image = form.get("image");
  const photo = image instanceof File && image.size > 0 ? image : null;
  if (photo && photo.size > MAX_IMAGE) return NextResponse.json({ error: "too_big" }, { status: 413 });
  if (photo && !["image/jpeg", "image/png", "image/webp"].includes(photo.type)) return NextResponse.json({ error: "bad_type" }, { status: 415 });
  if (!text && !photo) return NextResponse.json({ error: "need_input" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(sampleRecommend(regions, tone, pin || null, category || null));

  const out = new FormData();
  out.set("text", text);
  out.set("tone", tone);
  out.set("lang", lang);
  out.set("regions", regions.join(","));
  if (pin) out.set("term", pin);
  if (category) out.set("category", category);
  if (photo) out.set("image", photo, "photo");   // 파일 이름은 넘기지 않는다
  let res: Response;
  try {
    res = await apiFetch(`/recommend`, { method: "POST", body: out, cache: "no-store", signal: req.signal });
  } catch {
    return NextResponse.json({ error: "failed" }, { status: 502 });
  }
  if (!res.ok) {
    // 429(분당 한도)는 따로 알린다 — '잠시 뒤' 대신 '요청이 많다' 고 말한다
    const code = res.status === 413 ? "too_big" : res.status === 415 ? "bad_type" : res.status === 400 ? "need_input" : res.status === 429 ? "busy" : "failed";
    return NextResponse.json({ error: code }, { status: res.status });
  }
  return NextResponse.json(await res.json());
}
