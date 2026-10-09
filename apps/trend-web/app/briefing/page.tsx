import type { Metadata } from "next";
import Link from "next/link";
import { BriefingActions } from "@/components/briefing-actions";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { RegionChips } from "@/components/region-chips";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { getBriefing, isSampleMode } from "@/lib/data";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { fmtDate, fmtDateTime, regionLabel, sourceName } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";
import type { Briefing, KeywordCard } from "@/lib/types";
import { glossFor } from "@/lib/gloss";

/* 트렌드 브리핑 — 고른 시장의 대시보드를 마케터가 들고 갈 한 장으로. 목록·건수는 대시보드 규칙(백엔드 pipeline/briefing.py),
   요약 문장만 모델이 쓰고 없으면 규칙 문장. 지역은 주소에만 둔다(링크 복사 = 같은 보고서). 브라우저 인쇄로 PDF 저장. */
const KNOWN = [...TARGET_REGIONS, "GLOBAL"];
const one = (v: string | string[] | undefined) => [v].flat().filter(Boolean).join(",");
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);

function ruleSummary(b: Briefing, locale: Locale, names: string): string {
  const c = b.counts;
  const parts = [fill(t(locale, "brief_rule_1"), { regions: names, rising: c.rising, use_now: c.use_now })];
  if (b.use_now.length) parts.push(fill(t(locale, "brief_rule_top"), { top: b.use_now.slice(0, 3).map((x) => x.canonical).join(", ") }));
  parts.push(fill(t(locale, "brief_rule_2"), { careful: c.careful, fading: c.fading }));
  if (c.undecided) parts.push(fill(t(locale, "brief_rule_3"), { undecided: c.undecided }));
  return parts.join(" ");
}

type Kind = "use_now" | "careful" | "fading";

function Section({ kind, cards, total, locale, regions }: { kind: Kind; cards: KeywordCard[]; total: number; locale: Locale; regions: string[] }) {
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  return (
    <section aria-labelledby={`brief-${kind}`} className="break-inside-avoid space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h2 id={`brief-${kind}`} className="text-[16px] font-semibold text-ink">
          {t(locale, `brief_${kind}` as StringKey)} <span className="tabular-nums text-steel">{total}</span>
        </h2>
        <p className="text-[13px] text-steel">{t(locale, `brief_${kind}_note` as StringKey)}</p>
      </div>
      {cards.length ? (
        <ul className="border-b border-hairline">
          {cards.map((c) => {
            const ev = c.evidences[0];
            return (
              <li key={c.term_id} className="grid gap-x-6 gap-y-1.5 border-t border-hairline py-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <div className="min-w-0">
                  <Link href={`/dictionary/${encodeURIComponent(c.term_id)}${q}`} lang={langTag(c.lang)} className="text-[15px] font-semibold text-ink hover:underline">
                    {c.canonical}
                  </Link>
                  <p className="mt-0.5 line-clamp-2 text-[14px] leading-[1.55] text-charcoal">{glossFor(c, locale)}</p>
                  {ev && (
                    <a href={ev.url} target="_blank" rel="noreferrer" className="mt-0.5 inline-block text-[12px] text-steel hover:underline">
                      {t(locale, "brief_sources")} · {sourceName(locale, ev.source_domain)} · {fmtDate(ev.observed_at)}
                    </a>
                  )}
                </div>
                <div className="flex flex-col items-start gap-1.5 sm:items-end">
                  <StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} />
                  {kind === "careful" && <RiskCell item={c} locale={locale} />}
                </div>
              </li>
            );
          })}
        </ul>
      ) : <p className="border-t border-hairline py-3 text-[14px] text-steel">{t(locale, "brief_none")}</p>}
      {total > cards.length && <p className="text-[13px] text-steel">{fill(t(locale, "brief_more"), { n: total - cards.length })}</p>}
    </section>
  );
}

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다 — 여러 화면이 사이트 이름 하나뿐이었다(10-04)
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "brief_title")} — ${t(locale, "site")}` };
}

export default async function BriefingPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const raw = one(sp.regions);
  const asked = raw && raw !== "all" ? raw.split(",").map((s) => s.trim().toUpperCase()) : [];
  const reader = raw ? {} : await getReader();     // 주소에 지역이 없으면 로그인한 사람의 나라, 익명은 전체 — 대시보드와 같다
  const picked = raw ? KNOWN.filter((r) => asked.includes(r)) : reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : [];

  let b: Briefing | null = null;
  try {
    b = await getBriefing(picked, locale);
  } catch {
    b = null;
  }
  const targets = picked.filter((r) => r !== "GLOBAL");
  const names = picked.length ? picked.map((r) => (r === "GLOBAL" ? t(locale, "dash_global") : regionLabel(locale, r))).join(", ") : t(locale, "dash_all");
  const dashHref = `/trends?regions=${picked.length ? picked.join(",") : "all"}`;
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "brief_title")} description={t(locale, "brief_intro")}
          meta={!b ? null : isSampleMode
            ? <StatusBadge tone="muted">{t(locale, "dash_sample_badge")}</StatusBadge>
            : <span>{t(locale, "brief_as_of")} <span className="tabular-nums text-charcoal">{fmtDateTime(b.collected_at ?? b.generated_at, locale)}</span></span>}
          actions={<BriefingActions locale={locale} />}>
          <div className="print:hidden"><RegionChips picked={picked} locale={locale} base="/briefing" /></div>
        </PageHeader>

        {!b ? (
          <StatePanel role="alert" action={<Link href={`/briefing${raw ? `?regions=${raw}` : ""}`} className="text-[14px] text-link-blue hover:underline">{t(locale, "brief_retry")}</Link>}>
            {t(locale, "brief_error")}
          </StatePanel>
        ) : (
          <article className="space-y-7">
            <div className="space-y-1 text-[13px] text-steel">
              <p><span className="font-medium text-charcoal">{t(locale, "brief_market")}</span> {names}</p>
              <p>{t(locale, "brief_period")} · {t(locale, "brief_as_of")} {fmtDateTime(b.collected_at ?? b.generated_at, locale)}</p>
            </div>
            <section aria-labelledby="brief-summary" className="rounded-md border border-hairline-strong p-4">
              <h2 id="brief-summary" className="text-[14px] font-semibold text-ink">{t(locale, "brief_summary")}</h2>
              <p className="mt-1.5 text-[15px] leading-[1.6] text-ink">{b.summary || ruleSummary(b, locale, names)}</p>
              <p className="mt-2 text-[12px] text-steel">{t(locale, b.summary ? "brief_summary_ai" : "brief_summary_rule")}</p>
            </section>
            <Section kind="use_now" cards={b.use_now} total={b.counts.use_now} locale={locale} regions={picked} />
            <Section kind="careful" cards={b.careful} total={b.counts.careful} locale={locale} regions={picked} />
            <Section kind="fading" cards={b.fading} total={b.counts.fading} locale={locale} regions={picked} />
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-[14px] print:hidden">
              <Link href={targets.length ? `/recommend?regions=${targets.join(",")}` : "/recommend"} className="text-link-blue hover:underline">{t(locale, "brief_to_kit")}</Link>
              <Link href={dashHref} className="text-link-blue hover:underline">{t(locale, "brief_to_dashboard")}</Link>
            </div>
            <p className="hidden text-[12px] text-steel print:block">{t(locale, "brief_printed_from")}</p>
          </article>
        )}
      </div>
    </PageShell>
  );
}
