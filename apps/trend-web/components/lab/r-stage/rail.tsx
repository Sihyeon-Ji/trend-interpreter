/* 초안 한 시장의 네 단계 — 규칙이 고르고, AI가 쓰고, 규칙이 다시 보고, 사람이 승인한다.
   막대마다 '누가' 의 움직임이 다르다: 규칙은 일정한 속도로 훑고(기계), AI는 숨 쉬듯 밝아졌다 어두워지고, 사람은 도장처럼 채운다. */
import { ListChecks, Sparkles, Stamp } from "lucide-react";
import type { LabLocale as Locale } from "@/lib/i18n";
import type { CopyCheck, GenerationResult } from "@/lib/types";
import { tx } from "./copy";
import type { Column, Run } from "./store";

export type StepState = "idle" | "working" | "done" | "flag" | "fail" | "skip" | "ready";
export interface Steps { pick: StepState; write: StepState; check: StepState; sign: StepState }

/** 같은 밈이 든 문구마다 판정을 붙인다(첫 문구로 다시 검사하고, 같은 밈의 쓰임 판정은 그 밈이 든 문구 모두에) — make-flow 와 같은 규칙 */
export function issuesFor(text: string, check: CopyCheck | null) {
  const memes = check?.memes.filter((m) => m.matched && text.includes(m.matched)) ?? [];
  return memes.flatMap((m) => m.issues);
}

export function flaggedCount(gen: GenerationResult | null, check: CopyCheck | null) {
  return (gen?.copies ?? []).filter((c) => issuesFor(c.text, check).length > 0).length;
}

export function stepsOf(col: Column, run: Run): Steps {
  const pick: StepState = run.phase === "reading" ? "working" : run.phase === "error" ? "fail" : col.status === "none" ? "skip" : col.pick ? "done" : "idle";
  const write: StepState = col.status === "none" ? "skip" : col.status === "writing" ? "working" : col.gen ? "done" : col.status === "failed" || col.status === "stopped" ? "fail" : "idle";
  const checked = !!col.check || col.checkFailed || col.status === "poster" || col.status === "done";
  const check: StepState = col.status === "none" ? "skip" : col.status === "checking" ? "working" : checked ? (flaggedCount(col.gen, col.check) > 0 ? "flag" : "done") : col.status === "stopped" && col.gen ? "fail" : "idle";
  const sign: StepState = col.sign ? "done" : col.status === "done" ? "ready" : col.status === "none" ? "skip" : "idle";
  return { pick, write, check, sign };
}

const ITEMS = [
  { key: "pick", who: "rule", icon: ListChecks, label: "step_pick" },
  { key: "write", who: "ai", icon: Sparkles, label: "step_write" },
  { key: "check", who: "rule", icon: ListChecks, label: "step_check" },
  { key: "sign", who: "human", icon: Stamp, label: "step_sign" },
] as const;

/** 네 칸 막대. size l 은 낱말까지, s 는 막대만(이름은 화면 읽기용) */
export function StepRail({ steps, locale, size = "l", label }: { steps: Steps; locale: Locale; size?: "l" | "s"; label: string }) {
  const word = (s: StepState) => ({ idle: "", working: "…", done: "", flag: "!", fail: "×", skip: "–", ready: "" })[s];
  return (
    <ol className="rs-rail" data-size={size} aria-label={label}>
      {ITEMS.map((it) => {
        const st = steps[it.key];
        const Icon = it.icon;
        return (
          <li key={it.key} data-who={it.who} data-state={st}>
            <span className="rs-rail-bar" aria-hidden="true" />
            <span className={size === "l" ? "rs-rail-label" : "rs-sr"}>
              <Icon aria-hidden="true" size={13} strokeWidth={2.2} />
              {tx(locale, it.label)}
              <span className="rs-sr">{` ${tx(locale, it.who === "rule" ? "who_rule" : it.who === "ai" ? "who_ai" : "who_human")}, ${stateWord(st, locale)}`}</span>
              {size === "l" && word(st) ? <span className="rs-rail-mark" aria-hidden="true">{word(st)}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function stateWord(s: StepState, locale: Locale): string {
  const ko = { idle: "대기", working: "진행 중", done: "완료", flag: "표시 있음", fail: "멈춤", skip: "건너뜀", ready: "승인 대기" };
  const en = { idle: "waiting", working: "in progress", done: "done", flag: "flagged", fail: "stopped", skip: "skipped", ready: "awaiting approval" };
  return (locale === "ko" ? ko : en)[s];
}
