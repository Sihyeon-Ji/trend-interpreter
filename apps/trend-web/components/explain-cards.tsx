import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { jaUntranslated, type ExplainResult, type Explanation } from "@/lib/explain";
import { measuredUsage } from "@/lib/dictionary/regions";
import { t, type Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { L, fmtDate, regionLabel, sourceName, nuanceChecked } from "@/lib/labels";

/* 메시지 해석 결과. 원문 → 쉽게 풀어 쓰면 → 찾은 표현(표현마다 뜻과 라벨 행). 상자·그림자 없이 행 사이 선만 둔다.
   표현마다 단계·쓸 때 조심을 대시보드와 같은 말로 보인다 — '이 말을 지금 써도 되나' 에 답하는 것이 이 화면의 일이다. */

const rowGrid = "grid grid-cols-[88px_minmax(0,1fr)] gap-x-4 gap-y-1 sm:grid-cols-[112px_minmax(0,1fr)]";

/** 목록은 ', ' 로 잇는다 — 가운뎃점으로 이으면 휴대폰에서 줄이 '·' 로 시작했다 */
const list = (items: string[]) => items.join(", ");

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={`${rowGrid} py-1.5`}>
      <dt className="text-[13px] leading-[1.55] font-medium text-steel">{label}</dt>
      <dd className="min-w-0 text-[14px] leading-[1.55] text-charcoal">{children}</dd>
    </div>
  );
}

/** 결과 머리: h2 '결과' + (예시면) 예시 배지와 안내 + 요약 한 줄. */
export function ResultHeader({ locale, summary, sample = false, headingRef, headingId }: {
  locale: Locale; summary?: React.ReactNode; sample?: boolean; headingRef?: React.Ref<HTMLHeadingElement>; headingId?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <h2 ref={headingRef} id={headingId} tabIndex={-1} className="text-[18px] font-semibold text-ink outline-none">{t(locale, "pg_ex_result")}</h2>
        {sample && <StatusBadge tone="muted">{t(locale, "pg_sample_badge")}</StatusBadge>}
      </div>
      {sample && <p className="text-[14px] leading-[1.55] text-steel">{t(locale, "pg_ex_sample_note")}</p>}
      {summary && <p className="text-[15px] leading-[1.55] text-charcoal">{summary}</p>}
    </div>
  );
}

export const foundSummary = (locale: Locale, n: number) => t(locale, "pg_ex_found").replace("{n}", String(n));

