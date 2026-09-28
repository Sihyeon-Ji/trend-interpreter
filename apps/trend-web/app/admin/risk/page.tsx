import { RiskTable, type RiskRow } from "@/components/risk-table";
import { getTermRecords, isSampleMode } from "@/lib/data";

const ORDER = { avoid: 0, caution: 1 } as const;

export default async function AdminRiskPage() {
  const records = await getTermRecords();
  // 규칙이 경고를 붙였거나 사람이 이미 정한 것만 본다. '문제 없음'·'판단 보류'는 사전 화면에서 확인한다.
  const rows: RiskRow[] = records
    .map(({ term: t }) => ({ term_id: t.term_id, canonical: t.canonical, rule: t.risk_rule_level ?? (t.risk_human ? null : t.risk_level ?? null), human: t.risk_human ?? null,
                             by: t.risk_decided_by ?? null, at: t.risk_decided_at ?? null, reasons: t.risk_reasons ?? [] }))
    .filter((r) => r.human || r.rule === "avoid" || r.rule === "caution")
    .sort((a, b) => (ORDER[(a.human ?? a.rule) as keyof typeof ORDER] ?? 2) - (ORDER[(b.human ?? b.rule) as keyof typeof ORDER] ?? 2) || a.canonical.localeCompare(b.canonical));
  return (
    <section className="space-y-4">
      <p className="text-[15px] text-charcoal">
        브랜드가 쓰기 전에 조심해야 할 표현입니다. 수준은 근거 문장을 보고 규칙이 정하고, 여기서 사람이 바꾸면 그 결정이 규칙보다 우선합니다.
        지금 <span className="font-medium text-ink">사용 자제 {rows.filter((r) => (r.human ?? r.rule) === "avoid").length}건</span>, 주의 {rows.filter((r) => (r.human ?? r.rule) === "caution").length}건입니다.
      </p>
      {rows.length ? <RiskTable rows={rows} live={!isSampleMode} /> : <p className="text-[14px] text-steel">경고가 붙은 표현이 아직 없습니다.</p>}
    </section>
  );
}
