import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDate, sourceName } from "@/lib/labels";
import type { Maker, RiskBreakdown } from "@/lib/types";

const MODEL: Record<Maker, string> = { gemma: "Gemma", gemini: "Gemini", person: "", unknown: "AI" };
const RISK_KEYS = ["none", "hate", "mockery", "gender", "politics", "sexual"] as const;

/* 사전 항목의 '근거 문장 분류 보기'(Plan 14 0단계) — 리스크 판정이 본 쓰인 문장마다 모델이 붙인 뉘앙스·위험 유형과 그 모델.
   기사·쇼츠·문서만 문장을 보이고 커뮤니티·SNS 글은 건수로만 적는다(ADR 0003). 판정 규칙의 문턱을 같이 적어 '왜 이 수준인지'가 보이게 한다. */
export function RiskSentences({ b, locale }: { b: RiskBreakdown; locale: Locale }) {
  const say = (key: StringKey, vars: Record<string, string | number> = {}) =>
    Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), t(locale, key));
  const riskLabel = (r: string) => (RISK_KEYS as readonly string[]).includes(r) ? t(locale, `risk_type_${r}` as StringKey) : r;
  const toneLabel = (p?: string | null) => (p ? t(locale, `tone_${p}` as StringKey) : "—");
  const total = b.sentences.length + b.community;
  return (
    <details className="group rounded-md border border-hairline">
      <summary className="flex min-h-11 cursor-pointer items-center px-3 text-[14px] font-medium text-link-blue hover:underline">
        {say("rs_toggle", { n: total })}
      </summary>
      <div className="space-y-3 border-t border-hairline px-3 py-3">
        <p className="text-[14px] leading-[1.6] text-charcoal">
          {say("rs_summary", { counted: b.counted, risky: b.risky, negative: b.negative, offtopic: b.offtopic })}
          {b.community > 0 && <> {say("rs_community", { n: b.community })}</>}
        </p>
        {b.sentences.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead className="text-steel">
                <tr className="border-b border-hairline">
                  <th className="py-2 pr-3 font-medium">{t(locale, "rs_th_sentence")}</th>
                  <th className="py-2 pr-3 font-medium whitespace-nowrap">{t(locale, "rs_th_tone")}</th>
                  <th className="py-2 pr-3 font-medium whitespace-nowrap">{t(locale, "rs_th_risk")}</th>
                  <th className="py-2 font-medium whitespace-nowrap">{t(locale, "rs_th_by")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {b.sentences.map((s) => (
                  <tr key={s.evidence_id} className={s.on_topic ? "" : "text-steel"}>
                    <td className="py-2 pr-3 align-top">
                      <span className={s.on_topic ? "text-ink" : "line-through decoration-hairline"}>{s.text}</span>
                      <span className="mt-0.5 block text-[12px] text-steel">
                        {s.url ? <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-link-blue hover:underline">{sourceName(locale, s.source_domain)}</a> : sourceName(locale, s.source_domain)}
                        {s.observed_at && <> · {fmtDate(s.observed_at)}</>}
                      </span>
                    </td>
                    <td className="py-2 pr-3 align-top whitespace-nowrap">{s.on_topic ? toneLabel(s.polarity) : t(locale, "rs_offtopic")}</td>
                    <td className={`py-2 pr-3 align-top whitespace-nowrap ${s.on_topic && s.risk !== "none" ? "font-medium text-ink" : ""}`}>{s.on_topic ? riskLabel(s.risk) : "—"}</td>
                    <td className="py-2 align-top whitespace-nowrap text-steel">{MODEL[s.by ?? "unknown"] || "AI"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-[13px] leading-[1.6] text-steel">
          {say("rs_rule", { min: b.min_labeled, caution: b.caution_risky, neg: Math.round(b.caution_negative * 100), avoid: b.avoid_risky })}
        </p>
      </div>
    </details>
  );
}
