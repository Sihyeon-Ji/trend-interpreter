"use client";

import { useRouter } from "next/navigation";
import { startTransition } from "react";

/* 이 시안의 화면을 불러오지 못했을 때(자료 서버가 답하지 않음) — 예시 데이터로 바꾸지 않고 다시 불러오기를 낸다 */
export default function RFlowError({ reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  const ko = typeof document !== "undefined" && document.documentElement.lang !== "en";
  return (
    <div role="alert" style={{ padding: "40px 0" }}>
      <h1 className="rf-title">{ko ? "화면을 불러오지 못했습니다" : "Couldn't load this screen"}</h1>
      <p className="rf-lead">{ko ? "자료를 주는 서버가 답하지 않았습니다. 잠시 뒤 다시 불러오세요." : "The data server didn't answer. Reload in a moment."}</p>
      <button type="button" className="rf-btn" style={{ marginTop: 16 }} onClick={() => startTransition(() => { router.refresh(); reset(); })}>
        {ko ? "다시 불러오기" : "Reload"}
      </button>
    </div>
  );
}
