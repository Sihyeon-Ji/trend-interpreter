/** 항목 화면 뼈대 — 머리 타일과 본문 줄 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="fr-skel h-4 w-32" />
      <div className="fr-skel mt-4 min-h-[300px] rounded-[18px]" />
      <div className="fr-entry">
        <div className="grid gap-3">{Array.from({ length: 6 }, (_, i) => <div key={i} className="fr-skel h-5 w-full" style={{ width: `${90 - i * 8}%` }} />)}</div>
        <div className="fr-skel h-56 rounded-[14px]" />
      </div>
    </div>
  );
}