/** 표현 한 줄: 표제어(사전 링크) → 뜻 → 라벨 행. 값이 없는 행은 뺀다. */
export function ExpressionRow({ e, locale }: { e: Explanation; locale: Locale }) {
  const { record, meaning, text } = e;
  const term = record.term;
  const labels = L(locale);
  const id = term.term_id;
  // 영어·일본어 화면에서 번역 없이 원문(대개 한국어) 뜻으로 대신 나가는 줄
  const untranslated = locale === "en" && !record.en ? "ko" : locale === "ja" && jaUntranslated(record) ? scriptLang(text?.definition ?? "") ?? "ko" : undefined;
  const gens = [...new Set(measuredUsage(record.usage).map((u) => u.segment.generation))];
  // 가장 최근 근거 한 건. 검색 통계와 홈페이지 주소뿐인 것은 쓰인 글이 아니라 뺀다(대시보드와 같은 규칙) — 없으면 아무 근거나
  const byDate = [...record.evidences].sort((a, b) => b.observed_at.localeCompare(a.observed_at));
  const latest = byDate.find((x) => x.kind !== "datalab" && /^https?:\/\/[^/]+\/./.test(x.url)) ?? byDate[0];
  return (
    <li id={`term-${id}`} className="scroll-mt-20 py-5 lg:scroll-mt-6">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-[16px] font-semibold text-ink">
          <Link href={`/dictionary/${id}`} lang={langTag(term.lang)} className="hover:underline">{term.canonical}</Link>
        </h3>
        {e.matched !== term.canonical && (
          <span className="text-[13px] text-steel">{t(locale, "home_in_message")} &ldquo;<span lang={langTag(term.lang)}>{e.matched}</span>&rdquo;</span>
        )}
        {meaning && !meaning.verification?.startsWith("verified") && <StatusBadge tone="muted">{t(locale, "home_pending")}</StatusBadge>}
      </div>
      <p lang={untranslated} className="mt-1.5 text-[15px] leading-[1.6] text-ink">{e.headline}</p>
      <dl className="mt-2">
        <Row label={t(locale, "dash_col_stage")}><StageCell diffusion={term.diffusion} lifecycle={term.lifecycle ?? "unknown"} locale={locale} /></Row>
        <Row label={t(locale, "dash_col_risk")}><RiskCell item={term} locale={locale} /></Row>
        {text?.nuance && (
          <Row label={t(locale, "term_nuance")}>
            <span lang={untranslated}>{text.nuance}</span>
            {!nuanceChecked(meaning) && <StatusBadge tone="muted" className="ml-2 align-middle">{t(locale, "nuance_unchecked")}</StatusBadge>}
          </Row>
        )}
        {text?.origin && text.origin !== "unknown" && <Row label={t(locale, "term_origin")}><span lang={untranslated}>{text.origin}</span></Row>}
        {gens.length > 0 && <Row label={t(locale, "term_used_by")}>{list(gens.map((g) => labels.generation[g]))}</Row>}
        {e.regions.length > 0 && <Row label={t(locale, "pg_ex_regions")}>{list(e.regions.map((r) => regionLabel(locale, r)))}</Row>}
        {e.notes.length > 0 && <Row label={t(locale, "pg_ex_for_me")}>{e.notes.join(" ")}</Row>}
        {latest && (
          <Row label={t(locale, "pg_ex_sources")}>
            <span className="flex flex-wrap gap-x-2 text-[13px] text-steel">
              <span>{labels.evidenceKind[latest.kind]}</span>
              <span>{sourceName(locale, latest.source_domain)}</span>
              <span className="tabular-nums">{fmtDate(latest.observed_at)}</span>
            </span>
            {latest.title && (
              <a href={latest.url} target="_blank" rel="noreferrer noopener" className="block text-[13px] text-link-blue hover:underline">{latest.title}</a>
            )}
            {record.evidences.length > 1 && (
              <Link href={`/dictionary/${id}#refs`} className="block text-[13px] text-link-blue hover:underline">
                {t(locale, "pg_ex_all_sources").replace("{n}", String(record.evidences.length))}
              </Link>
            )}
          </Row>
        )}
      </dl>
      <Link href={`/dictionary/${id}`} className="mt-2 inline-block text-[14px] text-link-blue hover:underline">
        {t(locale, "home_more")}<span className="sr-only">: {term.canonical}</span>
      </Link>
    </li>
  );
}

/** 해석 결과 본문: 원문·쉽게 풀어 쓰면 두 행과 찾은 표현 목록. */
export function ExplainCards({ result, locale, original }: { result: ExplainResult; locale: Locale; original?: string }) {
  return (
    <div className="space-y-5">
      {(original || result.plain) && (
        <dl className="border-b border-hairline pb-4">
          {original && (
            <div className="grid gap-x-4 gap-y-1 py-1.5 sm:grid-cols-[112px_minmax(0,1fr)]">
              <dt className="text-[13px] font-medium text-steel">{t(locale, "pg_ex_original")}</dt>
              <dd className="text-[15px] leading-[1.6] whitespace-pre-wrap text-ink">{original}</dd>
            </div>
          )}
          {result.plain && (
            <div className="grid gap-x-4 gap-y-1 py-1.5 sm:grid-cols-[112px_minmax(0,1fr)]">
              <dt className="text-[13px] font-medium text-steel">{t(locale, "home_plain")}</dt>
              <dd className="text-[16px] leading-[1.6] text-ink">{result.plain}</dd>
            </div>
          )}
        </dl>
      )}
      {result.greeting && <p className="text-[14px] text-charcoal">{result.greeting}</p>}
      <ul className="divide-y divide-hairline">
        {result.items.map((e) => <ExpressionRow key={e.record.term.term_id} e={e} locale={locale} />)}
      </ul>
    </div>
  );
}
