import Link from "next/link";
import type { ExplainResult } from "@/lib/explain";
import { t, type Locale } from "@/lib/i18n";
import { fmtDate } from "@/lib/labels";
import { SourceList } from "./sources";

/** 해석 결과의 용어 카드. 뜻 하나하나에 근거 건수·마지막 확인·다음 재확인이 붙는다 — 이게 이 제품이 챗봇과 다른 지점이다. */
export function ExplainCards({ result, locale }: { result: ExplainResult; locale: Locale }) {
  return (
    <div className="space-y-6">
      {result.plain && (
        <div>
          <h3 className="text-[13px] font-medium text-steel">{t(locale, "home_plain")}</h3>
          <p className="mt-1 text-[16px] leading-[1.6] text-ink">{result.plain}</p>
        </div>
      )}
      <dl className="divide-y divide-hairline-soft border-y border-hairline-soft">
        {result.items.map((e) => (
          <div key={e.record.term.term_id} className="grid gap-x-8 gap-y-2 py-4 sm:grid-cols-[150px_1fr]">
            <dt>
              <span className="text-[17px] font-semibold text-ink">{e.record.term.canonical}</span>
              {e.matched !== e.record.term.canonical && <div className="mt-0.5 text-[13px] text-steel">{t(locale, "home_in_message")} &ldquo;{e.matched}&rdquo;</div>}
              {e.meaning && !e.meaning.verification?.startsWith("verified") && <div className="mt-0.5 text-[13px] text-steel">{t(locale, "home_pending")}</div>}
            </dt>
            <dd className="space-y-2">
              <p className="text-[15px] leading-[1.6] text-ink">{e.headline}</p>
              {e.background && <p className="text-[14px] leading-[1.7] text-charcoal">{e.background}</p>}
              <div className="space-y-1 text-[13px]">
                <p className="text-steel">
                  {t(locale, "home_trust_evidence")} {e.record.evidences.length}
                  {e.meaning && <> · {t(locale, "home_trust_last")} {fmtDate(e.meaning.valid_from)}</>}
                  {" · "}{t(locale, "home_trust_next")} {e.record.recheck_days}{locale === "ko" ? "일 후" : " days"}
                </p>
                <SourceList sources={e.record.evidences.slice(0, 1)} locale={locale} compact />
                <Link href={`/dictionary/${e.record.term.term_id}`} className="inline-block text-link-blue hover:underline">{t(locale, "home_more")}</Link>
              </div>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
