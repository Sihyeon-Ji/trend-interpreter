import type { Metadata } from "next";
import Link from "next/link";
import { ListTabs } from "@/components/list-tabs";
import { RiskTable, type RiskRow } from "@/components/risk-table";
import { getRiskRecords, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

const ORDER = { avoid: 0, caution: 1 } as const;
type View = "flagged" | "human" | "all";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "adm_tab_risk")} — ${t(locale, "adm_title")} — ${t(locale, "site")}` };
}

export default async function AdminRiskPage({ searchParams }: { searchParams: Promise<{ view?: string; all?: string }> }) {
  const [locale, records, sp] = await Promise.all([getLocale(), getRiskRecords(), searchParams]);
  // 기본은 규칙이 경고를 붙였거나 사람이 이미 정한 것. '전체' 는 사전에 오른 말 전부 — 규칙이 '특이 사항 없음'·'판단 보류' 로 둔 말도
  // 검수자가 주의·사용 자제로 올릴 수 있어야 한다(검토 3차: Plan 03 표본의 Tralalero Tralala 처럼 규칙이 놓친 것). 예전 ?all=1 은 전체로.
  const view: View = sp.view === "human" || sp.view === "all" ? sp.view : sp.all === "1" ? "all" : "flagged";
  const all: RiskRow[] = records
    .filter(({ term: t }) => t.status === "verified")
    .map(({ term: t }) => ({ term_id: t.term_id, canonical: t.canonical, lang: t.lang ?? null, rule: t.risk_rule_level ?? (t.risk_human ? null : t.risk_level ?? null), human: t.risk_human ?? null,
                             by: t.risk_decided_by ?? null, at: t.risk_decided_at ?? null, reasons: t.risk_reasons ?? [] }))
    .sort((a, b) => (ORDER[(a.human ?? a.rule) as keyof typeof ORDER] ?? 2) - (ORDER[(b.human ?? b.rule) as keyof typeof ORDER] ?? 2) || a.canonical.localeCompare(b.canonical));
  const lists: Record<View, RiskRow[]> = {
    flagged: all.filter((r) => r.human || r.rule === "avoid" || r.rule === "caution"),
    human: all.filter((r) => r.human),
    all,
  };
  const rows = lists[view];
  const tabs = (["flagged", "human", "all"] as const).map((id) => ({
    id, label: t(locale, id === "flagged" ? "adm_risk_flagged" : id === "human" ? "adm_risk_human" : "adm_risk_all"), count: lists[id].length,
    href: id === "flagged" ? "/admin/risk" : `/admin/risk?view=${id}`,
  }));
  const empty = view === "flagged" ? "adm_risk_empty_flagged" : view === "human" ? "adm_risk_empty_human" : "adm_risk_empty_all";
  return (
    <section aria-labelledby="adm-risk-h" className="space-y-4">
      <h2 id="adm-risk-h" className="sr-only">{t(locale, "adm_tab_risk")}</h2>
      <p className="text-[15px] text-charcoal">{t(locale, "adm_risk_intro")}</p>
      <ListTabs items={tabs} current={view} label={t(locale, "adm_risk_view_label")} />
      {/* 목록이 바뀌면 표를 새로 그린다 — 표가 처음 받은 줄의 결정만 기억한다 */}
      {rows.length ? <RiskTable key={view} rows={rows} live={!isSampleMode} locale={locale} />
        : (
          <div className="rounded-lg border border-hairline px-6 py-6 text-[14px] leading-[1.6] text-charcoal">
            <p>{t(locale, empty)}</p>
            {view !== "all" && <Link href="/admin/risk?view=all" className="mt-3 inline-block text-link-blue hover:underline">{t(locale, "adm_risk_all")}</Link>}
          </div>
        )}
    </section>
  );
}
