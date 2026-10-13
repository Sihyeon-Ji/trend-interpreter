import type { Metadata } from "next";
import { verdictOf } from "@/components/stage/bits";
import { isMarket, marketName, tx, type Market } from "@/components/stage/copy";
import { ExploreStage, type XList, type XRow } from "@/components/stage/explore-stage";
import { isPartialWeek } from "@/components/trend-chart";
import { getKeywordBoard, getTermRelated } from "@/lib/data";
import { glossFor } from "@/lib/gloss";
import { t, type Locale } from "@/lib/i18n";
import { L, regionLabel, sourceLabel, sourceName } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { KeywordBoard, KeywordCard } from "@/lib/types";

export async function generateMetadata({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }): Promise<Metadata> {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const m = [sp.m ?? sp.regions].flat()[0]?.toUpperCase();
  return { title: `${tx(locale, "nav_explore")}${isMarket(m) ? ` · ${marketName(locale, m)}` : ""} — ${t(locale, "site")}` };
}

const LISTS: XList[] = ["rising", "fading", "caution"];
const NOUN: Record<Locale, Record<string, string>> = {
  ko: { wiki: "문서", web: "문서", news: "기사", short: "영상" }, en: { wiki: "page", web: "page", news: "article", short: "video" },
  ja: { wiki: "記事", web: "ページ", news: "記事", short: "動画" },
};

/** 목록 한 줄 — 판정·생애주기는 백엔드 규칙 값 그대로, 여기서는 글로 옮기기만. 커뮤니티 글은 근거로 싣지 않는다 */
function toRow(c: KeywordCard, locale: Locale): XRow {
  const labels = L(locale);
  const refs = c.evidences
    .filter((e) => e.kind !== "community" && e.kind !== "datalab")
    .sort((a, b) => Number(b.kind === "wiki" || b.kind === "web") - Number(a.kind === "wiki" || a.kind === "web") || String(b.observed_at).localeCompare(String(a.observed_at)))
    .slice(0, 3)
    .map((e) => ({ url: e.url, label: sourceLabel(locale, sourceName(locale, e.source_domain), NOUN[locale][e.kind] ?? ""), title: e.title, date: e.observed_at }));
  return {
    id: c.term_id, word: c.canonical, lang: c.lang, readings: c.readings, gloss: glossFor(c, locale), verdict: verdictOf(c),
    life: labels.lifecycle[c.lifecycle], diffusion: c.diffusion ?? null, m4: c.mentions_4w, weekly: c.weekly.slice(-12),
    regions: c.regions.map((r) => regionLabel(locale, r)), tone: c.tone, refs, partial: isPartialWeek(c.weekly.at(-1)),
  };
}

/* 둘러보기 (Plan 20, 시안 r-stage) — 시장 하나의 무대. 왼쪽은 그 시장의 말 목록(순위), 말을 고르면 오른쪽 무대 위로 올라와 크게 선다.
   목록 셋은 대시보드 규칙(Plan 04) 그대로: 지금 쓰는 말·식는 말·조심할 말. 시장·목록·쪽은 주소에, 고른 말은 ?w= 에.
   예전 주소(?regions=·list=·page=, 지도·나라·브리핑 화면의 링크)도 받는다. 세 시장 밖의 나라는 한국으로 연다 */
export default async function ExplorePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const asked = [sp.m ?? sp.regions].flat()[0]?.split(",")[0]?.toUpperCase();
  const market: Market = isMarket(asked) ? asked : "KR";
  const listAsked = [sp.l ?? sp.list].flat()[0];
  const list: XList = LISTS.find((l) => l === listAsked) ?? "rising";
  const page = Math.max(1, Number.parseInt([sp.p ?? sp.page].flat()[0] ?? "", 10) || 1);
  const want = [sp.w].flat()[0] ?? null;
  let board: KeywordBoard | null = null;
  try {
    board = await getKeywordBoard([market], page);
  } catch {
    board = null;
  }
  // 이어진 밈(지식 그래프)은 목록 한 쪽(30개)만큼 함께 받는다 — 백엔드 응답이 수 ms 라 고를 때마다 따로 부르지 않는다
  const cards = board ? board[list] : [];
  const graphs = await Promise.all(cards.map((c) => getTermRelated(c.term_id)));
  const rows = cards.map((c, i) => ({ ...toRow(c, locale), related: graphs[i] }));
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <ExploreStage
        locale={locale} market={market} list={list} page={page} pageSize={board?.page_size ?? 30}
        totals={board?.totals ?? null} count={board?.counts[market] ?? 0} updatedAt={board ? board.collected_at ?? board.generated_at : null}
        rows={rows} initial={want && rows.some((r) => r.id === want) ? want : rows[0]?.id ?? null} failed={!board}
      />
    </main>
  );
}
