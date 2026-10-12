"use client";

/* 진행표 — 시장(줄) × 다섯 단계(칸). 칸 위의 가는 막대가 실제 요청이 끝날 때 그 칸을 한 일의 색으로 차오른다:
   먹(규칙), 파랑(AI), 초록(사람). 도는 중인 칸은 막대 위로 빛이 지나가고 걸린 시간이 흐른다.
   시작 화면에서는 같은 표가 비어 있는 채로 '이렇게 진행됩니다' 를 보여 주고, 만들기를 누르면 그대로 살아난다. */
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { MARKET_LANG, marketName, num, tr, type CopyKey, type Market } from "./copy";
import { Mark, type Actor } from "./glyph";

export type StepKey = "pick" | "write" | "check" | "poster" | "sign";
export type S = "idle" | "wait" | "run" | "done" | "warn" | "fail" | "none" | "stop";
export interface Step { s: S; t0?: number; t1?: number }

export const STEPS: { key: StepKey; actor: Actor; title: CopyKey; desc: CopyKey }[] = [
  { key: "pick", actor: "rule", title: "st_pick", desc: "st_pick_desc" },
  { key: "write", actor: "ai", title: "st_write", desc: "st_write_desc" },
  { key: "check", actor: "rule", title: "st_check", desc: "st_check_desc" },
  { key: "poster", actor: "rule", title: "st_poster", desc: "st_poster_desc" },
  { key: "sign", actor: "person", title: "st_sign", desc: "st_sign_desc" },
];

/** 칸 하나에 보일 것 — 결과 한 줄(원문 낱말이면 lang), 작은 설명 한 줄 */
export interface CellView { main: string; lang?: string; word?: boolean; meta?: string; actor?: Actor }
export interface LaneView { market: Market; steps: Record<StepKey, Step>; cells: Record<StepKey, CellView>; sub?: string }

function useTicker(active: boolean, ms = 100) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [active, ms]);
  return now;
}

const secs = (locale: Locale, ms: number) => tr(locale, "sec", { n: (Math.max(0, ms) / 1000).toFixed(1) });

export function Matrix({ lanes, locale, ghost, selected, onSelect, counts, quiet }: {
  lanes: LaneView[]; locale: Locale; ghost?: boolean; selected?: Market | null; onSelect?: (m: Market) => void;
  counts?: Record<string, number> | null; quiet?: boolean;
}) {
  const running = lanes.some((l) => STEPS.some((st) => l.steps[st.key].s === "run"));
  const now = useTicker(running);

  return (
    <>
    <ol className="rf-matrix" aria-label={tr(locale, "run_lanes")} data-quiet={quiet ? "true" : undefined} data-ghost={ghost ? "true" : undefined}>
      <li className="rf-mx-head" aria-hidden="true">
        <span className="rf-mx-h" />
        {STEPS.map((st) => (
          <span key={st.key} className="rf-mx-h">
            <b><Mark actor={st.actor} />{tr(locale, st.title)}</b>
            <span>{tr(locale, st.actor === "rule" ? "actor_rule" : st.actor === "ai" ? "actor_ai" : "actor_person")}</span>
            {ghost && <p>{tr(locale, st.desc)}</p>}
          </span>
        ))}
      </li>
      <AnimatePresence initial={false}>
        {lanes.map((lane) => {
          const sel = !ghost && selected === lane.market;
          return (
            <motion.li
              key={lane.market} layout="position" className="rf-lane"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }}
              transition={{ layout: { type: "spring", duration: 0.45, bounce: 0 }, opacity: { duration: 0.2 } }}
              data-selected={sel} data-selectable={!ghost && !!onSelect}
              onClick={!ghost && onSelect ? () => onSelect(lane.market) : undefined}
            >
              {ghost || !onSelect ? (
                <div className="rf-lane-m">
                  <b>{marketName(locale, lane.market)}</b>
                  <span>{counts?.[lane.market] != null ? `${tr(locale, "nav_verified_sr")} ${num(counts[lane.market])}` : tr(locale, `market_${lane.market}_lang`)}</span>
                </div>
              ) : (
                <button type="button" className="rf-lane-m" aria-pressed={sel} aria-label={`${marketName(locale, lane.market)}, ${tr(locale, "dt_region", { market: marketName(locale, lane.market) })}`}>
                  <b>{marketName(locale, lane.market)}</b>
                  <span>{lane.sub ?? tr(locale, `market_${lane.market}_lang`)}</span>
                </button>
              )}
              {STEPS.map((st, i) => {
                const step = lane.steps[st.key];
                const cell = lane.cells[st.key];
                const actor = cell.actor ?? st.actor;
                const time = step.s === "run" && step.t0 ? secs(locale, (now || step.t0) - step.t0)
                  : step.t0 && step.t1 && (step.s === "done" || step.s === "warn") && st.key !== "sign" ? secs(locale, step.t1 - step.t0) : "";
                return (
                  <div key={st.key} className="rf-cell" data-s={step.s} data-actor={actor} style={{ "--i": i } as React.CSSProperties}>
                    <span className="rf-track" aria-hidden="true"><span className="rf-fill" /><span className="rf-sweep" /></span>
                    <div className="rf-cell-top">
                      <Mark actor={actor} filled={step.s !== "idle" && step.s !== "wait" && step.s !== "none" && step.s !== "stop"} />
                      <span className="rf-cell-label rf-sr">{tr(locale, st.title)}</span>
                      <span className="rf-cell-time" aria-hidden={step.s === "run" ? "true" : undefined}>{time}</span>
                    </div>
                    <span key={`${step.s}-${cell.main}`} className="rf-swap" style={{ display: "contents" }}>
                      <span className="rf-cell-main rf-swap" data-word={cell.word ? "true" : undefined} lang={cell.lang ? langTag(cell.lang) : undefined}>{cell.main}</span>
                      {cell.meta && <span className="rf-cell-meta rf-swap">{cell.meta}</span>}
                    </span>
                  </div>
                );
              })}
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
    {ghost && lanes.length > 1 && <p className="rf-ghost-more">{tr(locale, "gh_more", { markets: lanes.slice(1).map((l) => marketName(locale, l.market)).join(", ") })}</p>}
    </>
  );
}

/** 빈 표(시작 화면) — 고른 시장만 줄로 */
export function ghostLanes(markets: Market[], locale: Locale): LaneView[] {
  const idle = { s: "idle" as const };
  // 비어 있는 칸에는 그 칸에 무엇이 들어올지를 옅게 적는다
  const cells: Record<StepKey, CellView> = {
    pick: { main: tr(locale, "gh_pick") }, write: { main: tr(locale, "gh_write") }, check: { main: tr(locale, "gh_check") },
    poster: { main: tr(locale, "gh_poster") }, sign: { main: tr(locale, "gh_sign") },
  };
  return markets.map((m) => ({ market: m, steps: { pick: idle, write: idle, check: idle, poster: idle, sign: idle }, cells, sub: tr(locale, `market_${m}_lang`) }));
}

export const langOfMarket = (m: Market) => MARKET_LANG[m];
