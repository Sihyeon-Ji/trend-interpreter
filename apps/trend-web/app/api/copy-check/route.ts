import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api-fetch";
import { isSampleMode } from "@/lib/data";
import { WRITE_REGIONS } from "@/lib/reader";
import { sampleCopyCheck } from "@/lib/sample/copy-check";

const MAX_TEXT = 1000;          // 백엔드 copycheck.MAX_TEXT
const MAX_BODY = 16 * 1024;

/** 카피 검사. 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 입력을 거르고 넘긴다. 문구는 저장하지 않고 기록에도 남기지 않는다. */
export async function POST(req: Request) {
  const length = req.headers.get("content-length");
  if (length === null) return NextResponse.json({ error: "failed" }, { status: 411 });
  if (!/^\d+$/.test(length) || Number(length) > MAX_BODY) return NextResponse.json({ error: "too_long" }, { status: 413 });
  const body = (await req.json().catch(() => null)) as { text?: unknown; region?: unknown; lang?: unknown } | null;
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  const region = String(body?.region ?? "").toUpperCase();
  const lang = body?.lang === "en" ? "en" : "ko";
  if (!text) return NextResponse.json({ error: "need_text" }, { status: 400 });
  if (text.length > MAX_TEXT) return NextResponse.json({ error: "too_long" }, { status: 400 });
  if (!WRITE_REGIONS.includes(region)) return NextResponse.json({ error: "failed" }, { status: 400 });

  if (isSampleMode) return NextResponse.json(sampleCopyCheck(text, region));

  let res: Response;
  try {
    res = await apiFetch("/copy-check", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, region, lang }),
      cache: "no-store",
      signal: req.signal,
    });
  } catch {
    return NextResponse.json({ error: req.signal.aborted ? "aborted" : "failed" }, { status: req.signal.aborted ? 499 : 502 });
  }
  if (!res.ok) return NextResponse.json({ error: res.status === 429 ? "busy" : "failed" }, { status: res.status });
  return NextResponse.json(await res.json());
}
