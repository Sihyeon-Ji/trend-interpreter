import Link from "next/link";
import { cookies } from "next/headers";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { AdminNav } from "@/components/admin-nav";
import { getMeta, getPipelineStages, getReviewStats } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/* 관리 머리 — 세 탭 공통. 로그아웃은 내 설정(/me)에 있다. 숫자를 못 읽어도 머리와 탭은 그린다(목록 실패는 error.tsx 가 알린다). */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  // 여기까지 왔다는 건 미들웨어를 통과했다는 뜻이다. 이름은 누가 결정을 남기는지 보여 주려고 읽는다.
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  const [stats, stages, meta] = await Promise.all([getReviewStats().catch(() => null), getPipelineStages().catch(() => null), getMeta()]);
  const failed = stages?.filter((s) => s.run_status === "error").length ?? 0;
  const lastRun = meta?.last_run ?? stages?.map((s) => s.last_finished_at).filter((x): x is string => !!x).sort().at(-1) ?? null;
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "adm_title")} description={t(locale, "adm_intro")} divider={false}
          meta={
            <>
              {session && <span>{t(locale, "adm_recorded_as").replace("{name}", session.user)}</span>}
              {lastRun && <span className="tabular-nums">{t(locale, "adm_last_run")} {fmtDateTime(lastRun, locale)}</span>}
              {failed > 0 && <Link href="/admin/status" className="text-link-blue hover:underline">{t(locale, "adm_failed_steps").replace("{n}", String(failed))}</Link>}
            </>
          }>
          <AdminNav label={t(locale, "adm_tabs_label")} items={[
            { id: "/admin", href: "/admin", label: t(locale, "adm_tab_review"), count: stats?.needs_review },
            { id: "/admin/risk", href: "/admin/risk", label: t(locale, "adm_tab_risk") },
            { id: "/admin/status", href: "/admin/status", label: t(locale, "adm_tab_status") },
          ]} />
        </PageHeader>
        {children}
      </div>
    </PageShell>
  );
}
