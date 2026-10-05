import { RiskCell, StageCell } from "@/components/term-status";
import { t, type Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { scriptLang } from "@/lib/lang";
import { fmtDate, fmtInt } from "@/lib/labels";
import type { Term } from "@/lib/types";

/** 쓸 때 조심 아래 한 줄. 한국어 화면은 규칙이 남긴 실제 이유를, 영어 화면은 이유가 한국어뿐이라 일반 설명을 쓴다.
 *  검수자가 정한 수준이면 규칙의 이유를 붙이지 않는다 — 규칙이 반대로 보았을 수 있다(검토 2차). 검사 전이면 줄이 없다. */
export function riskReason(term: Term, locale: Locale): string | null {
  const r = riskOf(term);
  if (term.risk_human && (r || term.risk_level === "none")) return t(locale, "risk_by_reviewer");
  if (r === "caution" || r === "avoid") {
    const own = (term.risk_reasons ?? []).find((x) => x !== "검수자가 정한 수준");
    return locale === "ko" && own ? own : t(locale, `risk_${r}_why`);
  }
  if (r === "unknown") return t(locale, "risk_unknown_why");
  return term.risk_level === "none" ? t(locale, "risk_none_why") : null;
}

export interface SummaryProps {
  locale: Locale;
  term: Term;
  verified: boolean;             // 확인 중이면 단계·쓸 때 조심을 '확인 전' 으로
  regions: string | null;
  gens: string | null;
  mentions: number | null;
  scope: string;
  lastUsed: string | null;
  plain: string | null;
  popularYear?: number | null;
  popularDecade?: number | null;
  plainLang?: string;
  sources: number;
}

/* 사전 항목 요약 — 머리 바로 다음(DOM 도 처음)에 두어 "지금 써도 되나" 를 본문을 읽기 전에 답한다.
   단계·쓸 때 조심은 대시보드 표와 같은 칸(term-status.tsx)이라 두 화면이 같은 말을 쓴다. */
export function TermSummary(p: SummaryProps) {
  const { locale, term } = p;
  const row = (label: string, value: React.ReactNode) => (
    <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-x-3 py-2">
      <dt className="text-[13px] text-steel">{label}</dt>
      <dd className="min-w-0 text-[14px] text-ink">{value}</dd>
    </div>
  );
  const why = (text: string | null) => text && <span className="mt-1 block text-[13px] leading-[1.5] text-steel">{text}</span>;
  const era = p.popularYear ? t(locale, "term_sum_era_year").replace("{y}", String(p.popularYear))
    : p.popularDecade ? t(locale, "term_sum_era_decade").replace("{y}", String(p.popularDecade)) : null;
  const notYet = <span className="text-[13px] text-steel">{t(locale, "risk_not_checked")}</span>;
  return (
    <aside aria-labelledby="term-summary" className="rounded-lg border border-hairline px-4 py-3">
      <h2 id="term-summary" className="text-[14px] font-semibold text-ink">{t(locale, "term_sum_title")}</h2>
      <dl className="mt-1 grid md:grid-cols-2 md:gap-x-8 xl:grid-cols-1">
        {row(t(locale, "term_sum_stage"), p.verified
          ? <><StageCell diffusion={term.diffusion} lifecycle={term.lifecycle ?? "unknown"} locale={locale} />
            {term.diffusion ? why(t(locale, `diffusion_${term.diffusion}_why`)) : (term.lifecycle ?? "unknown") === "unknown" && why(t(locale, "lifecycle_unknown_why"))}</>
          : notYet)}
        {row(t(locale, "term_sum_risk"), p.verified ? <><RiskCell item={term} locale={locale} />{why(riskReason(term, locale))}</> : notYet)}
        {p.regions && row(t(locale, "term_sum_regions"), p.regions)}
        {p.gens && row(t(locale, "term_sum_gens"), p.gens)}
        {p.mentions !== null && row(t(locale, "term_sum_mentions"),
          <><span className="tabular-nums">{fmtInt(p.mentions)}</span><span className="mt-0.5 block text-[13px] text-steel">{p.scope}</span></>)}
        {era && row(t(locale, "term_sum_era"), <span className="tabular-nums">{era}</span>)}
        {p.lastUsed && row(t(locale, "term_sum_last_used"), <span className="tabular-nums">{fmtDate(p.lastUsed)}</span>)}
        {p.plain && row(t(locale, "term_sum_plain"), <span lang={p.plainLang}>{p.plain}</span>)}
        {(term.aliases?.length ?? 0) > 0 && row(t(locale, "term_other_spellings"),
          term.aliases!.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>))}
        {p.sources > 0 && row(t(locale, "term_sum_sources"),
          <a href="#sources" className="text-link-blue hover:underline">{t(locale, "term_sum_sources_link").replace("{n}", fmtInt(p.sources))}</a>)}
      </dl>
    </aside>
  );
}
