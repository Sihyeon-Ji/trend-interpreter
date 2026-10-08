import type { Metadata } from "next";
import { verdictOf } from "@/components/stage/bits";
import { MARKETS, isMarket, tx, type Market } from "@/components/stage/copy";
import { StartStage } from "@/components/stage/start-stage";
import type { MarketLive, Pin } from "@/components/stage/store";
import { getKeywordBoard, getTermRecord } from "@/lib/data";
import { glossFor } from "@/lib/gloss";
import { t, type Locale } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import type { KeywordCard } from "@/lib/types";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${tx(locale, "nav_make")} — ${t(locale, "site")}` };
}

const LIFE_RANK: Record<string, number> = { emerging: 0, rising: 0, peak: 0, steady: 1 };

/** 무대의 '살아 있는 말' — 그 시장의 쓰이는 중 목록에서 규칙이 리스크를 검사한 말(문제 없음·조심)만, 4주 언급 순 6개.
 *  쓰지 않을 말·아직 판단 못 한 말은 무대에 세우지 않는다. 판정·목록은 백엔드 규칙 그대로이고 여기서는 고르고 줄 세우기만 */
function liveWords(cards: KeywordCard[], locale: Locale) {
  return cards
    .filter((c) => c.risk_level === "none" || c.risk_level === "caution")
    .sort((a, b) => b.mentions_4w - a.mentions_4w || (LIFE_RANK[a.lifecycle] ?? 2) - (LIFE_RANK[b.lifecycle] ?? 2))
    .slice(0, 6)
    .map((c) => ({ id: c.term_id, word: c.canonical, lang: c.lang, gloss: glossFor(c, locale), verdict: verdictOf(c) }));
}

async function loadLive(market: Market, locale: Locale): Promise<MarketLive> {
  try {
    const board = await getKeywordBoard([market], 1);
    return { market, count: board.counts[market] ?? 0, words: liveWords(board.rising, locale), at: board.collected_at ?? board.generated_at };
  } catch {
    return { market, count: 0, words: [], failed: true };
  }
}

/* 첫 화면 — 만들기 (Plan 20, 시안 r-stage). 무대 하나: 세 시장이 제 글자로 된 '지금 쓰이는 말' 을 들고 서 있고, 아래 책상에서 제품을 넣는다.
   둘러보기·사전 항목의 '이 말로 초안 만들기' 는 ?m=시장&term=밈 으로 넘어온다(예전 주소의 ?regions= 도 받는다) */
export default async function StartPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const asked = [sp.m ?? sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase()).filter(isMarket);
  const termId = [sp.term].flat()[0];
  const [live, record] = await Promise.all([
    Promise.all(MARKETS.map((m) => loadLive(m, locale))),
    termId && /^[\w.:-]{1,64}$/.test(termId) ? getTermRecord(termId).catch(() => null) : Promise.resolve(null),
  ]);
  // 사전에서 확인된 말이고 쓰지 않을 말이 아닐 때만 넣는다(추천 API 도 같은 것을 다시 본다)
  const pin: Pin | null = record && record.term.status === "verified" && record.term.risk_level !== "avoid"
    ? { id: record.term.term_id, word: record.term.canonical, lang: record.term.lang ?? "ko" } : null;
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <StartStage locale={locale} live={live} seedMarkets={asked.length ? asked : null} pin={pin} />
    </main>
  );
}
