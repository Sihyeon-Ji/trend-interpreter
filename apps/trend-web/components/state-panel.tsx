/* 빈 목록·불러오기 실패를 표 자리에 알린다 — 무엇을 하면 되는지 한 문장과 동작 하나(docs/트렌드/디자인-개편.md 원칙 7). 왼쪽 정렬. */
export function StatePanel({ children, action, role }: { children: React.ReactNode; action?: React.ReactNode; role?: "alert" | "status" }) {
  return (
    <div role={role} className="rounded-lg border border-hairline px-6 py-6 text-[14px] leading-[1.6] text-charcoal">
      <p>{children}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
