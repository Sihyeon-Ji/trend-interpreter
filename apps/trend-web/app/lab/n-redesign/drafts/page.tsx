import type { Metadata } from "next";
import Link from "next/link";
import { DraftsBoard } from "@/components/lab/n-redesign/drafts-board";
import { BRIEF, TONES, market } from "@/lib/lab/n-redesign/data";

/* 초안 — 시장마다 고른 말·카피·확인·포스터·승인. 예시 데이터로 고정. */
export const metadata: Metadata = { title: "초안" };

export default function DraftsPage() {
  const tone = TONES.find((t) => t.id === BRIEF.tone)?.name;
  return (
    <div className="n-wrap">
      <div className="n-head" style={{ paddingBottom: 24 }}>
        <p className="n-crumb"><Link href="/lab/n-redesign">만들기</Link><span aria-hidden="true">/</span><span>초안</span></p>
        <h1 className="n-h1">{BRIEF.product}</h1>
        <p className="n-lead">{BRIEF.pitch}</p>
        <dl className="n-brief">
          <div><dt>시장</dt><dd>{BRIEF.markets.map((c) => market(c).name).join(", ")}</dd></div>
          <div><dt>분야</dt><dd>{BRIEF.category} <span className="n-meta">(자동으로 정함)</span></dd></div>
          <div><dt>말투</dt><dd>{tone}</dd></div>
          <div><dt>만든 때</dt><dd className="n-num">{BRIEF.runAt}</dd></div>
        </dl>
      </div>
      <DraftsBoard />
    </div>
  );
}
