import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDate, sourceName } from "@/lib/labels";
import type { Provenance } from "@/lib/types";

/* 사전 항목의 '이렇게 만들었어요' — 이 뜻을 누가 쓰고 무엇으로 확인했나. 배포된 화면에서 수집 쪽 AI 가 하는 일이 보이지 않았다(10-05).
   기록에 있는 단계만 차례대로 보인다. 내부 용어(게이트·확신도·판 수), 검수자 이름, 모델 이름은 쓰지 않는다(모델 기록은 관리 화면). */
export function TermProvenance({ p, locale }: { p: Provenance; locale: Locale }) {
  const say = (key: StringKey, vars: Record<string, string | number> = {}) =>
    Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), t(locale, key));
  const steps: string[] = [];
  if (p.evidences > 0) steps.push(say("prov_collect", { n: p.evidences }));
  if (p.rewritten) steps.push(say("prov_rewritten"));
  else if (p.drafted_by === "person") steps.push(say("prov_draft_person"));
  else if (p.drafted_by) steps.push(say("prov_draft_ai"));
  if (p.checked === "person") steps.push(say("prov_check_person") + (p.checked_at ? ` (${fmtDate(p.checked_at)})` : ""));
  else if (p.checked === "rules") steps.push(p.reference ? say("prov_check_rules_doc", { doc: sourceName(locale, p.reference) }) : say("prov_check_rules"));
  else steps.push(say("prov_check_pending"));
  if (p.audit && !p.rewritten) steps.push(say(p.audit === "ok" ? "prov_audit_ok" : "prov_audit_fix"));
  steps.push(p.risk_sentences > 0 ? say("prov_risk", { n: p.risk_sentences }) : say("prov_risk_none"));
  if (p.translated_by) steps.push(p.translated_by === "person" ? say("prov_translated_person") : say("prov_translated_ai"));
  return (
    <div className="space-y-2">
      <ol className="list-decimal space-y-1 pl-5 text-[14px] leading-[1.6] text-charcoal">
        {steps.map((s) => <li key={s}>{s}</li>)}
      </ol>
      <p className="text-[13px] text-steel">{say("prov_note")}</p>
    </div>
  );
}
