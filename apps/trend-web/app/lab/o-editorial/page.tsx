import type { Metadata } from "next";
import Link from "next/link";
import { Cover, EmptyCover } from "@/components/lab/o-editorial/cover";
import { EditionBar } from "@/components/lab/o-editorial/frame";
import { MyScraps, SinceLastVisit } from "@/components/lab/o-editorial/return-band";
import { IndexItem, LedgerItem, Poster, RankRow, Rubric, RubricHead, type SinceMark } from "@/components/lab/o-editorial/rubrics";
import { getLocale } from "@/lib/locale";
import { BASE, copy, editionHref, editionName, parseEdition, searchedMore, type EditionKey } from "@/lib/lab/o-editorial";
import { getIssue } from "@/lib/lab/o-editorial-data";
import type { Locale } from "@/lib/i18n";

/* 이번 주 호 — 판(지역)을 고르면 그 시장의 커버 밈, 지난번 방문 이후 달라진 것, 꼭지 넷(지금 쓰이는·요즘 더 찾는·식어 가는·브랜드는 조심).
   목록 나누기와 단계·리스크는 백엔드 규칙(pipeline/dashboard.py) 그대로다. 이 화면이 새로 세는 것은 네이버 곡선의 4주 변화뿐이다. */

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };
const first = (v: string | string[] | undefined) => [v].flat()[0];

const RISING_ON_HOME = 10;     // 특집 2 + 넷씩 두 줄
const FADING_ON_HOME = 12;
const CAUTION_ON_HOME = 8;
const SEARCHED_ON_HOME = 8;

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const c = copy(locale);
  return { title: `${c.thisWeek(editionName(locale, parseEdition(first(sp.regions))))} | ${c.site}` };
}

function Contents({ locale, parts }: { locale: Locale; parts: { id: string; n: number }[] }) {
  const c = copy(locale);
  if (!parts.length) return null;
  const items = parts.map((p) => <a key={p.id} href={`#${p.id}`}>{c.contentsPart[p.id](p.n)}</a>);
  const joined = items.flatMap((el, i) => (i === 0 ? [el] : [i === items.length - 1 ? (locale === "ko" ? ", " : " and ") : ", ", el]));
  return (
    <div className="oe-wrap oe-contents">
      <p>{c.contentsLead} {joined}{c.contentsTail}</p>
    </div>
  );
}

function FailState({ locale, edition }: { locale: Locale; edition: EditionKey }) {
  const c = copy(locale);
  return (
    <div className="oe-wrap" style={{ paddingBlock: 48 }}>
      <div className="oe-state" role="alert">
        <p>{c.loadFailed}</p>
        <p style={{ marginTop: 16 }}><Link href={editionHref(edition)} className="oe-btn oe-btn-line">{c.retry}</Link></p>
      </div>
    </div>
  );
}

