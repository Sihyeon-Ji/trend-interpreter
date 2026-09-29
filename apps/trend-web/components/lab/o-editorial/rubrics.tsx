/* eslint-disable @next/next/no-img-element -- 유튜브 미리보기는 주소만 쓰는 평범한 <img>(파일을 받지 않는다, 이미지 설정에 외부 도메인을 열지 않는다) */
import Link from "next/link";
import type { ReactNode } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import {
  AGE_ORDER, ageName, cardVideo, copy, entryHref, fadeReason, fmtDay, glossOf, notableStage, pct, riskKind, riskNotes, riskTone, riskWhy, riskWord,
  stageTape, usedAgo, type EditionKey, type SearchSummary,
} from "@/lib/lab/o-editorial";
import type { KeywordCard } from "@/lib/types";
import { ScrapButton, SinceBadge } from "./client";
import { FitName, Tape } from "./type";

export type SinceMark = { at: string; kind: "verified" | "meaning_changed" };

const STRIP_MAX = 2;    // 나이대 막대 끝 = ±200%. 넘는 값은 끝을 각지게 잘라 보이고 숫자는 그대로
const BAR_MAX = 1;      // 순위 줄의 가운데 값 막대 끝 = +100%

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

function RiskTape({ locale, card }: { locale: Locale; card: KeywordCard }) {
  const k = riskKind(card);
  const tone = riskTone(k);
  return tone ? <Tape tone={tone}>{riskWord(locale, k)}</Tape> : null;
}

/** 마지막 쓰임을 지금에서 센 말로 — 모든 목록이 같은 잣대(며칠 전)로. 날짜 자체는 title·dateTime 에 */
function UsedAgo({ locale, card, asOf }: { locale: Locale; card: KeywordCard; asOf: string }) {
  const d = card.last_used ?? card.last_seen;
  const text = usedAgo(locale, d, asOf);
  return text && d ? <time className="oe-used oe-num" dateTime={d} title={fmtDay(locale, d)}>{text}</time> : null;
}

/** 포스터의 비교할 숫자 — 네이버 나이대별 4주 변화의 가운데 값. 곡선이 있고 값이 설 때만. */
function SearchFigure({ locale, search }: { locale: Locale; search: SearchSummary | null | undefined }) {
  if (!search || search.median === null || search.valid < 3) return null;   // 나이대 셋 이상에 값이 설 때만(둘의 가운데 값은 이야기가 못 된다)
  const c = copy(locale);
  const v = pct(search.median);
  return (
    <span className="oe-figure-search" data-down={search.median < 0}>
      <span aria-hidden>{c.posterSearch} </span>
      <span aria-hidden className="oe-num">{v}</span>
      <span className="oe-sr">{c.posterSearchSr(v)}</span>
    </span>
  );
}

/** 지금 쓰이는 밈 한 장 — 이름이 곧 그림. 위 칸은 알릴 것(새로 실림·뜻 바뀜·주의·꼭지의 보통과 다른 단계)만, 아래 칸은 견줄 숫자(며칠 전 쓰임·검색 변화).
 *  영상 근거가 있을 때만 미리보기를 싣는다(대부분 없다). */
export function Poster({ locale, edition, card, feature, since, search, asOf }: {
  locale: Locale; edition: EditionKey; card: KeywordCard; feature?: boolean; since?: SinceMark; search?: SearchSummary | null; asOf: string;
}) {
  const c = copy(locale);
  const g = glossOf(locale, card);
  const lang = langTag(card.lang);
  const video = cardVideo(card);
  const stage = notableStage(locale, card);
  return (
    <article className="oe-poster" data-feature={feature ? "true" : undefined}>
      <div className="oe-poster-top">
        <span className="oe-tapes">
          {since && <SinceBadge locale={locale} at={since.at} kind={since.kind} />}
          <RiskTape locale={locale} card={card} />
          {stage && <Tape tone={stage.tone}>{stage.text}</Tape>}
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
        <UsedAgo locale={locale} card={card} asOf={asOf} />
        <SearchFigure locale={locale} search={search} />
      </div>
      {/* 스크랩 단추는 오른쪽 위에 보이지만 DOM 에서는 이름 뒤 — 키보드가 이름(기사로 가는 길)을 먼저 만난다 */}
      <div className="oe-poster-save">
        <ScrapButton locale={locale} scrap={{ id: card.term_id, name: card.canonical, lang, lifecycle: card.lifecycle, diffusion: card.diffusion ?? null, risk: riskKind(card) }} />
      </div>
    </article>
  );
}

/** 나이대별 4주 변화 — 가운데 0 에서 늘면 오른쪽(울트라마린), 줄면 왼쪽(회색). ±200% 를 끝으로 잡고 숫자는 그대로.
 *  전 4주에 거의 찾지 않던 나이대('전엔 거의 없음')와 날이 모자란 나이대('자료 부족')는 막대 없이 말로. */
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
            <dd className="oe-strip-val">{v === null ? <span className="oe-strip-thin">{a?.state === "low" ? c.lowBase : c.thin}</span> : pct(v)}</dd>
          </div>
        );
      })}
    </dl>
  );
}

