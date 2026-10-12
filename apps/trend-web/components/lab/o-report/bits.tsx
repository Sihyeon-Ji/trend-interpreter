/* 작은 표시들 — 쓸 때 조심, 증감, 순위 변화, 이름 조판. 색만으로 뜻을 전하지 않는다(글자·기호가 같이 간다). */
import type { CSSProperties } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fitName, fmtPct, type Risk, type RiskNote } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report/copy";

/** 주의·사용 자제는 테두리와 글자로. 판단 보류는 중립 톤(판단 못 한 것이 '문제 없음' 처럼 보이지 않게, 그러나 경고처럼도 보이지 않게) */
export function RiskMark({ risk, locale, withNone = false }: { risk: Risk | "none"; locale: Locale; withNone?: boolean }) {
  if (!risk || (risk === "none" && !withNone)) return null;
  const cls =
    risk === "avoid" ? "border-[var(--or-avoid-line)] text-[var(--or-avoid)]"
    : risk === "caution" ? "border-[var(--or-caution-line)] text-[var(--or-caution)]"
    : "border-[var(--or-line-strong)] text-[var(--or-slate)]";
  const label = tr(locale, risk === "avoid" ? "risk_avoid" : risk === "caution" ? "risk_caution" : risk === "unknown" ? "risk_unknown" : "risk_none");
  return (
    <span className={`inline-flex h-[22px] shrink-0 items-center gap-1 rounded-[3px] border px-1.5 text-[12px] leading-none font-semibold whitespace-nowrap ${cls}`}>
      {risk === "avoid" && <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden><circle cx="6" cy="6" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M2.8 9.2l6.4-6.4" stroke="currentColor" strokeWidth="1.5" /></svg>}
      {risk === "caution" && <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden><path d="M6 1.4l4.8 8.6H1.2z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" /><path d="M6 4.8v2.4M6 8.4v.3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>}
      {label}
    </span>
  );
}

/** 쓸 때 조심 이유 — 알아본 것 전부. 없으면 판정 낱말의 기본 설명. 사전 주의점 원문은 lang="ko" */
export function RiskNotes({ notes, fallback, className = "", max = 3 }: { notes: RiskNote[]; fallback: string; className?: string; max?: number }) {
  const shown = notes.slice(0, max);
  if (!shown.length) return <p className={className}>{fallback}</p>;
  if (shown.length === 1) return <p className={className}><Note n={shown[0]} /></p>;
  return (
    <ul className={`space-y-1 ${className}`}>
      {shown.map((n) => <li key={`${n.text}${n.quote ?? ""}`} className="relative pl-3 before:absolute before:top-[0.7em] before:left-0 before:h-1 before:w-1 before:rounded-full before:bg-current"><Note n={n} /></li>)}
    </ul>
  );
}
const Note = ({ n }: { n: RiskNote }) => <>{n.text}{n.quote && <> <span lang="ko">“{n.quote}”</span></>}</>;

/** 증감 숫자. 오름은 청록 ▲, 내림은 석판 ▼ (빨강은 쓰지 않는다) */
export function Growth({ g, size = "sm", locale }: { g: number; size?: "xs" | "sm" | "md" | "lg"; locale: Locale }) {
  const flat = Math.round(Math.abs(g) * 100) === 0;   // 0% 에 ▲ 를 달지 않는다
  const up = g >= 0;
  const cls = size === "lg" ? "text-[36px] leading-none font-bold" : size === "md" ? "text-[21px] leading-none font-bold" : size === "sm" ? "text-[16px] leading-none font-semibold" : "text-[13px] leading-none font-semibold";
  return (
    <span className={`or-num inline-flex items-baseline gap-[0.18em] whitespace-nowrap ${cls} ${up && !flat ? "text-[var(--or-petrol)]" : "text-[var(--or-slate)]"}`}>
      {!flat && <span aria-hidden className="text-[0.6em]">{up ? "▲" : "▼"}</span>}
      {fmtPct(g)}
      {!flat && <span className="sr-only">{tr(locale, up ? "growth_up" : "growth_down")}</span>}
    </span>
  );
}

/** 순위 변화. none12 = 12주 보기(견줄 앞 기간이 없다)는 조용한 '–' 와 그 이유(화면 읽기용) */
export function RankChange({ n, locale, fresh = false, none12 = false }: { n: number | null; locale: Locale; fresh?: boolean; none12?: boolean }) {
  if (none12) return <span className="or-num text-[12px] text-[var(--or-slate)]" title={tr(locale, "rank_none_12")}><span aria-hidden>–</span><span className="sr-only">{tr(locale, "rank_none_12")}</span></span>;
  // 한 창 전에는 검색이 드물어 순위를 매길 수 없었는데 지금은 순위에 든 밈 — 새로 떴다
  if (n == null && fresh) return <span className="text-[12px] font-semibold text-[var(--or-petrol)]">{tr(locale, "rank_new")}<span className="sr-only"> ({tr(locale, "rank_new_note")})</span></span>;
  if (n == null) return null;
  if (n === 0) return <span className="or-num text-[12px] text-[var(--or-slate)]" title={tr(locale, "rank_same")}><span aria-hidden>–</span><span className="sr-only">{tr(locale, "rank_same")}</span></span>;
  const up = n > 0;
  const label = tr(locale, up ? "rank_up" : "rank_down", { n: Math.abs(n) });
  return (
    <span className={`or-num inline-flex items-center gap-0.5 text-[12px] font-semibold ${up ? "text-[var(--or-petrol)]" : "text-[var(--or-slate)]"}`} title={label}>
      <span aria-hidden>{up ? "▲" : "▼"}{Math.abs(n)}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** 표지·목록 위의 '새로 실림' · '뜻 바뀜' · '검색어' */
export function Tag({ kind, locale }: { kind: "new" | "changed" | "search"; locale: Locale }) {
  const cls = kind === "new" ? "bg-[var(--or-petrol-tint)] text-[var(--or-petrol-deep)]"
    : kind === "changed" ? "border border-[var(--or-petrol)] text-[var(--or-petrol-deep)]"
      : "border border-[var(--or-line-strong)] text-[var(--or-slate)]";
  return (
    <span className={`inline-flex h-5 shrink-0 items-center rounded-[3px] px-1.5 text-[12px] leading-none font-semibold whitespace-nowrap ${cls}`}>
      {tr(locale, kind === "new" ? "tag_new" : kind === "changed" ? "tag_changed" : "tag_search")}
    </span>
  );
}

/** 이름을 칸 폭에 맞춰 세운다 — 줄은 여기서(낱말 사이), 크기는 CSS(.or-fit: 칸 폭 ÷ 가장 긴 줄, 칸 높이 ÷ 줄 수).
 *  줄 사이 띄어쓰기는 글 속에 남겨 화면 읽기·복사에서 이름이 붙지 않게 한다. */
export function FitName({ name, lang, as: El = "p", className = "", maxLines = 3, splitAbove, id }: {
  name: string; lang?: string; as?: "p" | "h1" | "h2"; className?: string; maxLines?: number; splitAbove?: number; id?: string;
}) {
  const { lines, em } = fitName(name, maxLines, splitAbove);
  const spaced = /\s/.test(name.trim());
  return (
    <El id={id} lang={lang} className={`or-fit ${className}`} style={{ "--em": em.toFixed(3), "--lines": lines.length } as CSSProperties}>
      {lines.map((ln, i) => (
        <span key={i} className="block">
          {ln}
          {spaced && i < lines.length - 1 ? " " : null}
        </span>
      ))}
    </El>
  );
}
