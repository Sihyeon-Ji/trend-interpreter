import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { entryHref, glossOf, videoThumb, type SearchTrend } from "@/lib/lab/f-editorial";
import { fmtDate, regionLabel } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { KeywordCard } from "@/lib/types";
import { Sparkline } from "./charts";
import { Stickers, lifecycleWord, riskKeyOf, riskReasonText, riskWord, riskClass } from "./stickers";
import { StarButton } from "./watchlist";

/* 꼭지 하나 — 제목·건수·한 줄 안내, 그 아래 내용. 비어 있으면 제목과 '없습니다' 한 줄로 접는다(빈 격자를 그리지 않는다). */
export function Rubric({ id, title, note, count, empty, more, children }: {
  id: string; title: string; note?: string; count?: number; empty?: string; more?: React.ReactNode; children?: React.ReactNode;
}) {
  if (empty) {
    return (
      <section className="fe-rubric-line" aria-labelledby={`${id}-title`}>
        <h2 id={`${id}-title`} className="fe-rubric-line__title">{title}</h2>
        <p>{empty}</p>
      </section>
    );
  }
  return (
    <section className="fe-rubric" aria-labelledby={`${id}-title`}>
      <div className="fe-rubric__head">
        <h2 id={`${id}-title`} className="fe-h2">{title}{count !== undefined && count > 0 && <span className="fe-rubric__count">{count}</span>}</h2>
        {note && <p className="fe-rubric__note">{note}</p>}
      </div>
      {children}
      {more}
    </section>
  );
}

/** 포스터 격자 — 1280 이상에서 4열로 놓아 줄이 꽉 차면 4열, 3열로 꽉 차면 3열, 아니면 외톨이 칸이 덜 남는 쪽 */
export function PosterGrid({ count, children }: { count: number; children: React.ReactNode }) {
  const four = count % 4 === 0 || (count % 3 !== 0 && count > 4 && count % 4 !== 1);
  return <div className={four ? "fe-grid fe-grid--4" : "fe-grid"}>{children}</div>;
}

const cardState = (card: KeywordCard) => ({ stage: card.lifecycle, risk: riskKeyOf(card) });

function Meta({ card, locale, trend, showRegions }: { card: KeywordCard; locale: Locale; trend?: SearchTrend | null; showRegions: boolean }) {
  const regions = showRegions && card.regions.length ? card.regions.map((r) => regionLabel(locale, r)).join(", ") : null;
  if (trend) return <Sparkline trend={trend} locale={locale} />;
  if (regions) return <span className="fe-cell__meta">{regions}</span>;
  if (card.last_used) return <span className="fe-cell__meta">{fe(locale, "last_used", { date: fmtDate(card.last_used) })}</span>;
  return null;
}

/* 미니 포스터 — 이름이 그림이다. 영상이 실제로 있을 때만 썸네일(대부분 없다). rank 는 실제 순위(검색 상승)일 때만. */
export function MemeCard({ card, locale, edition, trend, rank, hideStage = false, showRegions = false }: {
  card: KeywordCard; locale: Locale; edition: string; trend?: SearchTrend | null; rank?: number; hideStage?: boolean; showRegions?: boolean;
}) {
  const gloss = glossOf(card, locale);
  const thumb = videoThumb(card.evidences);
  return (
    <article className="fe-cell">
      {thumb && (
        <a href={thumb.url} target="_blank" rel="noreferrer noopener" className="fe-cell__thumb">
          {/* 유튜브가 주는 그림을 그대로 잇는다 — 파일을 받아 두지 않는다 */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={thumb.img} alt="" loading="lazy" />
          <span className="sr-only">{fe(locale, "video")} ({fe(locale, "new_tab")})</span>
        </a>
      )}
      <div className="fe-cell__head">
        <h3 className="fe-card-name">
          {rank !== undefined && <span className="fe-cell__rank"><span aria-hidden>{rank}</span><span className="sr-only">{fe(locale, "rank", { n: rank })}</span></span>}
          <Link href={entryHref(card.term_id, edition)} lang={langTag(card.lang)}>{card.canonical}</Link>
        </h3>
        <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} state={cardState(card)} locale={locale} />
      </div>
      <p className="fe-cell__gloss" lang={gloss.lang}>{gloss.text}</p>
      <div className="fe-cell__foot">
        <Stickers item={card} locale={locale} hideStage={hideStage} />
        <Meta card={card} locale={locale} trend={trend} showRegions={showRegions} />
      </div>
    </article>
  );
}

/* 색인 줄 — 이름, 뜻 한 줄, 붙임표, 추세. 꾸준·식는 중처럼 긴 목록은 포스터 대신 이 줄로 훑는다. large 는 한둘뿐인 꼭지의 넓은 줄. */
export function IndexRow({ card, locale, edition, trend, hideStage = false, showRegions = false, large = false }: {
  card: KeywordCard; locale: Locale; edition: string; trend?: SearchTrend | null; hideStage?: boolean; showRegions?: boolean; large?: boolean;
}) {
  const gloss = glossOf(card, locale);
  return (
    <li className={large ? "fe-row fe-row--lg" : "fe-row"}>
      <div className="fe-row__name">
        <h3 className="fe-row__title"><Link href={entryHref(card.term_id, edition)} lang={langTag(card.lang)}>{card.canonical}</Link></h3>
        <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} state={cardState(card)} locale={locale} />
      </div>
      <p className="fe-row__gloss" lang={gloss.lang}>{gloss.text}</p>
      <div className="fe-row__meta">
        <Stickers item={card} locale={locale} hideStage={hideStage} />
        <Meta card={card} locale={locale} trend={trend} showRegions={showRegions} />
      </div>
    </li>
  );
}

/* 조심 점검표 줄 — 수준, 이름, 쉬운 이유, 단계. 색은 낱말과 테두리에만. */
export function LedgerRow({ card, locale, edition }: { card: KeywordCard; locale: Locale; edition: string }) {
  const risk = riskWord(card, locale);
  const reason = riskReasonText(card, locale);
  return (
    <li className="fe-ledger__row">
      <span className="fe-ledger__level">{risk && <span className={riskClass(risk.key)}>{risk.label}</span>}</span>
      <div className="fe-row__name">
        <h3 className="fe-row__title"><Link href={entryHref(card.term_id, edition)} lang={langTag(card.lang)}>{card.canonical}</Link></h3>
        <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} state={cardState(card)} locale={locale} />
      </div>
      <p className="fe-ledger__reason" lang={reason?.lang}>{reason?.text}</p>
      <span className="fe-ledger__stage"><span className="fe-sticker">{lifecycleWord(locale, card.lifecycle)}</span></span>
    </li>
  );
}
