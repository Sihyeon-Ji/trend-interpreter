import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { entryHref, glossOf } from "@/lib/lab/f-editorial";
import { fmtDate, sourceName } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { GenerationCurve } from "@/lib/trends/types";
import type { Evidence, KeywordCard, MeaningText } from "@/lib/types";
import { AgeCurves } from "./charts";
import { Stickers } from "./stickers";
import { StarButton } from "./watchlist";

/* 이번 주 표지 — 대담함은 여기 한 곳. 코발트 면 위에 밈 이름을 포스터처럼 크게, 그 아래 확인된 뜻과 브랜드 메모(뉘앙스).
   오른쪽에는 나이대별 검색 관심, 그것이 없으면 유래(출처와 함께). 이름이 그림이므로 영상·사진이 없어도 비지 않는다. */
export function Cover({ card, text, refs, curves, locale, edition, canMake }: {
  card: KeywordCard; text: MeaningText | null; refs: Evidence[]; curves: GenerationCurve[]; locale: Locale; edition: string; canMake: boolean;
}) {
  const gloss = glossOf(card, locale);
  const textLang = locale === "en" && !text ? "ko" : undefined;
  const href = entryHref(card.term_id, edition);
  const hasCurves = curves.some((c) => c.points.length > 1);
  const origin = text?.origin && text.origin !== "unknown" ? text.origin : null;
  const aside = hasCurves ? "curves" : origin ? "origin" : null;
  return (
    <section className="fe-cover" aria-labelledby="fe-cover-title">
      <div className="fe-wrap">
        <div className="fe-cover__top">
          <p className="fe-cover__label">{fe(locale, "cover_label")}</p>
          <span>
            <Stickers item={card} locale={locale} full />
            <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} locale={locale} />
          </span>
        </div>
        <div className={aside ? "fe-cover__grid" : "fe-cover__grid fe-cover__grid--single"}>
          <div>
            <h2 id="fe-cover-title" className="fe-poster fe-cover__name fe-reveal"><Link href={href} lang={langTag(card.lang)}>{card.canonical}</Link></h2>
            <p className="fe-lede fe-reveal fe-reveal--2" lang={gloss.lang}>{gloss.text}</p>
            {text?.nuance && (
              <p className="fe-cover__note fe-reveal fe-reveal--3" lang={textLang}>
                <span className="fe-cover__note-label">{fe(locale, "brand_note")}</span>
                {text.nuance}
              </p>
            )}
            <div className="fe-cover__actions fe-reveal fe-reveal--3">
              {canMake && <Link href={`/recommend?term=${encodeURIComponent(card.term_id)}`} className="fe-btn fe-btn--primary">{fe(locale, "make")}</Link>}
              <Link href={href} className="fe-btn fe-btn--ghost">{fe(locale, "cover_read")}</Link>
            </div>
          </div>
          {aside === "curves" && (
            <div className="fe-cover__aside fe-reveal fe-reveal--3">
              <p className="fe-cover__label" style={{ marginBottom: 14 }}>{fe(locale, "e_ages")}</p>
              <AgeCurves curves={curves} locale={locale} onDark />
            </div>
          )}
          {aside === "origin" && origin && (
            <div className="fe-cover__aside fe-reveal fe-reveal--3">
              <p className="fe-cover__label">{fe(locale, "e_origin")}</p>
              <p lang={textLang}>{origin}</p>
              {refs.length > 0 && (
                <p className="fe-refs">
                  <span>{fe(locale, "e_sources")}</span>
                  {refs.map((e) => (
                    <a key={e.evidence_id} href={e.url} target="_blank" rel="noreferrer noopener" className="fe-link">{sourceName(locale, e.source_domain)} {fmtDate(e.observed_at)}<span className="sr-only"> ({fe(locale, "new_tab")})</span></a>
                  ))}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
