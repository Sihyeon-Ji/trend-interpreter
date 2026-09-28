"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Level = "none" | "caution" | "avoid";
export interface RiskRow { term_id: string; canonical: string; level: Level | null; human: Level | null; reasons: string[] }

export const RISK_LABEL: Record<Level, string> = { none: "문제 없음", caution: "주의", avoid: "사용 자제" };

/** 리스크 수준을 사람이 바꾼다. 사람의 결정은 규칙보다 우선하고, '규칙대로' 를 누르면 지워진다.
 *  뜻 검수와 같이 같은 사이트의 /api/review 를 거친다 — 로그인 확인과 쓰기 토큰이 거기 있다. */
export function RiskTable({ rows, live = false }: { rows: RiskRow[]; live?: boolean }) {
  const [human, setHuman] = useState<Record<string, Level | null>>(Object.fromEntries(rows.map((r) => [r.term_id, r.human])));
  const [error, setError] = useState<string | null>(null);
  const decide = async (termId: string, level: Level | null) => {
    const before = human[termId];
    setHuman({ ...human, [termId]: level });
    if (!live) return;
    try {
      const res = await fetch(`/api/review/${encodeURIComponent(termId)}/risk`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ level }) });
      if (!res.ok) throw new Error(String(res.status));
    } catch (e) {
      setError(`서버에 기록하지 못했습니다 (${(e as Error).message}). 다시 시도해 주세요.`);
      setHuman((prev) => ({ ...prev, [termId]: before }));
    }
  };
  return (
    <div className="overflow-x-auto">
      {error && <p className="mb-2 text-[13px] text-error">{error}</p>}
      <table className="w-full min-w-[820px] text-left text-[14px]">
        <thead className="border-b border-hairline text-[13px] font-medium text-steel whitespace-nowrap">
          <tr>
            <th className="py-2 pr-4">용어</th>
            <th className="py-2 pr-4">지금 수준</th>
            <th className="py-2 pr-4">규칙이 본 근거</th>
            <th className="py-2">바꾸기</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline-soft align-top">
          {rows.map((r) => {
            const h = human[r.term_id];
            const shown = h ?? r.level;
            return (
              <tr key={r.term_id}>
                <td className="py-3 pr-4">
                  <Link href={`/dictionary/${r.term_id}`} className="font-semibold text-ink hover:underline">{r.canonical}</Link>
                </td>
                <td className="py-3 pr-4 whitespace-nowrap text-charcoal">
                  {shown ? RISK_LABEL[shown] : "판단 보류"}
                  {h && <div className="text-[13px] text-steel">검수자가 정함</div>}
                </td>
                <td className="max-w-[380px] py-3 pr-4 text-charcoal">
                  <ul className="list-disc space-y-0.5 pl-4">{r.reasons.filter((x) => x !== "검수자가 정한 수준").slice(0, 3).map((x) => <li key={x}>{x}</li>)}</ul>
                </td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {(["none", "caution", "avoid"] as Level[]).map((l) => (
                      <Button key={l} size="sm" variant={h === l ? "default" : "outline"}
                        className={cn("rounded-lg px-3", h !== l && "border-hairline-strong shadow-none")} onClick={() => decide(r.term_id, l)}>
                        {RISK_LABEL[l]}
                      </Button>
                    ))}
                    {h && <Button size="sm" variant="ghost" className="rounded-lg px-3 text-steel" onClick={() => decide(r.term_id, null)}>규칙대로</Button>}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
