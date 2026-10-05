import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDate, sourceName } from "@/lib/labels";
import type { RiskBreakdown } from "@/lib/types";

const RISK_KEYS = ["none", "hate", "mockery", "gender", "politics", "sexual"] as const;

/* 사전 항목의 '이 판정의 근거 문장'(Plan 14 0단계) — 리스크 판정이 본 쓰인 문장마다 붙은 뉘앙스·위험 유형. 이용자 화면이라 모델 이름·문턱 숫자는
   쓰지 않는다(그건 관리 화면 '모델 기록'). 기사·쇼츠·문서만 문장을 보이고 커뮤니티·SNS 글은 건수로만 적는다(ADR 0003). */
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
            <table className="w-full min-w-[480px] text-left text-[13px]">
              <thead className="text-steel">
                <tr className="border-b border-hairline">
                  <th className="py-2 pr-3 font-medium">{t(locale, "rs_th_sentence")}</th>
                  <th className="py-2 pr-3 font-medium whitespace-nowrap">{t(locale, "rs_th_tone")}</th>
                  <th className="py-2 font-medium whitespace-nowrap">{t(locale, "rs_th_risk")}</th>
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
                    <td className={`py-2 align-top whitespace-nowrap ${s.on_topic && s.risk !== "none" ? "font-medium text-ink" : ""}`}>{s.on_topic ? riskLabel(s.risk) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-[13px] leading-[1.6] text-steel">
          {t(locale, "rs_rule")}
        </p>
      </div>
    </details>
  );
}
