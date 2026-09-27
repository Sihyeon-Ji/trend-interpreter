import { NextResponse } from "next/server";
import { explain } from "@/lib/data";
import type { Locale } from "@/lib/i18n";
import { getReader } from "@/lib/reader-server";

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { text?: string; locale?: Locale } | null;
  const text = body?.text?.trim() ?? "";
  if (!text) return NextResponse.json({ items: [], plain: null });
  const locale: Locale = body?.locale === "en" ? "en" : "ko";
  return NextResponse.json(await explain(text, locale, await getReader()));
}
