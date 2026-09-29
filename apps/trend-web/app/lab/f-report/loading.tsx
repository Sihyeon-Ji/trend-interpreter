/** 리포트 홈 뼈대 — 머리·타일 셋·행 여덟 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="fr-skel h-9 w-[min(560px,80%)]" />
      <div className="mt-4 flex flex-wrap gap-2">{Array.from({ length: 6 }, (_, i) => <div key={i} className="fr-skel h-[34px] w-24 rounded-full" />)}</div>
      <div className="fr-since" style={{ visibility: "hidden" }}>&nbsp;</div>
      <div className="fr-section-head"><div className="fr-skel h-5 w-28" /></div>
      <div className="fr-tiles">{Array.from({ length: 3 }, (_, i) => <div key={i} className="fr-skel min-h-[236px] rounded-[14px]" />)}</div>
      <div className="fr-board">
        <div>
          <div className="fr-skel h-10 w-full" />
          <div className="mt-3 grid gap-3">{Array.from({ length: 8 }, (_, i) => <div key={i} className="fr-skel h-[50px] w-full" />)}</div>
        </div>
        <div className="fr-preview"><div className="fr-skel h-6 w-24" /><div className="fr-skel mt-3 h-9 w-48" /><div className="fr-skel mt-4 h-20 w-full" /></div>
      </div>
    </div>
  );
}
