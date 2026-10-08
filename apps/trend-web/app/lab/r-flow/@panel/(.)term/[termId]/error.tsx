"use client";

import { useRouter } from "next/navigation";
import { startTransition } from "react";

/* 패널 안의 밈을 불러오지 못했을 때 — 패널은 열린 채로 다시 불러오기를 낸다 */
export default function PanelError({ reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  const ko = typeof document !== "undefined" && document.documentElement.lang !== "en";
  return (
    <div className="rf-term" role="alert">
      <p className="rf-h2">{ko ? "밈을 불러오지 못했습니다." : "Couldn't load this meme."}</p>
      <p className="rf-note" style={{ marginTop: 6 }}>{ko ? "자료를 주는 서버가 답하지 않았습니다." : "The data server didn't answer."}</p>
      <button type="button" className="rf-btn" data-kind="line" style={{ marginTop: 14 }} onClick={() => startTransition(() => { router.refresh(); reset(); })}>
        {ko ? "다시 불러오기" : "Reload"}
      </button>
    </div>
  );
}
