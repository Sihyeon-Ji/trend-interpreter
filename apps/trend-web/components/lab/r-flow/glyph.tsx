/* 누가 했나 — 규칙(네모), AI(마름모), 사람(동그라미). 모양과 낱말이 함께 달라 색을 못 봐도 구분된다.
   비어 있으면 아직 하지 않은 단계, 채워져 있으면 한 단계. 시안의 로고도 이 셋이다. */
import type { Locale } from "@/lib/i18n";
import { tr } from "./copy";

export type Actor = "rule" | "ai" | "person";

export function Mark({ actor, filled = true, size = 10 }: { actor: Actor; filled?: boolean; size?: number }) {
  const s = size;
  return (
    <svg className="rf-mark" data-actor={actor} data-filled={filled} width={s} height={s} viewBox="0 0 10 10" aria-hidden="true" focusable="false">
      {actor === "rule" && <rect x="1" y="1" width="8" height="8" rx="1.6" />}
      {actor === "ai" && <path d="M5 0.6 9.4 5 5 9.4 0.6 5Z" />}
      {actor === "person" && <circle cx="5" cy="5" r="4.2" />}
    </svg>
  );
}

/** 표지와 낱말: '■ 규칙' */
export function Who({ actor, locale, children }: { actor: Actor; locale: Locale; children?: React.ReactNode }) {
  return (
    <span className="rf-who" data-actor={actor}>
      <Mark actor={actor} />
      <span>{children ?? tr(locale, actor === "rule" ? "actor_rule" : actor === "ai" ? "actor_ai" : "actor_person")}</span>
    </span>
  );
}

export function Logo() {
  return (
    <span className="rf-logo" aria-hidden="true">
      <Mark actor="rule" size={9} />
      <Mark actor="ai" size={9} />
      <Mark actor="person" size={9} />
    </span>
  );
}
