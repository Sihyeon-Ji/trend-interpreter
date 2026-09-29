/** 리포트 홈 뼈대 — 머리·칩·띠·타일 셋·행 여덟 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="fr-skel h-9 w-[min(560px,80%)]" />
      <div className="mt-[18px] flex flex-wrap gap-[6px]">{Array.from({ length: 7 }, (_, i) => <div key={i} className="fr-skel h-10 w-24" />)}</div>
      <div className="fr-since" aria-hidden><span className="fr-since-when">&nbsp;</span></div>
      <div className="fr-section-head"><div className="fr-skel h-5 w-28" /></div>
      <div className="fr-tiles">{Array.from({ length: 3 }, (_, i) => <div key={i} className="fr-skel min-h-[250px]" />)}</div>
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
