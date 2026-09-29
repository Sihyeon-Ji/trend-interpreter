import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { fe } from "@/lib/lab/f-editorial-copy";
import { entryHref, glossOf, videoThumb, type SearchTrend } from "@/lib/lab/f-editorial";
import { fmtDate, regionLabel } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { KeywordCard } from "@/lib/types";
import { Sparkline } from "./charts";
import { Stickers, riskReasonText } from "./stickers";
import { StarButton } from "./watchlist";

/* 꼭지 하나 — 제목·건수·한 줄 안내, 그리고 격자. 비어 있으면 왜 비었는지 한 줄. */
export function Rubric({ id, title, note, count, empty, more, four = false, children }: {
  id: string; title: string; note?: string; count?: number; empty?: string; more?: React.ReactNode; four?: boolean; children?: React.ReactNode;
}) {
  return (
    <section className="fe-rubric" aria-labelledby={`${id}-title`}>
      <div className="fe-rubric__head">
        <h2 id={`${id}-title`} className="fe-h2">{title}{count !== undefined && count > 0 && <span className="fe-rubric__count">{count}</span>}</h2>
        {note && <p className="fe-rubric__note">{note}</p>}
      </div>
      {empty ? <p className="fe-rubric__empty">{empty}</p> : <div className={four ? "fe-grid fe-grid--4" : "fe-grid"}>{children}</div>}
      {more}
    </section>
  );
}

/* 미니 포스터 — 이름이 그림이다. 영상이 실제로 있을 때만 썸네일(대부분 없다). */
export function MemeCard({ card, locale, edition, trend, showReason = false, showRegions = false }: {
  card: KeywordCard; locale: Locale; edition: string; trend?: SearchTrend | null; showReason?: boolean; showRegions?: boolean;
}) {
  const gloss = glossOf(card, locale);
  const thumb = videoThumb(card.evidences);
  const reason = showReason ? riskReasonText(card, locale) : null;
  const regions = showRegions && card.regions.length ? card.regions.map((r) => regionLabel(locale, r)).join(", ") : null;
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
        <h3 className="fe-card-name"><Link href={entryHref(card.term_id, edition)} lang={langTag(card.lang)}>{card.canonical}</Link></h3>
        <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} locale={locale} />
      </div>
      <p className="fe-cell__gloss" lang={gloss.lang}>{gloss.text}</p>
      {reason && <p className={riskOf(card) === "avoid" ? "fe-cell__reason fe-cell__reason--avoid" : "fe-cell__reason"}>{reason}</p>}
      <div className="fe-cell__foot">
        <Stickers item={card} locale={locale} />
        {trend ? <Sparkline trend={trend} locale={locale} />
          : regions ? <span className="fe-cell__meta">{regions}</span>
            : card.last_used ? <span className="fe-cell__meta">{fe(locale, "last_used", { date: fmtDate(card.last_used) })}</span> : null}
      </div>
    </article>
  );
}
