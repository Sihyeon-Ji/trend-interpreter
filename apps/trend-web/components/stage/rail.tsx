/* 초안 한 시장의 네 단계 — 규칙이 고르고, AI가 쓰고, 규칙이 다시 보고, 사람이 승인한다.
   막대마다 '누가' 의 움직임이 다르다: 규칙은 일정한 속도로 훑고(기계), AI는 숨 쉬듯 밝아졌다 어두워지고, 사람은 도장처럼 채운다. */
import { ListChecks, Sparkles, Stamp } from "lucide-react";
import { copyIssues, isBlocking } from "@/lib/approval";
import type { Locale } from "@/lib/i18n";
import { tx } from "./copy";
import type { Column, Run } from "./store";

export type StepState = "idle" | "working" | "done" | "flag" | "block" | "fail" | "skip" | "ready";
export interface Steps { pick: StepState; write: StepState; check: StepState; sign: StepState }

/** 문구 하나의 규칙 코드(문구마다 따로 다시 검사한 결과) — lib/approval.ts copyIssues */
export const issuesAt = (col: Column, i: number) => copyIssues(col.checks?.[i]);

/** 규칙이 표시한 문구 수 */
export function flaggedCount(col: Column) {
  return (col.gen?.copies ?? []).filter((_, i) => issuesAt(col, i).length > 0).length;
}

/** 쓰지 말라고 한 말(사용 자제·저속한 말투)이나 욕설·선정 표현이 든 문구의 번호 — 하나라도 있으면 승인·요청을 막는다 */
export function blockedAt(col: Column): number[] {
  return (col.gen?.copies ?? []).flatMap((_, i) => (issuesAt(col, i).some(isBlocking) ? [i] : []));
}

export function stepsOf(col: Column, run: Run): Steps {
  const pick: StepState = run.phase === "reading" ? "working" : run.phase === "error" ? "fail" : col.status === "none" ? "skip" : col.pick ? "done" : "idle";
  const write: StepState = col.status === "none" ? "skip" : col.status === "writing" ? "working" : col.gen ? "done" : col.status === "failed" || col.status === "stopped" ? "fail" : "idle";
  const checked = !!col.checks || col.checkFailed || col.status === "poster" || col.status === "done";
  const blocked = blockedAt(col).length > 0;
  // 검사가 돌아오지 않았으면(504) 통과처럼 'done' 이 아니라 실패 — 데모 점검 10-14 에서 검은 막대가 통과로 읽혔다
  const check: StepState = col.status === "none" ? "skip" : col.status === "checking" ? "working"
    : col.checkFailed ? "fail" : checked ? (blocked ? "block" : flaggedCount(col) > 0 ? "flag" : "done") : col.status === "stopped" && col.gen ? "fail" : "idle";
  const a = col.approval?.status;
  const sign: StepState = a === "approved" ? "done" : a === "rejected" ? "fail" : col.status === "none" ? "skip"
    : col.status === "done" ? (blocked && !a ? "block" : "ready") : "idle";
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
  const word = (s: StepState) => ({ idle: "", working: "…", done: "", flag: "!", block: "×", fail: "×", skip: "–", ready: "" })[s];
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
  const ko = { idle: "대기", working: "진행 중", done: "완료", flag: "표시 있음", block: "막힘", fail: "멈춤", skip: "건너뜀", ready: "승인 대기" };
  const en = { idle: "waiting", working: "in progress", done: "done", flag: "flagged", block: "blocked", fail: "stopped", skip: "skipped", ready: "awaiting approval" };
  const ja = { idle: "待機中", working: "進行中", done: "完了", flag: "マークあり", block: "使用NG", fail: "停止", skip: "スキップ", ready: "承認待ち" };
  return { ko, en, ja }[locale][s];
}
