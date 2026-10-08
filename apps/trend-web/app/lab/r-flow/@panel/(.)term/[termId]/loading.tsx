/* 패널이 먼저 열리고 내용은 도착하면 채운다 — 자리를 최종 높이로 잡아 내용이 들어올 때 덜 흔들리게 */
export default function PanelLoading() {
  return (
    <div className="rf-term" aria-busy="true">
      <span className="rf-skel" style={{ width: "46%", height: 46, borderRadius: 8 }} />
      <span className="rf-skel" style={{ width: "72%", height: 14, marginTop: 18 }} />
      <span className="rf-skel" style={{ width: "100%", height: 96, marginTop: 26, borderRadius: 10 }} />
      <span className="rf-skel" style={{ width: "100%", height: 48, marginTop: 18 }} />
      <span className="rf-skel" style={{ width: "88%", height: 14, marginTop: 28 }} />
      <span className="rf-skel" style={{ width: "80%", height: 14, marginTop: 10 }} />
      <span className="rf-skel" style={{ width: "64%", height: 14, marginTop: 10 }} />
    </div>
  );
}
