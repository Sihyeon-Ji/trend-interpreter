/** 항목 화면 뼈대 — 머리와 본문 줄 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="fr-skel h-4 w-32" />
      <div className="mt-3 border-t border-[var(--fr-ink)] pt-6">
        <div className="fr-skel h-4 w-16" />
        <div className="fr-skel mt-3 h-14 w-[min(420px,70%)]" />
        <div className="fr-skel mt-4 h-5 w-[min(560px,90%)]" />
        <div className="fr-skel mt-6 h-[120px] w-full" />
      </div>
      <div className="fr-entry">
        <div className="grid gap-3">{Array.from({ length: 6 }, (_, i) => <div key={i} className="fr-skel h-5" style={{ width: `${90 - i * 8}%` }} />)}</div>
        <div className="fr-skel h-56" />
      </div>
    </div>
  );
}
