import type { Metadata } from "next";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { getPipelineStages } from "@/lib/data";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDateTime, fmtInt } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { PipelineStage } from "@/lib/types";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "adm_tab_status")} — ${t(locale, "adm_title")} — ${t(locale, "site")}` };
}

type Run = NonNullable<PipelineStage["run_status"]>;
type Group = "collect" | "discover" | "research" | "build";
const GROUPS: Group[] = ["collect", "discover", "research", "build"];
// 번호 대신 네 묶음 — 실행 순서는 묶음 안에서 마지막 실행 시작 순으로 보인다(scripts/run_pipeline.py 순서와 같은 뜻)
const GROUP_OF: Record<string, Group> = {
  classify: "discover", spikes: "discover", candidates: "discover", spot: "discover", namu: "discover", hunt: "discover", interpret: "discover", discover: "discover",
  research: "research", crosscheck: "research", track: "research", risk: "research", naver: "research", verify: "research",
  translate: "build", topics: "build", board: "build", dashboard: "build", fit: "build",
};
const groupOf = (key: string): Group => (key === "collect" || key.startsWith("collect.") ? "collect" : GROUP_OF[key] ?? "build");
const STAGE_KEY: Record<string, StringKey> = {
  "collect.youtube": "adm_stage_collect_youtube", "collect.news": "adm_stage_collect_news", "collect.trends_rss": "adm_stage_collect_trends_rss",
  "collect.trends_bq": "adm_stage_collect_trends_bq", "collect.wikipedia": "adm_stage_collect_wikipedia", "collect.mentions": "adm_stage_collect_mentions",
  "collect.retention": "adm_stage_collect_retention", classify: "adm_stage_classify", spikes: "adm_stage_spikes", candidates: "adm_stage_candidates",
  spot: "adm_stage_spot", namu: "adm_stage_namu", hunt: "adm_stage_hunt", interpret: "adm_stage_interpret", research: "adm_stage_research", crosscheck: "adm_stage_crosscheck",
  track: "adm_stage_track", risk: "adm_stage_risk", naver: "adm_stage_naver", translate: "adm_stage_translate", topics: "adm_stage_topics",
  board: "adm_stage_board", dashboard: "adm_stage_dashboard", fit: "adm_stage_fit",
};
const stageName = (locale: Locale, s: PipelineStage) => (STAGE_KEY[s.key] ? t(locale, STAGE_KEY[s.key]) : s.label);
// 예전 모양(예시 데이터)은 status 만 있다: 0건은 처리 없음, 주의는 건너뜀으로 읽는다
const runOf = (s: PipelineStage): Run | null => (s.run_status !== undefined ? s.run_status : s.status === "ok" ? "ok" : s.status === "zero" ? "idle" : "skipped");
const RUN_KEY = { ok: "adm_st_ok", idle: "adm_st_idle", skipped: "adm_st_skipped", error: "adm_st_error" } as const;

/** 요청 때 한 번 재는 경과 시간(서버 화면) — 마지막 실행이 24시간보다 오래됐는지 */
function hoursSince(iso: string) {
  return (Date.now() - Date.parse(iso)) / 3_600_000;
}

function RunBadge({ run, locale }: { run: Run | null; locale: Locale }) {
  if (run === "ok") return <span className="text-[14px] text-charcoal">{t(locale, "adm_st_ok")}</span>;
  if (!run) return <StatusBadge tone="muted">{t(locale, "adm_st_not_run")}</StatusBadge>;
  return <StatusBadge tone={run === "error" ? "avoid" : run === "skipped" ? "caution" : "muted"}>{t(locale, RUN_KEY[run])}</StatusBadge>;
}

function Note({ s, run, locale }: { s: PipelineStage; run: Run | null; locale: Locale }) {
  if (!s.note) return null;
  // 오류 원문(예외 이름과 메시지)은 접어 둔다 — 운영자가 볼 때만 펼친다
  if (run === "error") {
    return (
      <details className="text-[13px] text-charcoal">
        <summary className="cursor-pointer text-link-blue">{t(locale, "adm_st_error_details")}</summary>
        <p className="mt-1 [overflow-wrap:anywhere]">{s.note}</p>
      </details>
    );
  }
  return <span className="text-[13px] text-charcoal">{s.note}</span>;
}

export default async function AdminStatusPage() {
  const [locale, stages] = await Promise.all([getLocale(), getPipelineStages()]);
  const finished = stages.map((s) => s.last_finished_at).filter((x): x is string => !!x).sort().at(-1) ?? null;
  // 한 번의 실행에는 번호가 없다 — 가장 늦게 끝난 시각 3시간 안에 시작한 단계들 가운데 가장 이른 시작을 그 실행의 시작으로 본다
  const started = finished
    ? stages.map((s) => s.last_started_at).filter((x): x is string => !!x && Date.parse(finished) - Date.parse(x) <= 3 * 3_600_000).sort()[0] ?? null
    : null;
  const failed = stages.filter((s) => runOf(s) === "error");
  const stale = !!finished && hoursSince(finished) > 24;
  const short = (iso: string | null | undefined) => {
    if (!iso) return "—";
    const full = fmtDateTime(iso, locale);
    return finished && full.slice(0, 10) === fmtDateTime(finished, locale).slice(0, 10) ? full.slice(11) : full.slice(5);
  };
  const byGroup = GROUPS.map((g) => [g, stages.filter((s) => groupOf(s.key) === g)
    .sort((a, b) => (a.last_started_at ?? "9").localeCompare(b.last_started_at ?? "9"))] as const).filter(([, l]) => l.length);
  const anyRun = stages.some((s) => s.last_started_at || s.run_status === undefined);   // 예시 데이터는 시각 없이 상태만 있다
  const summary: [string, string][] = [
    [t(locale, "adm_st_started"), started ? fmtDateTime(started, locale) : "—"],
    [t(locale, "adm_st_finished"), short(finished)],
    [t(locale, "adm_st_failed"), String(failed.length)],
  ];

  return (
    <section aria-labelledby="adm-status-h" className="space-y-5">
      <h2 id="adm-status-h" className="sr-only">{t(locale, "adm_tab_status")}</h2>
      <p className="text-[15px] text-charcoal">{t(locale, "adm_status_intro")}</p>
      {!anyRun ? <StatePanel>{t(locale, "adm_st_none")}</StatePanel> : (
        <>
          <dl aria-label={t(locale, "adm_st_summary_label")} className="grid grid-cols-2 gap-y-4 sm:flex sm:divide-x sm:divide-hairline">
            {summary.map(([label, value]) => (
              <div key={label} className="space-y-1 sm:px-6 sm:first:pl-0">
                <dt className="text-[13px] text-steel">{label}</dt>
                <dd className="text-[18px] font-semibold tabular-nums text-ink">{value}</dd>
              </div>
            ))}
          </dl>
          {failed.length > 0 && (
            <p role="alert" className="rounded-md border border-avoid-line px-4 py-3 text-[14px] text-avoid">
              {t(locale, "adm_st_failed_alert").replace("{steps}", failed.map((s) => stageName(locale, s)).join(", "))}
            </p>
          )}
          {stale && <p role="alert" className="rounded-md border border-caution-line px-4 py-3 text-[14px] text-caution">{t(locale, "adm_st_stale")}</p>}

          {/* 768px 이상: 묶음별 tbody 표 */}
          <table className="hidden w-full table-fixed text-left text-[14px] md:table">
            <colgroup><col className="w-[200px]" /><col className="w-[120px]" /><col className="w-[110px]" /><col className="w-[110px]" /><col /></colgroup>
            <thead className="border-b border-hairline bg-surface text-[13px] text-steel">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">{t(locale, "adm_st_col_step")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t(locale, "adm_st_col_last")}</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">{t(locale, "adm_st_col_count")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t(locale, "adm_st_col_status")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t(locale, "adm_st_col_note")}</th>
              </tr>
            </thead>
            {byGroup.map(([g, list]) => (
              <tbody key={g} className="border-b border-hairline">
                <tr className="bg-surface"><th scope="rowgroup" colSpan={5} className="px-3 py-1.5 text-[13px] font-semibold text-ink">{t(locale, `adm_grp_${g}`)}</th></tr>
                {list.map((s) => {
                  const run = runOf(s);
                  return (
                    <tr key={s.key} className="border-t border-hairline align-top">
                      <th scope="row" className="px-3 py-2.5 font-normal text-ink">{stageName(locale, s)}</th>
                      <td className="px-3 py-2.5 tabular-nums whitespace-nowrap text-charcoal">{short(s.last_started_at)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums whitespace-nowrap text-ink">{fmtInt(s.count_24h)}</td>
                      <td className="px-3 py-2.5"><RunBadge run={run} locale={locale} /></td>
                      <td className="px-3 py-2.5 [overflow-wrap:break-word]"><Note s={s} run={run} locale={locale} /></td>
                    </tr>
                  );
                })}
              </tbody>
            ))}
          </table>

          {/* 휴대폰: 묶음 제목 아래 단계마다 세 줄 */}
          <div className="space-y-4 md:hidden">
            {byGroup.map(([g, list]) => (
              <section key={g} aria-labelledby={`st-${g}`}>
                <h3 id={`st-${g}`} className="bg-surface px-3 py-1.5 text-[13px] font-semibold text-ink">{t(locale, `adm_grp_${g}`)}</h3>
                <ul className="divide-y divide-hairline border-b border-hairline">
                  {list.map((s) => {
                    const run = runOf(s);
                    return (
                      <li key={s.key} className="space-y-1 px-3 py-2.5">
                        <div className="flex items-center justify-between gap-3"><span className="text-[14px] text-ink">{stageName(locale, s)}</span><RunBadge run={run} locale={locale} /></div>
                        <div className="flex justify-between gap-3 text-[13px] text-steel">
                          <span className="whitespace-nowrap">{t(locale, "adm_st_col_last")} <span className="tabular-nums text-charcoal">{short(s.last_started_at)}</span></span>
                          <span className="whitespace-nowrap">{t(locale, "adm_st_col_count")} <span className="tabular-nums text-charcoal">{fmtInt(s.count_24h)}</span></span>
                        </div>
                        <Note s={s} run={run} locale={locale} />
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
          <p className="text-[13px] text-steel">{t(locale, "adm_st_legend")}</p>
        </>
      )}
    </section>
  );
}
