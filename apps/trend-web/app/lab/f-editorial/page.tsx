import type { Metadata } from "next";
import Link from "next/link";
import { ChangesBand, ChangesSection } from "@/components/lab/f-editorial/changes";
import { Cover } from "@/components/lab/f-editorial/cover";
import { visibleSources } from "@/components/lab/f-editorial/entry-parts";
import { Masthead, EditionTabs } from "@/components/lab/f-editorial/masthead";
import { MemeCard, Rubric } from "@/components/lab/f-editorial/meme-card";
import { SearchBox, type SearchCard } from "@/components/lab/f-editorial/search-box";
import { riskWord, stageWord } from "@/components/lab/f-editorial/stickers";
import { WatchSection, type WatchCardInfo } from "@/components/lab/f-editorial/watchlist";
import { getGenerationCurves, getKeywordBoard, getMeta, getTermRecord, getUpdates } from "@/lib/data";
import { textFor } from "@/lib/explain";
import { fe } from "@/lib/lab/f-editorial-copy";
import { editionName, editionRegions, glossOf, issueHref, issueRange, matchCard, parseEdition, parsePage, parseQuery, rubrics, searchTrend, uniqueCards, type SearchTrend } from "@/lib/lab/f-editorial";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordCard } from "@/lib/types";

/* 이번 호 — 판(지역) 하나의 주간 밈 매거진. 표지(1위 밈) → 꼭지(검색 상승·뜨는 중·절정·꾸준·식는 중·조심) → 이번 주 달라진 것 → 내 목록 → 추천받기.
   판정은 데이터(대시보드 목록·생애주기·네이버 곡선)가 하고, 없으면 없다고 적는다. */

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  return { title: `${editionName(locale, parseEdition(sp))} — ${fe(locale, "site")}` };
}

const GROWTH_MIN = 15;   // 검색 관심이 이만큼(%) 이상 늘어야 '늘어난 밈' 에 싣는다

