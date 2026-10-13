import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api-fetch";
import { isSampleMode } from "@/lib/data";
import { WRITE_REGIONS } from "@/lib/reader";
import { sampleCopyCheck } from "@/lib/sample/copy-check";
import { localeOf } from "@/lib/i18n";

const MAX_TEXT = 2000;          // 본문(백엔드 copycheck.MAX_TEXT 1000자)과 해시태그 — 백엔드 /copy-check/all 과 같다
const MAX_TEXTS = 6;            // 만들기는 시장마다 문구 넷
const MAX_BODY = 48 * 1024;

/** 초안 한 시장의 문구 모두를 규칙으로 다시 본다(Plan 20 ④). AI 의견은 opinion 번째 문구 하나에만 — 시장마다 한 번.
 *  브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 거르고 넘긴다. 문구는 저장하지 않고 기록에도 남기지 않는다. */
export async function POST(req: Request) {
  const length = req.headers.get("content-length");
  if (length === null) return NextResponse.json({ error: "failed" }, { status: 411 });
  if (!/^\d+$/.test(length) || Number(length) > MAX_BODY) return NextResponse.json({ error: "too_long" }, { status: 413 });
  const body = (await req.json().catch(() => null)) as { texts?: unknown; region?: unknown; lang?: unknown; opinion?: unknown } | null;
  const raw = Array.isArray(body?.texts) ? body.texts : [];
  const texts = raw.map((t) => (typeof t === "string" ? t.trim() : ""));
  const region = String(body?.region ?? "").toUpperCase();
  const lang = localeOf(body?.lang);   // 화면 언어 그대로(ko·en·ja) — 일본어 화면이 한국어 AI 의견을 받던 것(10-13)
  if (!texts.length || texts.length > MAX_TEXTS || texts.some((t) => !t || t.length > MAX_TEXT)) return NextResponse.json({ error: "need_text" }, { status: 400 });
  if (!WRITE_REGIONS.includes(region)) return NextResponse.json({ error: "failed" }, { status: 400 });
  const opinion = typeof body?.opinion === "number" && Number.isInteger(body.opinion) && body.opinion >= 0 && body.opinion < texts.length ? body.opinion : null;

  if (isSampleMode) return NextResponse.json({ region, items: texts.map((t) => sampleCopyCheck(t, region)), opinion: null });

  let res: Response;
  try {
    res = await apiFetch("/copy-check/all", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ texts, region, lang, opinion }),
      cache: "no-store",
      signal: req.signal,
    });
  } catch {
    return NextResponse.json({ error: req.signal.aborted ? "aborted" : "failed" }, { status: req.signal.aborted ? 499 : 502 });
  }
  if (!res.ok) return NextResponse.json({ error: res.status === 429 ? "busy" : "failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