export default async function EditorialHome({ searchParams }: Props) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const c = copy(locale);
  const edition = parseEdition(first(sp.regions));
  const issue = await getIssue(edition);

  if (!issue) {
    return (
      <>
        <EditionBar locale={locale} edition={edition} counts={null} generatedAt={null} />
        <FailState locale={locale} edition={edition} />
      </>
    );
  }

  const { board, cover } = issue;
  const at = board.generated_at;
  const rising = board.rising.filter((x) => x.term_id !== cover?.term_id);
  const searched = issue.searched
    .map((card) => ({ card, s: issue.searches[card.term_id] }))
    .filter((x) => searchedMore(x.s))
    .sort((a, b) => (b.s.median ?? 0) - (a.s.median ?? 0))
    .slice(0, SEARCHED_ON_HOME);
  const fading = board.fading.filter((x) => x.term_id !== cover?.term_id);
  const marks: Record<string, SinceMark> = {};
  for (const i of issue.since) {
    if (i.termId && i.kind !== "spike" && !marks[i.termId]) marks[i.termId] = { at: i.at, kind: i.kind };
  }
  const list = (name: string) => `${BASE}/list/${name}?regions=${edition === "ALL" ? "all" : edition}`;

  const coverInRising = !!cover && !issue.coverFallback;
  const parts = [
    { id: "rising", n: rising.length ? board.totals.rising ?? 0 : 0 },
    { id: "searched", n: searched.length },
    { id: "fading", n: fading.length ? board.totals.fading ?? 0 : 0 },
    { id: "caution", n: board.caution.length ? board.totals.caution ?? 0 : 0 },
  ].filter((p) => p.n > 0);
  const risingShown = Math.min(RISING_ON_HOME, rising.length) + (coverInRising ? 1 : 0);
  const risingCount = risingShown < board.totals.rising
    ? c.countLine(risingShown, board.totals.rising)
    : coverInRising ? c.withCover(board.totals.rising) : c.countLine(rising.length, rising.length);

  return (
    <>
      <EditionBar locale={locale} edition={edition} counts={board.counts} generatedAt={at} />

      {cover
        ? <Cover locale={locale} edition={edition} card={cover} record={issue.coverRecord} search={issue.searches[cover.term_id] ?? null} fallback={issue.coverFallback} generatedAt={at} />
        : <EmptyCover locale={locale} edition={edition} counts={board.counts} avoidOnly={board.totals.caution ? board.caution.filter((x) => x.risk_level === "avoid").length : 0} spikes={issue.since.filter((i) => i.kind === "spike").length} />}

      <div className="oe-wrap oe-return">
        <SinceLastVisit locale={locale} edition={edition} items={issue.since} />
        <MyScraps locale={locale} edition={edition} />
      </div>

      <Contents locale={locale} parts={parts} />

      {rising.length > 0 && (
        <Rubric id="rising">
          <RubricHead id="rising-title" title={c.rubricRising} count={risingCount} note={c.rubricRisingNote} />
          <div className="oe-posters">
            {rising.slice(0, RISING_ON_HOME).map((card, i) => (
              <Poster key={card.term_id} locale={locale} edition={edition} card={card} feature={i < 2 && rising.length > 3} since={marks[card.term_id]} generatedAt={at} />
            ))}
          </div>
          {rising.length > RISING_ON_HOME && <Link href={list("rising")} className="oe-link oe-rubric-more">{c.seeAll(board.totals.rising)}</Link>}
        </Rubric>
      )}

      {searched.length > 0 && (
        <Rubric id="searched">
          <RubricHead id="searched-title" title={c.rubricSearch} count={c.countLine(searched.length, searched.length)} note={c.rubricSearchNote} />
          <ol className="oe-ranks">
            {searched.map(({ card, s }, i) => (
              <RankRow key={card.term_id} locale={locale} edition={edition} card={card} search={s} rank={i + 1} generatedAt={at} />
            ))}
          </ol>
        </Rubric>
      )}

      {fading.length > 0 && (
        <Rubric id="fading">
          <RubricHead id="fading-title" title={c.rubricFading} count={c.countLine(Math.min(FADING_ON_HOME, fading.length), board.totals.fading)} note={c.rubricFadingNote} />
          <ul className="oe-index">
            {fading.slice(0, FADING_ON_HOME).map((card) => <IndexItem key={card.term_id} locale={locale} edition={edition} card={card} generatedAt={at} />)}
          </ul>
          {board.totals.fading > FADING_ON_HOME && <Link href={list("fading")} className="oe-link oe-rubric-more">{c.seeAll(board.totals.fading)}</Link>}
        </Rubric>
      )}

      {board.caution.length > 0 && (
        <Rubric id="caution">
          <RubricHead id="caution-title" title={c.rubricCaution} count={c.countLine(Math.min(CAUTION_ON_HOME, board.caution.length), board.totals.caution)} note={c.rubricCautionNote} />
          <ul className="oe-ledger">
            {board.caution.slice(0, CAUTION_ON_HOME).map((card) => <LedgerItem key={card.term_id} locale={locale} edition={edition} card={card} generatedAt={at} />)}
          </ul>
          {board.totals.caution > CAUTION_ON_HOME && <Link href={list("caution")} className="oe-link oe-rubric-more">{c.seeAll(board.totals.caution)}</Link>}
        </Rubric>
      )}

      <div style={{ height: 72 }} />
    </>
  );
}
