import { cn } from "@/lib/utils";

/** 칩 안의 고른 표시 — 여러 곳을 고르는 칩(지역)은 네모 체크, 하나만 고르는 칩(톤)은 동그라미. 색만으로 가르지 않는다.
 *  대시보드·사전·최근 변화·추천의 칩이 같은 모양을 쓴다(개편 종합 09-29). */
export function ChipMark({ on, round }: { on: boolean; round?: boolean }) {
  return (
    <span aria-hidden className={cn("inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center border", round ? "rounded-full" : "rounded-[3px]",
      on ? "border-link-blue" : "border-hairline-strong")}>
      {on && (round ? <span className="h-1.5 w-1.5 rounded-full bg-link-blue" />
        : <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 5.2l2 2 4-4.4" fill="none" stroke="var(--link-blue)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>)}
    </span>
  );
}
