"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { CREATED_BY, fmtDate } from "@/lib/labels";
import type { ReviewItem } from "@/lib/types";

type Decision = "approved" | "held" | "rejected";
const DECISION: Record<Decision, string> = { approved: "승인함", held: "보류함 — 근거 보강 요청", rejected: "제외함" };

export function ReviewTable({ items, live = false }: { items: ReviewItem[]; live?: boolean }) {
  const [decided, setDecided] = useState<Record<string, Decision>>({});
  const [error, setError] = useState<string | null>(null);
  // live(api 모드)면 결정을 서버에 기록한다: 승인 → verified_human, 제외 → rejected, 보류 → 서버 변경 없음.
  // 백엔드를 직접 부르지 않고 같은 사이트의 /api/review 를 거친다 — 로그인 확인과 쓰기 토큰이 거기 있다.
  const decide = async (id: string, termId: string, d: Decision) => {
    setDecided({ ...decided, [id]: d });
    if (!live || d === "held") return;
    try {
      const res = await fetch(`/api/review/${encodeURIComponent(termId)}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ decision: d === "approved" ? "approve" : "reject" }) });
      if (!res.ok) throw new Error(String(res.status));
    } catch (e) {
      setError(`서버에 기록하지 못했습니다 (${(e as Error).message}). 다시 시도해 주세요.`);
      setDecided((prev) => { const next = { ...prev }; delete next[id]; return next; });
    }
  };
  return (
    <div className="overflow-x-auto">
      {error && <p className="mb-2 text-[13px] text-error">{error}</p>}
      <table className="w-full min-w-[820px] text-left text-[14px]">
        <thead className="border-b border-hairline text-[13px] font-medium text-steel whitespace-nowrap">
          <tr>
            <th className="py-2 pr-4">용어</th>
            <th className="py-2 pr-4">제안된 뜻</th>
            <th className="py-2 pr-4">확인이 필요한 이유</th>
            <th className="py-2 pr-4">근거</th>
            <th className="py-2 pr-4">등록</th>
            <th className="py-2">결정</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline-soft align-top">
          {items.map((it) => {
            const id = it.proposed.meaning_id;
            const d = decided[id];
            return (
              <tr key={id}>
                <td className="py-3 pr-4">
                  <Link href={`/dictionary/${it.term_id}`} className="font-semibold text-ink hover:underline">{it.canonical}</Link>
                  <div className="text-[13px] text-steel">{it.proposed.version}판 · {CREATED_BY[it.proposed.created_by ?? ""] ?? it.proposed.created_by}</div>
                </td>
                <td className="max-w-[300px] py-3 pr-4 text-charcoal">{it.proposed.definition}</td>
                <td className="max-w-[260px] py-3 pr-4 text-charcoal">
                  <ul className="list-disc space-y-0.5 pl-4">{it.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                </td>
                <td className="py-3 pr-4 tabular-nums text-charcoal">{it.evidence_count}건</td>
                <td className="py-3 pr-4 tabular-nums text-charcoal">{fmtDate(it.queued_at)}</td>
                <td className="py-3">
                  {d ? (
                    <span className="text-[13px] text-charcoal">{DECISION[d]}</span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      <Button size="sm" className="rounded-lg px-3" onClick={() => decide(id, it.term_id, "approved")}>승인</Button>
                      <Button size="sm" variant="outline" className="rounded-lg border-hairline-strong px-3 shadow-none" onClick={() => decide(id, it.term_id, "held")}>보류</Button>
                      <Button size="sm" variant="ghost" className="rounded-lg px-3 text-steel" onClick={() => decide(id, it.term_id, "rejected")}>제외</Button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
