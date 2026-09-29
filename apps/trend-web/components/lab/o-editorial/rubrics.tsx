/* eslint-disable @next/next/no-img-element -- 유튜브 미리보기는 주소만 쓰는 평범한 <img>(파일을 받지 않는다, 이미지 설정에 외부 도메인을 열지 않는다) */
import Link from "next/link";
import type { ReactNode } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import {
  AGE_ORDER, ageName, cardVideo, copy, entryHref, fmtDay, glossOf, listTapes, pct, riskKind, riskNotes, riskTone, riskWhy, riskWord,
  type EditionKey, type SearchSummary,
} from "@/lib/lab/o-editorial";
import type { KeywordCard } from "@/lib/types";
import { ScrapButton, SinceBadge } from "./client";
import { FitName, Tape } from "./type";

export type SinceMark = { at: string; kind: "verified" | "meaning_changed" };

const STRIP_MAX = 2;    // 막대 끝 = ±200%. 넘는 값은 끝을 각지게 잘라 보이고 숫자는 그대로

export function RubricHead({ id, title, count, note }: { id: string; title: string; count: string; note: string }) {
  return (
    <header className="oe-rubric-head">
      <h2 id={id} className="oe-rubric-title">
        {title}
        <span className="oe-rubric-count oe-num">{count}</span>
      </h2>
      <p className="oe-rubric-note">{note}</p>
    </header>
  );
}

export function Rubric({ id, children }: { id: string; children: ReactNode }) {
  return <section className="oe-wrap oe-rubric" id={id} aria-labelledby={`${id}-title`}>{children}</section>;
}

function StageTapes({ locale, card }: { locale: Locale; card: KeywordCard }) {
  return <>{listTapes(locale, card).map((t) => <Tape key={t.text} tone={t.tone}>{t.text}</Tape>)}</>;
}

function RiskTape({ locale, card }: { locale: Locale; card: KeywordCard }) {
  const k = riskKind(card);
  const tone = riskTone(k);
  return tone ? <Tape tone={tone}>{riskWord(locale, k)}</Tape> : null;
}

function lastUsed(locale: Locale, card: KeywordCard, ref: string) {
  const d = card.last_used ?? card.last_seen;
  return d ? <span className="oe-meta oe-num">{copy(locale).lastUsedLabel} {fmtDay(locale, d, ref)}</span> : null;
}

/** 지금 쓰이는 밈 한 장 — 이름이 곧 그림. 영상 근거가 있을 때만 미리보기를 싣는다(대부분 없다). */
export function Poster({ locale, edition, card, feature, since, generatedAt }: {
  locale: Locale; edition: EditionKey; card: KeywordCard; feature?: boolean; since?: SinceMark; generatedAt: string;
}) {
  const c = copy(locale);
  const g = glossOf(locale, card);
  const lang = langTag(card.lang);
  const video = cardVideo(card);
  return (
    <article className="oe-poster" data-feature={feature ? "true" : undefined}>
      <div className="oe-poster-top">
        <span className="oe-tapes">
          <StageTapes locale={locale} card={card} />
          <RiskTape locale={locale} card={card} />
        </span>
      </div>
      {video && (
        <a className="oe-thumb" href={video.url} target="_blank" rel="noreferrer noopener">
          <img src={`https://i.ytimg.com/vi/${video.id}/mqdefault.jpg`} alt={c.videoAlt(card.canonical)} loading="lazy" width={320} height={180} />
        </a>
      )}
      <h3 className="oe-fit oe-poster-name" style={{ margin: 0 }}>
        <Link href={entryHref(card.term_id, edition)} className="oe-poster-link">
          <FitName name={card.canonical} lang={lang} maxLines={3} splitAbove={feature ? 4.2 : 5} />
        </Link>
      </h3>
      {g.text && <p className="oe-poster-gloss" lang={g.lang}>{g.text}</p>}
      <div className="oe-poster-foot">
        {lastUsed(locale, card, generatedAt)}
        {since && <SinceBadge locale={locale} at={since.at} kind={since.kind} />}
      </div>
      {/* 스크랩 단추는 오른쪽 위에 보이지만 DOM 에서는 이름 뒤 — 키보드가 이름(기사로 가는 길)을 먼저 만난다 */}
      <div className="oe-poster-save">
        <ScrapButton locale={locale} scrap={{ id: card.term_id, name: card.canonical, lang, lifecycle: card.lifecycle, diffusion: card.diffusion ?? null, risk: riskKind(card) }} />
      </div>
    </article>
  );
}

