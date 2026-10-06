import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDate, fmtInt } from "@/lib/labels";
import type { GemmaStageId, GemmaUsage, ModelCalls } from "@/lib/types";

/* 관리 화면 '모델 기록'(Plan 14 0단계) — 공개 사전 항목에 단계별로 Gemma·Gemini 가 남긴 결과 수와 모델 이름.
   모델 이름·건수는 이용자 화면에 두지 않는다(내부 용어). 기록만 세고 모델을 부르지 않는다. */
const STAGES: GemmaStageId[] = ["risk", "translate", "fit", "audit", "crosscheck", "research"];

export function ModelUsageTable({ usage, locale }: { usage: GemmaUsage; locale: Locale }) {
  const say = (key: StringKey, vars: Record<string, string | number> = {}) =>
    Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), t(locale, key));
  const byStage = new Map(usage.stages.map((s) => [s.stage, s]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-[14px]">
        <thead className="text-[13px] text-steel">
          <tr className="border-b border-hairline">
            <th className="py-2 pr-4 font-medium">{t(locale, "gemma_th_stage")}</th>
            <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "gemma_th_count")}</th>
            <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "gemma_th_terms")}</th>
            <th className="py-2 pr-4 font-medium whitespace-nowrap">{t(locale, "gemma_th_models")}</th>
            <th className="py-2 font-medium whitespace-nowrap">{t(locale, "gemma_th_last")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {STAGES.map((id) => {
            const s = byStage.get(id);
            const others = s ? [s.gemini ? say("gemma_gemini", { n: fmtInt(s.gemini) }) : "", s.other ? say("gemma_other", { n: fmtInt(s.other) }) : ""].filter(Boolean) : [];
            return (
              <tr key={id}>
                <td className="py-3 pr-4 align-top font-medium whitespace-nowrap text-ink">{t(locale, `gemma_stage_${id}` as StringKey)}</td>
                <td className="py-3 pr-4 text-right align-top tabular-nums whitespace-nowrap">
                  <span className="font-semibold text-ink">{fmtInt(s?.gemma ?? 0)}</span>
                  {others.length > 0 && <span className="block text-[12px] text-steel">{others.join(" · ")}</span>}
                </td>
                <td className="py-3 pr-4 text-right align-top tabular-nums">{fmtInt(s?.terms ?? 0)}</td>
                <td className="py-3 pr-4 align-top text-[13px] text-charcoal">{s?.models.length ? s.models.join(", ") : "—"}</td>
                <td className="py-3 align-top text-[13px] tabular-nums whitespace-nowrap text-charcoal">{fmtDate(s?.last_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const secs = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${s.toFixed(s < 10 ? 1 : 0)}s`);

/* 같은 섹션의 두 번째 표 — 실행 기록(pipeline_runs.model_calls)의 단계별 모델 호출 수·시간. Gemma 를 쓴 줄은 표시를 따로 단다(Plan 14 0단계). */
export function ModelCallsTable({ calls, locale }: { calls: ModelCalls[]; locale: Locale }) {
  if (calls.length === 0) return <p className="text-[13px] text-steel">{t(locale, "adm_calls_empty")}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-[14px]">
        <thead className="text-[13px] text-steel">
          <tr className="border-b border-hairline">
            <th className="py-2 pr-4 font-medium">{t(locale, "adm_calls_th_stage")}</th>
            <th className="py-2 pr-4 font-medium">{t(locale, "adm_calls_th_model")}</th>
            <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "adm_calls_th_calls")}</th>
            <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "adm_calls_th_time")}</th>
            <th className="py-2 text-right font-medium whitespace-nowrap">{t(locale, "adm_calls_th_avg")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {calls.map((c) => (
            <tr key={`${c.stage}:${c.model}`}>
              <td className="py-3 pr-4 align-top font-medium whitespace-nowrap text-ink">{c.label}</td>
              <td className="py-3 pr-4 align-top text-[13px] text-charcoal">
                {c.model}
                {c.maker === "gemma" && <span className="ml-2 rounded-full bg-surface px-2 py-0.5 text-[12px] text-ink">Gemma</span>}
              </td>
              <td className="py-3 pr-4 text-right align-top tabular-nums">{fmtInt(c.calls)}</td>
              <td className="py-3 pr-4 text-right align-top tabular-nums whitespace-nowrap">{secs(c.seconds)}</td>
              <td className="py-3 text-right align-top tabular-nums whitespace-nowrap text-charcoal">{c.calls ? secs(c.seconds / c.calls) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
