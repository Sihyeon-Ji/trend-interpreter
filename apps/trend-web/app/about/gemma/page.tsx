import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { getGemmaUsage } from "@/lib/data";
import { t, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { fmtDate, fmtInt } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { GemmaStageId } from "@/lib/types";

/* Gemma가 하는 일(Plan 14 0단계) — 배치가 공개 사전 항목에 남긴 Gemma 결과를 단계별로 센다. 모델을 부르지 않고 기록만 읽는다.
   예시 모드는 건수를 지어내지 않는다(설명과 규칙만). 문장·모델 출력 원문은 이 화면에 없다 — 문장별 결과는 각 사전 항목에서 본다. */
const STAGES: GemmaStageId[] = ["risk", "translate", "fit", "audit", "crosscheck", "research"];

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "gemma_title")} — ${t(locale, "site")}` };
}

export default async function GemmaPage() {
  const [locale, usage] = await Promise.all([getLocale(), getGemmaUsage()]);
  const say = (key: StringKey, vars: Record<string, string | number> = {}) =>
    Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), t(locale, key));
  const byStage = new Map((usage?.stages ?? []).map((s) => [s.stage, s]));
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader title={t(locale, "gemma_title")} description={t(locale, "gemma_intro")} />

        {!usage && <p className="rounded-md border border-hairline bg-muted/40 px-4 py-3 text-[14px] text-charcoal">{t(locale, "gemma_sample_mode")}</p>}

        <section className="space-y-3">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-[14px]">
              <thead className="text-[13px] text-steel">
                <tr className="border-b border-hairline">
                  <th className="py-2 pr-4 font-medium">{t(locale, "gemma_th_stage")}</th>
                  <th className="py-2 pr-4 font-medium">{t(locale, "gemma_th_does")}</th>
                  {usage && <>
                    <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "gemma_th_count")}</th>
                    <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">{t(locale, "gemma_th_terms")}</th>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">{t(locale, "gemma_th_models")}</th>
                    <th className="py-2 font-medium whitespace-nowrap">{t(locale, "gemma_th_last")}</th>
                  </>}
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {STAGES.map((id) => {
                  const s = byStage.get(id);
                  const others = s ? [s.gemini ? say("gemma_gemini", { n: fmtInt(s.gemini) }) : "", s.other ? say("gemma_other", { n: fmtInt(s.other) }) : ""].filter(Boolean) : [];
                  return (
                    <tr key={id}>
                      <td className="py-3 pr-4 align-top font-medium whitespace-nowrap text-ink">{t(locale, `gemma_stage_${id}` as StringKey)}</td>
                      <td className="py-3 pr-4 align-top leading-[1.55] text-charcoal">{t(locale, `gemma_does_${id}` as StringKey)}</td>
                      {usage && <>
                        <td className="py-3 pr-4 text-right align-top tabular-nums whitespace-nowrap">
                          <span className="font-semibold text-ink">{fmtInt(s?.gemma ?? 0)}</span>
                          {others.length > 0 && <span className="block text-[12px] text-steel">{others.join(" · ")}</span>}
                        </td>
                        <td className="py-3 pr-4 text-right align-top tabular-nums">{fmtInt(s?.terms ?? 0)}</td>
                        <td className="py-3 pr-4 align-top text-[13px] text-charcoal">{s?.models.length ? s.models.join(", ") : "—"}</td>
                        <td className="py-3 align-top text-[13px] tabular-nums whitespace-nowrap text-charcoal">{fmtDate(s?.last_at)}</td>
                      </>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {usage && usage.samples.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-[18px] font-semibold text-ink">{t(locale, "gemma_samples")}</h2>
            <ul className="flex flex-wrap gap-2">
              {usage.samples.map((x) => (
                <li key={x.term_id}>
                  <Link href={`/dictionary/${encodeURIComponent(x.term_id)}#made`} lang={langTag(x.lang)}
                    className="inline-flex h-10 items-center rounded-md border border-hairline px-3 text-[14px] text-ink hover:border-ink">{x.canonical}</Link>
                </li>
              ))}
            </ul>
            <p className="text-[13px] text-steel">{t(locale, "gemma_samples_note")}</p>
          </section>
        )}

        <section className="space-y-3">
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "gemma_rules_title")}</h2>
          <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-[1.6] text-charcoal">
            {(["gemma_rule_1", "gemma_rule_2", "gemma_rule_3", "gemma_rule_4"] as const).map((k) => <li key={k}>{t(locale, k)}</li>)}
          </ul>
        </section>
      </div>
    </PageShell>
  );
}