export default async function IssuePage({ searchParams }: Props) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const edition = parseEdition(sp);
  const page = parsePage(sp);
  const q = parseQuery(sp);
  const [board, updates, meta] = await Promise.all([getKeywordBoard(editionRegions(edition), page), getUpdates(168), getMeta()]);

  const cards = uniqueCards(board);
  const cover = board.rising[0] ?? board.fading[0] ?? null;
  // 네이버 검색 곡선은 한국어 검색어에만 있고 한국 검색 관심이다 — 한국판·전체판에서만, 한국어 표제어만 묻는다(항목마다 한 번, 300초 캐시)
  const koreanIssue = edition === "KR" || edition === "ALL";
  const curvesById = new Map<string, GenerationCurve[]>(
    await Promise.all(cards.filter((c) => koreanIssue && c.lang === "ko").map(async (c) => [c.term_id, await getGenerationCurves(c.term_id)] as const)),
  );
  const trends = new Map<string, SearchTrend | null>([...curvesById].map(([id, cs]) => [id, searchTrend(cs)]));
  const coverRecord = cover ? await getTermRecord(cover.term_id).catch(() => null) : null;
  const coverText = coverRecord ? textFor(coverRecord, locale) : null;
  const coverRefs = coverRecord ? visibleSources(coverRecord.evidences).sort((a, b) => a.observed_at.localeCompare(b.observed_at)).slice(0, 2) : [];

  const rs = rubrics(board);
  const growth = cards
    .map((c) => ({ c, t: trends.get(c.term_id) ?? null }))
    .filter((x): x is { c: KeywordCard; t: SearchTrend } => !!x.t && x.t.pct !== null && x.t.pct >= GROWTH_MIN)
    .sort((a, b) => (b.t.pct ?? 0) - (a.t.pct ?? 0))
    .slice(0, 8);
  const hits = q ? cards.filter((c) => matchCard(c, q)) : [];

  const range = issueRange(board.generated_at, locale);
  const updatedAt = meta?.last_run ?? board.generated_at;
  const searchCards: SearchCard[] = cards.map((c) => ({ id: c.term_id, name: c.canonical, lang: c.lang, ...(() => { const g = glossOf(c, locale); return { gloss: g.text, glossLang: g.lang }; })() }));
  const watchCards: WatchCardInfo[] = cards.map((c) => { const r = riskWord(c, locale); return { id: c.term_id, stage: stageWord(c, locale), risk: r && r.key !== "none" ? r.label : null, riskKey: r?.key ?? null }; });
  const pageLinks = (total: number, shown: number) => {
    if (total <= shown && page === 1) return null;
    return (
      <p className="fe-rubric__more">
        <span>{fe(locale, "r_more", { total, shown: Math.min(total, shown + (page - 1) * board.page_size) })}</span>
        {page > 1 && <Link href={issueHref(edition, { page: String(page - 1) })} className="fe-link">{fe(locale, "r_prev")}</Link>}
        {page * board.page_size < total && <Link href={issueHref(edition, { page: String(page + 1) })} className="fe-link">{fe(locale, "r_next")}</Link>}
      </p>
    );
  };
  const wide = edition === "ALL" || edition === "GLOBAL";

  return (
    <>
      <Masthead locale={locale} edition={edition} />
      <EditionTabs locale={locale} edition={edition} counts={board.counts} />
      <main id="fe-main">
        <div className="fe-wrap fe-issue">
          <div>
            <h1 className="fe-issue__title">{editionName(locale, edition)}{range && <span className="fe-muted"> — {fe(locale, "issue_for", { range })}</span>}</h1>
            {updatedAt && <p className="fe-issue__meta">{fe(locale, "updated", { time: fmtDateTime(updatedAt, locale) })}</p>}
          </div>
          <SearchBox locale={locale} edition={edition} cards={searchCards} initialQ={q} />
        </div>

        {q && (
          <div className="fe-wrap" style={{ marginTop: 8 }}>
            <Rubric id="fe-hits" title={fe(locale, "search_results", { q })} count={hits.length}
              empty={hits.length === 0 ? `${fe(locale, "search_none")} ` : undefined} four={hits.length > 3}>
              {hits.map((c) => <MemeCard key={c.term_id} card={c} locale={locale} edition={edition} trend={trends.get(c.term_id)} showRegions={wide} />)}
            </Rubric>
            {hits.length === 0 && <p style={{ marginTop: 12 }}><a className="fe-link" href={`/dictionary?q=${encodeURIComponent(q)}`}>{fe(locale, "search_whole")}</a></p>}
          </div>
        )}

        {cover && (
          <Cover card={cover} text={coverText} refs={coverRefs} curves={curvesById.get(cover.term_id) ?? []} locale={locale} edition={edition}
            canMake={coverRecord?.term.status === "verified" && cover.risk_level !== "avoid"} />
        )}
        <ChangesBand items={updates} locale={locale} edition={edition} />

        <div className="fe-wrap">
          {growth.length > 0 && (
            <Rubric id="fe-growth" title={fe(locale, "r_growth")} note={fe(locale, "r_growth_note")} count={growth.length} four={growth.length > 3}>
              {growth.map(({ c, t }) => <MemeCard key={c.term_id} card={c} locale={locale} edition={edition} trend={t} showRegions={wide} />)}
            </Rubric>
          )}
          {rs.map((r) => {
            if (!r.cards.length && !r.alwaysShow) return null;
            const empty = r.cards.length ? undefined : fe(locale, `r_${r.key}_empty`);
            return (
              <Rubric key={r.key} id={`fe-${r.key}`} title={fe(locale, `r_${r.key}`)} note={fe(locale, `r_${r.key}_note`)} count={r.cards.length} empty={empty}
                four={r.cards.length > 3} more={pageLinks(r.total, r.cards.length)}>
                {r.cards.map((c) => (
                  <MemeCard key={c.term_id} card={c} locale={locale} edition={edition} trend={trends.get(c.term_id)} showReason={r.key === "caution"} showRegions={wide} />
                ))}
              </Rubric>
            );
          })}

          <ChangesSection items={updates} locale={locale} edition={edition} known={watchCards} />
          <WatchSection locale={locale} edition={edition} cards={watchCards} />

          <section className="fe-cta" aria-labelledby="fe-cta-title">
            <div className="fe-cta__row">
              <div>
                <h2 id="fe-cta-title">{fe(locale, "recommend_title")}</h2>
                <p>{fe(locale, "recommend_note")}</p>
              </div>
              <Link href={`/recommend?regions=${encodeURIComponent(edition === "ALL" || edition === "GLOBAL" ? "KR" : edition)}`} className="fe-btn fe-btn--primary">{fe(locale, "recommend")}</Link>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
