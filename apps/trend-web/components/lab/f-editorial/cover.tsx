import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { editionName, entryHref, glossOf, issueHref, type CoverRule, type SourceItem } from "@/lib/lab/f-editorial";
import { fmtDate } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordCard, MeaningText } from "@/lib/types";
import { AgeCurves } from "./age-curves";
import { Stickers, riskKeyOf } from "./stickers";
import { StarButton } from "./watchlist";

/** 긴 이름은 포스터 크기를 한두 단계 내린다 — 128px 로 넉 줄이 되는 것보다 두 줄이 낫다. 한·중·일 글자는 라틴보다 넓어 더 짧게 센다. */
export function posterSize(name: string): string {
  const cjk = (name.match(/[가-힣一-鿿぀-ヿ]/g) ?? []).length;
  const width = [...name].length + cjk * 0.6;   // 대략의 폭(라틴 글자 단위)
  return width > 24 ? "fe-poster--longer" : width > 13 ? "fe-poster--long" : "";
}

/* 이번 주 표지 — 대담함은 여기 한 곳. 코발트 면 위에 밈 이름을 포스터처럼 크게, 그 아래 확인된 뜻과 브랜드 메모(뉘앙스).
   어느 규칙으로 골랐는지 표지 이름 아래 한 줄로 적는다. 오른쪽에는 나이대별 검색 관심, 그것이 없으면 유래(참고 문서와 함께).
   이름이 그림이므로 영상·사진이 없어도 비지 않는다. */
export function Cover({ card, rule, text, refs, curves, locale, edition, canMake }: {
  card: KeywordCard; rule: CoverRule; text: MeaningText | null; refs: SourceItem[]; curves: GenerationCurve[]; locale: Locale; edition: string; canMake: boolean;
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
          <div>
            <p className="fe-cover__label">{fe(locale, "cover_label")}</p>
            <p className="fe-cover__rule">{fe(locale, `cover_rule_${rule}`)}</p>
          </div>
          <span className="fe-cover__state">
            <Stickers item={card} locale={locale} full />
            <StarButton item={{ id: card.term_id, name: card.canonical, lang: card.lang }} state={{ stage: card.lifecycle, risk: riskKeyOf(card) }} locale={locale} />
          </span>
        </div>
        <div className={aside ? "fe-cover__grid" : "fe-cover__grid fe-cover__grid--single"}>
          <div>
            <h2 id="fe-cover-title" className={`fe-poster fe-cover__name fe-reveal ${posterSize(card.canonical)}`}><Link href={href} lang={langTag(card.lang)}>{card.canonical}</Link></h2>
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
                  {refs.map((s) => (
                    <a key={s.id} href={s.url} target="_blank" rel="noreferrer noopener" className="fe-link">{s.source} {fmtDate(s.date)}<span className="sr-only"> ({fe(locale, "new_tab")})</span></a>
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

/* 실린 밈이 없는 판 — 코발트 면 대신 종이 위에 다음 할 일. 빈 판도 열리게 두는 것이 정보다(작은 시장의 마케터에게). */
export function EmptyCover({ locale, edition }: { locale: Locale; edition: string }) {
  return (
    <section className="fe-wrap fe-empty" aria-labelledby="fe-empty-title">
      <h2 id="fe-empty-title" className="fe-h2">{fe(locale, "empty_title", { edition: editionName(locale, edition) })}</h2>
      <p className="fe-body">{fe(locale, "empty_body")}</p>
      <Link href={issueHref("ALL")} className="fe-btn fe-btn--primary">{fe(locale, "empty_action")}</Link>
    </section>
  );
}
