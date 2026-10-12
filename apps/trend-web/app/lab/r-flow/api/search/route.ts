import { NextResponse, type NextRequest } from "next/server";
import { loadTermRecords } from "@/lib/data";
import { textFor } from "@/lib/explain";
import type { LabLocale as Locale } from "@/lib/i18n";

/* 명령 팔레트의 밈 찾기(읽기 전용). 브라우저는 백엔드에 직접 가지 않는다 — 서버가 사전(확인된 말)을 받아
   이름·다른 표기·뜻 한 줄만 추려 맞는 것 8개를 돌려준다. 추린 색인은 이 서버 메모리에 10분 둔다. */

interface Entry { id: string; name: string; lang: string; keys: string[]; gloss: Record<Locale, string>; risk: string | null; life: string | null }
let index: { at: number; entries: Entry[] } | null = null;
let building: Promise<Entry[] | null> | null = null;
const TTL = 10 * 60_000;

const norm = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[\s·・\-_'"“”‘’.,!?！？]+/g, "");

async function entries(): Promise<Entry[] | null> {
  if (index && Date.now() - index.at < TTL) return index.entries;
  building ??= (async () => {
    const { records, ok } = await loadTermRecords(true);
    if (!ok) return null;
    const out = records
      .filter((r) => r.term.status === "verified")
      .map((r) => ({
        id: r.term.term_id,
        name: r.term.canonical,
        lang: r.term.lang ?? "",
        keys: [r.term.canonical, ...(r.term.aliases ?? [])].map(norm).filter(Boolean),
        gloss: { ko: (textFor(r, "ko")?.definition ?? "").slice(0, 90), en: r.en ? r.en.definition.slice(0, 90) : "" },
        risk: r.term.risk_level ?? (r.term.risk_checked_at ? "unknown" : null),
        life: r.term.lifecycle ?? null,
      }));
    index = { at: Date.now(), entries: out };
    return out;
  })().finally(() => { building = null; });
  return building;
}

function rank(e: Entry, q: string): number {
  let best = 99;
  e.keys.forEach((k, i) => {
    const alias = i > 0 ? 1 : 0;
    if (k === q) best = Math.min(best, 0 + alias);
    else if (k.startsWith(q)) best = Math.min(best, 2 + alias);
    else if (k.includes(q)) best = Math.min(best, 4 + alias);
  });
  return best;
}

export async function GET(req: NextRequest) {
  const locale: Locale = req.nextUrl.searchParams.get("locale") === "en" ? "en" : "ko";
  const q = norm(req.nextUrl.searchParams.get("q") ?? "").slice(0, 40);
  const all = await entries();
  if (!all) return NextResponse.json({ error: "unavailable" }, { status: 503 });
  if (!q) return NextResponse.json({ items: [] });
  const hits: { e: Entry; r: number }[] = [];
  for (const e of all) {
    let r = rank(e, q);
    if (r === 99 && q.length >= 2 && norm(e.gloss[locale] || e.gloss.ko).includes(q)) r = 8;
    if (r < 99) hits.push({ e, r });
  }
  hits.sort((a, b) => a.r - b.r || a.e.name.length - b.e.name.length || a.e.name.localeCompare(b.e.name));
  const items = hits.slice(0, 8).map(({ e }) => ({
    id: e.id, name: e.name, lang: e.lang, gloss: e.gloss[locale] || "", pending: locale === "en" && !e.gloss.en, risk: e.risk, life: e.life,
  }));
  return NextResponse.json({ items, total: hits.length });
}
