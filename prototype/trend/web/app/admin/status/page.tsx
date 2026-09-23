import { getPipelineStages } from "@/lib/data";
import { fmtInt } from "@/lib/labels";

const STATUS: Record<"ok" | "warn" | "zero", string> = { ok: "정상", warn: "주의", zero: "0건" };

export default async function AdminStatusPage() {
  const stages = await getPipelineStages();
  return (
    <section className="space-y-4">
      <p className="text-[15px] text-charcoal">최근 24시간 처리량입니다. 파이프라인은 6시간마다 실행됩니다.</p>
      <table className="w-full max-w-[720px] text-left text-[14px]">
        <thead className="border-b border-hairline text-[13px] font-medium text-steel">
          <tr><th className="whitespace-nowrap py-2 pr-4">단계</th><th className="whitespace-nowrap py-2 pr-4 text-right">건수</th><th className="whitespace-nowrap py-2 pr-4">상태</th><th className="whitespace-nowrap py-2">비고</th></tr>
        </thead>
        <tbody className="divide-y divide-hairline-soft">
          {stages.map((s, i) => (
            <tr key={s.key}>
              <td className="whitespace-nowrap py-2.5 pr-4 text-ink">{i + 1}. {s.label}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-ink whitespace-nowrap">{fmtInt(s.count_24h)}</td>
              <td className={`whitespace-nowrap py-2.5 pr-4 ${s.status === "ok" ? "text-charcoal" : "font-medium text-error"}`}>{STATUS[s.status]}</td>
              <td className="py-2.5 text-charcoal">{s.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[13px] text-steel">어느 단계든 건수가 0이 되면 상태가 바뀝니다.</p>
    </section>
  );
}
