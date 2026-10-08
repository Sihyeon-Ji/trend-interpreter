"use client";

import { animate, useReducedMotion } from "motion/react";
import { useLayoutEffect, useRef } from "react";
import { fmtN } from "./bits";
import { useFirstPlay } from "./play";

/** 규칙의 움직임 — 일정한 속도로 세어 내려가는 숫자(후보 2,720개 → 견준 48개). 처음 한 번만, 움직임 줄이기면 바로 끝 값 */
export function Count({ from, to, playKey, duration = 0.9 }: { from: number; to: number; playKey: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const first = useFirstPlay(playKey);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !first || reduce || from === to) return;
    el.textContent = fmtN(from);
    const ctl = animate(from, to, { duration, ease: "linear", onUpdate: (v) => { el.textContent = fmtN(Math.round(v)); } });
    return () => ctl.stop();
  }, [first, reduce, from, to, duration]);
  return <span ref={ref} className="rs-num">{fmtN(to)}</span>;
}
