/* 무대 화면의 작은 부품 — 서버·클라이언트 어디서나 쓴다(훅 없음). */
import { Ban, CircleHelp, CircleCheck, ListChecks, Sparkles, Stamp, TriangleAlert } from "lucide-react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { tx } from "./copy";

/** 글자가 차지하는 너비(em) 어림 — 한글·가나·한자는 1, 라틴은 0.56. 큰 낱말을 칸 너비에 맞추는 데 쓴다 */
export function vlen(s: string): number {
  let n = 0;
  for (const ch of s) {
    if (/[ᄀ-ᇿ⺀-鿿가-힯豈-﫿＀-￯]/.test(ch)) n += 1;
    else if (/\s/.test(ch)) n += 0.28;
    else if (/[A-Z0-9]/.test(ch)) n += 0.66;
    else n += 0.54;
  }
  return Math.max(n, 1.6);
}

/** 밈 원문. 번역하지 않고 제 글자의 lang 을 단다. 크기는 칸(container) 너비에 맞추되 max 를 넘지 않는다.
 *  아주 긴 말(구절)은 두 줄까지 접는다 */
export function MemeWord({ text, lang, max, min = 20, as: Tag = "span", className = "", id }: {
  text: string; lang?: string | null; max: number; min?: number; as?: "span" | "h1" | "h2" | "p"; className?: string; id?: string;
}) {
  const v = vlen(text);
  const lines = v > 11 ? 2 : 1;
  const style = { "--rs-vlen": (v / lines).toFixed(2), "--rs-max": `${max}px`, "--rs-min": `${min}px` } as React.CSSProperties;
  return (
    <Tag id={id} className={`rs-word ${className}`} lang={langTag(lang)} style={style} data-lines={lines}>
      {text}
    </Tag>
  );
}

export type Actor = "rule" | "ai" | "human";
const ACTOR_ICON = { rule: ListChecks, ai: Sparkles, human: Stamp } as const;

/** 누가 했나 — 규칙(목록 표), AI(반짝임), 사람(도장). 아이콘과 낱말이 함께라 색 없이도 구분된다 */
export function ActorTag({ who, locale, children, state }: { who: Actor; locale: Locale; children?: React.ReactNode; state?: "working" | "done" | "idle" }) {
  const Icon = ACTOR_ICON[who];
  return (
    <span className="rs-actor" data-who={who} data-state={state}>
      <Icon aria-hidden="true" size={14} strokeWidth={2} />
      <span className="rs-actor-who">{tx(locale, who === "rule" ? "who_rule" : who === "ai" ? "who_ai" : "who_human")}</span>
      {children ? <span className="rs-actor-what">{children}</span> : null}
    </span>
  );
}

export type VerdictKind = "ok" | "caution" | "avoid" | "unknown" | "unchecked";

/** 리스크 판정 → 화면 판정. 검사했는데 근거가 모자란 것만 '판단 보류'. 검사 전이면 따로 말한다 (lib/keyword riskOf 와 같은 규칙) */
export function verdictOf(x: { risk_level?: string | null; risk_checked_at?: string | null }): VerdictKind {
  if (x.risk_level === "avoid") return "avoid";
  if (x.risk_level === "caution") return "caution";
  if (x.risk_level === "none") return "ok";
  return x.risk_checked_at ? "unknown" : "unchecked";
}

const VERDICT_ICON = { ok: CircleCheck, caution: TriangleAlert, avoid: Ban, unknown: CircleHelp, unchecked: CircleHelp } as const;

export function Verdict({ kind, locale, size = "m" }: { kind: VerdictKind; locale: Locale; size?: "s" | "m" | "l" }) {
  const Icon = VERDICT_ICON[kind];
  const label = tx(locale, kind === "ok" ? "v_ok" : kind === "caution" ? "v_caution" : kind === "avoid" ? "v_avoid" : kind === "unknown" ? "v_unknown" : "v_unchecked");
  return (
    <span className="rs-verdict" data-kind={kind} data-size={size}>
      <Icon aria-hidden="true" size={size === "l" ? 22 : size === "m" ? 16 : 14} strokeWidth={2.2} />
      <span>{label}</span>
    </span>
  );
}

/** 낱말 옆 작은 표지 — 조심(삼각형)·쓰지 않음(금지). 늘 화면 읽기용 낱말과 함께 */
export function RiskMark({ kind, locale }: { kind: VerdictKind; locale: Locale }) {
  if (kind !== "caution" && kind !== "avoid") return null;
  const Icon = kind === "avoid" ? Ban : TriangleAlert;
  return (
    <span className="rs-riskmark" data-kind={kind} title={tx(locale, kind === "avoid" ? "v_avoid" : "v_caution")}>
      <Icon aria-hidden="true" size={14} strokeWidth={2.2} />
      <span className="rs-sr">{tx(locale, kind === "avoid" ? "v_avoid" : "v_caution")}</span>
    </span>
  );
}

/* 날짜는 서울 시각으로 고정 — 서버 그림과 브라우저 그림이 같은 글자가 되게(하이드레이션) */
const TZ = "Asia/Seoul";

/** 날짜 'M월 D일' / 'Mon D' */
export function fmtDay(iso: string | null | undefined, locale: Locale, withYear = false): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", { timeZone: TZ, ...(withYear ? { year: "numeric", month: "short", day: "numeric" } : { month: "short", day: "numeric" }) });
}

export function fmtStamp(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(locale === "ko" ? "ko-KR" : "en-US", { timeZone: TZ, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const fmtN = (n: number) => n.toLocaleString("en-US");

/** 같은 낱말이 화면을 건너 옮겨 가는 보기 전환 이름 — 시장까지 넣어 한 화면에 같은 이름이 둘 생기지 않게 */
export const wordVT = (termId: string, market?: string | null) => `rs-word-${market ? `${market}-` : ""}${termId.replace(/[^\w-]/g, "_")}`;
