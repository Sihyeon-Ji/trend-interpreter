import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, regionLabel, sourceName } from "@/lib/labels";
import type { TrendWhy } from "@/lib/trends/types";

/* 왜 지금 뜨나 — 검색어 하나의 급증 원인 카드. 근거는 접어 두고 종류별 개수만 먼저 보인다. */
export function WhyCard({ w, locale, showRegion = false }: { w: TrendWhy; locale: Locale; showRegion?: boolean }) {
  const labels = L(locale);
  const counts = Object.entries(w.evidence_counts).sort((a, b) => b[1] - a[1]);
  return (
    <article className="border-t border-hairline py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="text-[15px] font-semibold text-ink">
          {showRegion && <span className="mr-1.5 text-[12px] font-normal text-steel">{regionLabel(locale, w.region)}</span>}{w.term}
        </h3>
        <span className="text-[12px] text-steel">{labels.trigger[w.trigger] ?? w.trigger} · {fmtDate(w.date)}</span>
      </div>
      <p className="mt-1 text-[14px] leading-relaxed text-charcoal">{w.why_now[locale]}</p>
      {w.confidence < 0.5 && <p className="mt-1 text-[12px] text-steel">{t(locale, "why_confidence_low")}</p>}
      <dl className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-steel">
        {w.actors.length > 0 && <div><dt className="inline">{t(locale, "why_actors")}: </dt><dd className="inline text-charcoal">{w.actors.map((a) => a.name).join(", ")}</dd></div>}
        {w.first_signal && <div><dt className="inline">{t(locale, "why_first_signal")}: </dt><dd className="inline text-charcoal tabular-nums">{fmtDate(w.first_signal)}</dd></div>}
      </dl>
      {w.evidence.length > 0 && (
        <details className="mt-1.5 text-[12px]">
          <summary className="cursor-pointer text-steel hover:text-ink">
            {t(locale, "why_evidence")} {counts.map(([k, n]) => `${labels.evidenceKind[k as keyof typeof labels.evidenceKind] ?? k} ${n}`).join(" · ")}
          </summary>
          <ul className="mt-1.5 space-y-1">
            {w.evidence.map((e) => (
              <li key={e.url} className="truncate">
                <span className="text-steel">{labels.evidenceKind[e.kind as keyof typeof labels.evidenceKind] ?? e.kind} · {sourceName(locale, e.source_domain)} · {fmtDate(e.observed_at)}</span>{" "}
                <Link href={e.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">{e.title}<span className="sr-only"> {t(locale, "feeds_new_window")}</span></Link>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
