import type { Metadata } from "next";
import Link from "next/link";
import { ChangesBand, ChangesSection } from "@/components/lab/f-editorial/changes";
import { Cover, EmptyCover } from "@/components/lab/f-editorial/cover";
import { Masthead, EditionTabs } from "@/components/lab/f-editorial/masthead";
import { IndexRow, LedgerRow, MemeCard, PosterGrid, Rubric } from "@/components/lab/f-editorial/meme-card";
import { SearchBox, type SearchCard } from "@/components/lab/f-editorial/search-box";
import { riskKeyOf } from "@/components/lab/f-editorial/stickers";
import { WatchSection, type WatchCardInfo } from "@/components/lab/f-editorial/watchlist";
import { getGenerationCurves, getKeywordBoard, getMeta, getTermRecord, getUpdateFeed } from "@/lib/data";
import { textFor } from "@/lib/explain";
import { fe } from "@/lib/lab/f-editorial/copy";
import {
  changeRows, editionName, editionRegions, glossOf, issueHref, issueRange, matchCard, originRefs, parseEdition, parsePage, parseQuery, pickCover,
  recommendHref, rubrics, searchTrend, searchedMore, sourceItems, uniqueCards, type Rubric as RubricData, type SearchTrend,
} from "@/lib/lab/f-editorial";
import { fmtDateTime } from "@/lib/labels";
import { getLabLocale as getLocale } from "@/lib/locale";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordCard } from "@/lib/types";

/* 이번 호 — 판(지역) 하나의 주간 밈 매거진. 표지 → 지난 방문 이후 달라진 것 → 내 목록 → 꼭지(검색 상승·뜨는 중·절정·꾸준·식는 중·조심) → 추천받기.
   판정은 데이터(대시보드 목록·생애주기·네이버 곡선)가 하고, 없으면 없다고 적는다. 긴 목록은 포스터가 아니라 색인 줄로 훑고 8개 뒤는 접는다. */

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  return { title: `${editionName(locale, parseEdition(sp))}, ${fe(locale, "site")}` };
}

const SHOW = 8;   // 색인 줄은 여덟 개까지 펼치고 나머지는 접는다

