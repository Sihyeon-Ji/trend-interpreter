/* 불러오는 동안 — 제호 자리와 표지 자리만 비워 둔다. 언어는 아직 모르므로 두 말을 같이 적는다. */
export default function Loading() {
  return (
    <div className="fe-wrap fe-state" role="status" aria-live="polite">
      <div className="fe-skeleton" style={{ height: 24, width: 200 }} />
      <div className="fe-skeleton" style={{ height: 320, marginTop: 40 }} />
      <p className="sr-only">이번 호를 불러오는 중입니다 / Loading this issue</p>
    </div>
  );
}
