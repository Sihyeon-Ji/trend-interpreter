import type { Metadata } from "next";
import { ReviewTable, type ReviewKind } from "@/components/review-table";
import { getReviewQueue, getReviewStats, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "adm_tab_review")} — ${t(locale, "adm_title")} — ${t(locale, "site")}` };
}

export default async function AdminReviewPage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const [items, stats] = await Promise.all([getReviewQueue(), getReviewStats().catch(() => null)]);   // 요약 숫자만 실패하면 그 칸에 '—'
  const kind: ReviewKind | "all" = sp.kind === "new" || sp.kind === "changed" || sp.kind === "trend" ? sp.kind : "all";
  const total = stats ? stats.verified_auto + stats.verified_human + stats.needs_review + stats.rejected : 0;
  const n = (v: number | undefined) => (stats && v != null ? t(locale, "adm_count").replace("{n}", v.toLocaleString("en-US")) : "—");
  const cells: [string, string, string?][] = [
    [t(locale, "admin_ratio"), n(stats?.verified_auto), stats && total ? `${Math.round((stats.verified_auto / total) * 100)}%` : undefined],
    [t(locale, "admin_ratio_manual"), n(stats?.verified_human)],
    [t(locale, "admin_ratio_pending"), n(stats?.needs_review)],
    [t(locale, "admin_ratio_rejected"), n(stats?.rejected)],
  ];
  return (
    <section aria-labelledby="adm-review-h" className="space-y-5">
      <h2 id="adm-review-h" className="sr-only">{t(locale, "adm_tab_review")}</h2>
      <p className="text-[15px] text-charcoal">{t(locale, "adm_review_intro")}</p>
      {/* 대부분이 자동으로 실리고 예외만 사람이 본다는 것을 한눈에 — 라벨 칸 줄, 칸 사이 hairline */}
      <dl aria-label={t(locale, "adm_summary_label")} className="grid grid-cols-2 gap-y-4 sm:flex sm:divide-x sm:divide-hairline">
        {cells.map(([label, value, pct]) => (
          <div key={label} className="space-y-1 sm:px-6 sm:first:pl-0">
            <dt className="text-[13px] text-steel">{label}</dt>
            <dd className="text-[18px] font-semibold tabular-nums text-ink">{value}{pct && <span className="ml-1.5 text-[13px] font-normal text-steel">({pct})</span>}</dd>
          </div>
        ))}
      </dl>
      <ReviewTable items={items} live={!isSampleMode} locale={locale} kind={kind} />
    </section>
  );
}