/** 요즘 더 찾는 밈 한 줄 — 순위, 이름·뜻, 그리고 견줄 숫자 하나(나이대별 변화의 가운데 값)와 막대. 나이대 다섯 줄은 접어 둔다.
 *  커버에 실린 밈은 한 줄로만 적고 커버로 잇는다(같은 이야기를 두 번 싣지 않게). */
export function RankRow({ locale, edition, card, search, rank, generatedAt, isCover }: {
  locale: Locale; edition: EditionKey; card: KeywordCard; search: SearchSummary; rank: number; generatedAt: string; isCover?: boolean;
}) {
  const c = copy(locale);
  const g = glossOf(locale, card);
  const lang = langTag(card.lang);
  const m = search.median ?? 0;
  const cut = m > BAR_MAX;
  const bar = (
    <span className="oe-rank-bar" aria-hidden>
      <span className="oe-rank-fill" data-cut={cut} style={{ width: `${(Math.min(BAR_MAX, Math.max(0, m)) / BAR_MAX) * 100}%` }} />
    </span>
  );
  if (isCover) {
    return (
      <li className="oe-rank oe-rank-cover">
        <span className="oe-rank-no" aria-hidden>{rank}</span>
        <p className="oe-rank-cover-line">
          <span className="oe-sr">{c.rankLabel(rank)} </span>
          <a href="#cover" className="oe-rank-name oe-poster-link" lang={lang}>{card.canonical}</a>
          <span className="oe-meta">{c.coverRow}</span>
        </p>
        <div className="oe-rank-figure">
          <span className="oe-rank-pct oe-num">{pct(m)}</span>
          {bar}
        </div>
      </li>
    );
  }
  const st = stageTape(locale, card);
  return (
    <li className="oe-rank">
      <span className="oe-rank-no" aria-hidden>{rank}</span>
      <div className="oe-rank-main">
        <h3 style={{ margin: 0 }}>
          <span className="oe-sr">{c.rankLabel(rank)} </span>
          <Link href={entryHref(card.term_id, edition)} className="oe-rank-name oe-poster-link" lang={lang}>{card.canonical}</Link>
        </h3>
        {g.text && <p className="oe-poster-gloss" lang={g.lang}>{g.text}</p>}
        <span className="oe-tapes">
          <Tape tone={st.tone}>{st.text}</Tape>
          <RiskTape locale={locale} card={card} />
        </span>
      </div>
      <div className="oe-rank-figure">
        <span className="oe-rank-pct oe-num">{pct(m)}</span>
        {bar}
        <p className="oe-meta oe-num">{c.agesUp(search.up, search.valid)} {search.end && c.windowEnd(fmtDay(locale, search.end, generatedAt))}</p>
        <details className="oe-details oe-rank-ages">
          <summary>{c.agesOpen}</summary>
          <AgeStrip locale={locale} name={card.canonical} search={search} />
        </details>
      </div>
    </li>
  );
}

/** 식어 가는 밈 — 색인처럼 가볍게. 이름·뜻 한 줄 | 그 목록에 선 까닭 | 며칠 전 쓰임(오른쪽 맞춤) */
export function IndexItem({ locale, edition, card, generatedAt }: { locale: Locale; edition: EditionKey; card: KeywordCard; generatedAt: string }) {
  const g = glossOf(locale, card);
  return (
    <li className="oe-index-item">
      <div className="oe-index-main">
        <Link href={entryHref(card.term_id, edition)} className="oe-index-name" lang={langTag(card.lang)}>{card.canonical}</Link>
        {g.text && <p className="oe-index-gloss" lang={g.lang}>{g.text}</p>}
      </div>
      <div className="oe-index-side">
        <RiskTape locale={locale} card={card} />
        <span className="oe-index-why">{fadeReason(locale, card, generatedAt)}</span>
        <UsedAgo locale={locale} card={card} asOf={generatedAt} />
      </div>
    </li>
  );
}

/** 브랜드는 조심 — 장부. 수준 테이프가 줄의 머리(한 열로 내려 읽힌다), 이름·뜻, 쉬운 말로 옮긴 이유(인용 없이), 단계와 며칠 전 쓰임(오른쪽 맞춤) */
export function LedgerItem({ locale, edition, card, generatedAt }: { locale: Locale; edition: EditionKey; card: KeywordCard; generatedAt: string }) {
  const k = riskKind(card);
  const notes = riskNotes(locale, card.risk_reasons);
  const g = glossOf(locale, card);
  return (
    <li className="oe-ledger-item">
      <span className="oe-ledger-level"><RiskTape locale={locale} card={card} /></span>
      <div className="oe-ledger-main">
        <Link href={entryHref(card.term_id, edition)} className="oe-ledger-name" lang={langTag(card.lang)}>{card.canonical}</Link>
        {g.text && <p className="oe-index-gloss" lang={g.lang}>{g.text}</p>}
      </div>
      <div className="oe-ledger-why">
        {(notes.length ? notes : [riskWhy(locale, k)]).slice(0, 2).map((n) => <p key={n}>{n}</p>)}
      </div>
      <div className="oe-ledger-side">
        <span>{stageTape(locale, card).text}</span>
        <UsedAgo locale={locale} card={card} asOf={generatedAt} />
      </div>
    </li>
  );
}