/** 나이대별 4주 변화 — 가운데 0 에서 늘면 오른쪽(울트라마린), 줄면 왼쪽(회색). ±200% 를 끝으로 잡고 숫자는 그대로. */
export function AgeStrip({ locale, name, search }: { locale: Locale; name: string; search: SearchSummary }) {
  const c = copy(locale);
  return (
    <dl className="oe-strip" aria-label={c.ageStripLabel(name)}>
      {AGE_ORDER.map((g) => {
        const a = search.ages.find((x) => x.gen === g);
        const v = a?.change ?? null;
        const cut = v !== null && Math.abs(v) > STRIP_MAX;
        const w = v === null ? 0 : (Math.min(STRIP_MAX, Math.abs(v)) / STRIP_MAX) * 50;
        return (
          <div key={g} className="oe-strip-row">
            <dt className="oe-strip-age">{ageName(locale, g)}</dt>
            <span className="oe-strip-bar" aria-hidden>
              {v !== null && <span className="oe-strip-fill" data-down={v < 0} data-cut={cut} style={v < 0 ? { right: "50%", width: `${w}%` } : { left: "50%", width: `${w}%` }} />}
            </span>
            <dd className="oe-strip-val">{v === null ? <span className="oe-strip-thin">{c.thin}</span> : pct(v)}</dd>
          </div>
        );
      })}
    </dl>
  );
}

export function RankRow({ locale, edition, card, search, rank, generatedAt }: {
  locale: Locale; edition: EditionKey; card: KeywordCard; search: SearchSummary; rank: number; generatedAt: string;
}) {
  const c = copy(locale);
  const g = glossOf(locale, card);
  const lang = langTag(card.lang);
  return (
    <li className="oe-rank">
      <span className="oe-rank-no" aria-hidden>{rank}</span>
      <div className="oe-rank-main">
        <h3 style={{ margin: 0 }}>
          <span className="oe-sr">{c.rankLabel(rank)} </span>
          <Link href={entryHref(card.term_id, edition)} className="oe-rank-name oe-poster-link" lang={lang}>{card.canonical}</Link>
        </h3>
        {g.text && <p className="oe-poster-gloss" lang={g.lang} style={{ WebkitLineClamp: 2 }}>{g.text}</p>}
        <span className="oe-tapes">
          <StageTapes locale={locale} card={card} />
          <RiskTape locale={locale} card={card} />
        </span>
        <p className="oe-meta oe-num">
          {c.agesUp(search.up, search.valid)} {search.end && c.windowEnd(fmtDay(locale, search.end, generatedAt))}
        </p>
      </div>
      <div className="oe-rank-strip"><AgeStrip locale={locale} name={card.canonical} search={search} /></div>
    </li>
  );
}

/** 12주 언급 없이 마지막 쓰임이 90일을 넘었나 — 백엔드가 이 말을 '식어 가는 밈' 에 둔 까닭(dashboard._stale)을 보인다 */
function stale(card: KeywordCard, ref: string): boolean {
  const last = card.last_used ?? card.last_seen;
  return !!last && !card.weekly?.some((p) => p.count) && Date.parse(ref) - Date.parse(last) > 90 * 86_400_000;
}

/** 식어 가는 밈 — 색인처럼 가볍게 */
export function IndexItem({ locale, edition, card, generatedAt }: { locale: Locale; edition: EditionKey; card: KeywordCard; generatedAt: string }) {
  const g = glossOf(locale, card);
  const old = stale(card, generatedAt) && card.lifecycle !== "declining" && card.lifecycle !== "dormant";
  return (
    <li className="oe-index-item">
      <Link href={entryHref(card.term_id, edition)} className="oe-index-name" lang={langTag(card.lang)}>{card.canonical}</Link>
      {g.text && <p className="oe-index-gloss" lang={g.lang}>{g.text}</p>}
      <div className="oe-index-foot">
        <StageTapes locale={locale} card={card} />
        {old && <Tape tone="fade">{copy(locale).staleTape}</Tape>}
        <RiskTape locale={locale} card={card} />
        {lastUsed(locale, card, generatedAt)}
      </div>
    </li>
  );
}

/** 브랜드는 조심 — 수준, 이름, 쉬운 말로 옮긴 이유(인용 없이), 단계 */
export function LedgerItem({ locale, edition, card, generatedAt }: { locale: Locale; edition: EditionKey; card: KeywordCard; generatedAt: string }) {
  const k = riskKind(card);
  const notes = riskNotes(locale, card.risk_reasons);
  const g = glossOf(locale, card);
  return (
    <li className="oe-ledger-item">
      <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
        <span className="oe-tapes"><RiskTape locale={locale} card={card} /></span>
        <Link href={entryHref(card.term_id, edition)} className="oe-ledger-name" lang={langTag(card.lang)}>{card.canonical}</Link>
        {g.text && <p className="oe-index-gloss" lang={g.lang}>{g.text}</p>}
      </div>
      <div className="oe-ledger-why">
        {(notes.length ? notes : [riskWhy(locale, k)]).slice(0, 3).map((n) => <p key={n}>{n}</p>)}
      </div>
      <div className="oe-ledger-side">
        <StageTapes locale={locale} card={card} />
        {lastUsed(locale, card, generatedAt)}
      </div>
    </li>
  );
}