export default async function IssuePage({ searchParams }: Props) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const edition = parseEdition(sp);
  const page = parsePage(sp);
  const q = parseQuery(sp);
  const [board, feed, meta] = await Promise.all([getKeywordBoard(editionRegions(edition), page), getUpdateFeed(168), getMeta()]);

  const cards = uniqueCards(board);
  // 네이버 검색 곡선은 한국어 검색어에만 있고 한국 검색 관심이다 — 한국판·전체판에서만, 한국어 표제어만 묻는다(항목마다 한 번, 300초 캐시)
  const koreanIssue = edition === "KR" || edition === "ALL";
  const curvesById = new Map<string, GenerationCurve[]>(
    await Promise.all(cards.filter((c) => koreanIssue && c.lang === "ko").map(async (c) => [c.term_id, await getGenerationCurves(c.term_id)] as const)),
  );
  const trends = new Map<string, SearchTrend | null>([...curvesById].map(([id, cs]) => [id, searchTrend(cs, board.generated_at)]));
  const picked = pickCover(board, trends);
  const coverRecord = picked ? await getTermRecord(picked.card.term_id).catch(() => null) : null;
  const coverText = coverRecord ? textFor(coverRecord, locale) : null;
  const coverRefs = coverRecord ? originRefs(sourceItems(coverRecord.evidences, [coverRecord.term.canonical, ...(coverRecord.term.aliases ?? [])], locale)) : [];

  const growth = cards
    .filter((c) => searchedMore(trends.get(c.term_id)))
    .sort((a, b) => (trends.get(b.term_id)!.pct ?? 0) - (trends.get(a.term_id)!.pct ?? 0))
    .slice(0, SHOW);
  const rs = rubrics(board, new Set(growth.map((c) => c.term_id)));
  const hits = q ? cards.filter((c) => matchCard(c, q)) : [];
  const changes = changeRows(feed?.items ?? [], edition, locale);

  const range = issueRange(board.generated_at, locale);
  const updatedAt = meta?.last_run ?? board.generated_at;
  const wide = edition === "ALL" || edition === "GLOBAL";
  const searchCards: SearchCard[] = cards.map((c) => { const g = glossOf(c, locale); return { id: c.term_id, name: c.canonical, lang: c.lang, gloss: g.text, glossLang: g.lang }; });
  const watchCards: WatchCardInfo[] = cards.map((c) => ({ id: c.term_id, lifecycle: c.lifecycle, risk: riskKeyOf(c) }));
  const trendOf = (c: KeywordCard) => trends.get(c.term_id);

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

  /* 꼭지마다 모양이 다르다: 뜨는 중·절정은 포스터(셋 미만이면 넓은 줄), 꾸준·미확인·식는 중은 색인 줄, 조심은 점검표. 비면 한 줄. */
  const renderRubric = (r: RubricData) => {
    if (!r.cards.length && !r.alwaysShow) return null;
    const id = `fe-${r.key}`;
    const title = fe(locale, `r_${r.key}`);
    if (!r.cards.length) return <Rubric key={r.key} id={id} title={title} empty={fe(locale, `r_${r.key}_empty`)} />;
    const poster = r.key === "hot" || r.key === "peak";
    const hideStage = r.key !== "fading";   // 꼭지 제목이 이미 단계를 말한다. 식는 중만 여러 단계가 섞인다
    const rows = (cs: KeywordCard[]) => (
      <ul className={r.key === "caution" ? "fe-ledger" : "fe-rows"}>
        {cs.map((c) => r.key === "caution"
          ? <LedgerRow key={c.term_id} card={c} locale={locale} edition={edition} />
          : <IndexRow key={c.term_id} card={c} locale={locale} edition={edition} trend={trendOf(c)} hideStage={hideStage} showRegions={wide} />)}
      </ul>
    );
    let body: React.ReactNode;
    if (poster && r.cards.length >= 3) {
      body = <PosterGrid count={r.cards.length}>{r.cards.map((c) => <MemeCard key={c.term_id} card={c} locale={locale} edition={edition} trend={trendOf(c)} hideStage showRegions={wide} />)}</PosterGrid>;
    } else if (poster) {
      body = <ul className="fe-rows">{r.cards.map((c) => <IndexRow key={c.term_id} card={c} locale={locale} edition={edition} trend={trendOf(c)} hideStage showRegions={wide} large />)}</ul>;
    } else {
      const head = r.cards.slice(0, SHOW), rest = r.cards.slice(SHOW);
      body = (
        <>
          {rows(head)}
          {rest.length > 0 && <details className="fe-rest"><summary>{fe(locale, "r_rest", { n: rest.length })}</summary>{rows(rest)}</details>}
        </>
      );
    }
    return (
      <Rubric key={r.key} id={id} title={title} note={fe(locale, `r_${r.key}_note`)} count={r.cards.length} more={pageLinks(r.total, r.cards.length)}>
        {body}
      </Rubric>
    );
  };

  return (
    <>
      <Masthead locale={locale} edition={edition} />
      <EditionTabs locale={locale} edition={edition} counts={board.counts} />
      <main id="fe-main">
        <div className="fe-wrap fe-issue">
          <div>
            <h1 className="fe-issue__title">{editionName(locale, edition)}</h1>
            {range && <p className="fe-issue__range">{fe(locale, "issue_for", { range })}</p>}
            {updatedAt && <p className="fe-issue__meta">{fe(locale, "updated", { time: fmtDateTime(updatedAt, locale) })}</p>}
          </div>
          <SearchBox locale={locale} edition={edition} cards={searchCards} initialQ={q} />
        </div>

        {q && (
          <div className="fe-wrap" style={{ marginTop: 8 }}>
            <Rubric id="fe-hits" title={fe(locale, "search_results", { q })} count={hits.length} empty={hits.length === 0 ? fe(locale, "search_none") : undefined}>
              <ul className="fe-rows">{hits.map((c) => <IndexRow key={c.term_id} card={c} locale={locale} edition={edition} trend={trendOf(c)} showRegions={wide} large />)}</ul>
            </Rubric>
            {hits.length === 0 && <p style={{ marginTop: 12 }}><a className="fe-link" href={`/dictionary?q=${encodeURIComponent(q)}`}>{fe(locale, "search_whole")}</a></p>}
          </div>
        )}

        {picked ? (
          <Cover card={picked.card} rule={picked.rule} text={coverText} refs={coverRefs} curves={curvesById.get(picked.card.term_id) ?? []} locale={locale} edition={edition}
            canMake={coverRecord?.term.status === "verified" && picked.card.risk_level !== "avoid"} />
        ) : <EmptyCover locale={locale} edition={edition} />}
        <ChangesBand rows={changes} locale={locale} />

        <div className="fe-wrap">
          <ChangesSection rows={changes} locale={locale} edition={edition} />
          <WatchSection locale={locale} edition={edition} cards={watchCards} />

          {growth.length > 0 && (
            <Rubric id="fe-growth" title={fe(locale, "r_growth")} note={fe(locale, "r_growth_note")} count={growth.length}>
              <PosterGrid count={growth.length}>
                {growth.map((c, i) => <MemeCard key={c.term_id} card={c} locale={locale} edition={edition} trend={trendOf(c)} rank={i + 1} showRegions={wide} />)}
              </PosterGrid>
            </Rubric>
          )}
          {cards.length > 0 && rs.map(renderRubric)}

          <section className="fe-cta" aria-labelledby="fe-cta-title">
            <div className="fe-cta__row">
              <div>
                <h2 id="fe-cta-title">{fe(locale, "recommend_title")}</h2>
                <p>{fe(locale, "recommend_note")}</p>
              </div>
              <Link href={recommendHref(edition)} className="fe-btn fe-btn--primary">{fe(locale, "recommend")}</Link>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
