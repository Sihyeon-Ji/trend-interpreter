import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { TARGET_REGIONS } from "@/lib/reader";
import { sampleRecommend } from "@/lib/sample/recommend";
import type { CampaignTone } from "@/lib/types";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";
const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];

/** 밈 추천 (Plan 07). 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 한 번 거르고 넘긴다.
 *  사진은 메모리에서만 다루고 저장·기록하지 않는다(요청 로그에도 남기지 않는다). */
export async function POST(req: Request) {
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
  const image = form.get("image");
  const photo = image instanceof File && image.size > 0 ? image : null;
  if (photo && photo.size > MAX_IMAGE) return NextResponse.json({ error: "too_big" }, { status: 413 });
  if (photo && !["image/jpeg", "image/png", "image/webp"].includes(photo.type)) return NextResponse.json({ error: "bad_type" }, { status: 415 });
  if (!text && !photo) return NextResponse.json({ error: "need_input" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(sampleRecommend(regions, tone));

  const out = new FormData();
  out.set("text", text);
  out.set("tone", tone);
  out.set("lang", lang);
  out.set("regions", regions.join(","));
  if (photo) out.set("image", photo, "photo");   // 파일 이름은 넘기지 않는다
  let res: Response;
  try {
    res = await fetch(`${API}/recommend`, { method: "POST", body: out, cache: "no-store" });
  } catch {
    return NextResponse.json({ error: "failed" }, { status: 502 });
  }
  if (!res.ok) {
    const code = res.status === 413 ? "too_big" : res.status === 415 ? "bad_type" : res.status === 400 ? "need_input" : "failed";
    return NextResponse.json({ error: code }, { status: res.status });
  }
  return NextResponse.json(await res.json());
}
