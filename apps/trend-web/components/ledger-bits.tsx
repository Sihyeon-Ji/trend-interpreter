import Link from "next/link";
import { glossFor } from "@/lib/gloss";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L, fmtDate } from "@/lib/labels";
import type { KeywordCard, Lifecycle } from "@/lib/types";

/* 원장 화면의 작은 부품 (Plan 20, 시안 n-redesign) — 단계 눈금·리스크 글자·12주 추이·말 표. 스타일은 ledger.css. */
const STAGE_ORDER: Lifecycle[] = ["emerging", "rising", "peak", "steady", "declining", "dormant"];

/** 생애주기 여섯 칸 눈금 + 낱말. 판단 보류(unknown)는 칸을 칠하지 않는다 */
export function StageMark({ stage, locale }: { stage: Lifecycle; locale: Locale }) {
  const at = STAGE_ORDER.indexOf(stage);
  return (
    <span className="n-stage">
      <i aria-hidden="true">{STAGE_ORDER.map((s, n) => <b key={s} data-on={n === at} />)}</i>
      <span>{L(locale).lifecycle[stage]}</span>
    </span>
  );
}

export type RiskKey = "none" | "caution" | "avoid" | "unknown";
export const riskKey = (c: { risk_level?: string | null }): RiskKey =>
  c.risk_level === "avoid" ? "avoid" : c.risk_level === "caution" ? "caution" : c.risk_level === "none" ? "none" : "unknown";

export function RiskText({ risk, locale }: { risk: RiskKey; locale: Locale }) {
  return <span className="n-risk" data-r={risk}>{t(locale, risk === "none" ? "dr_ok" : `risk_${risk}` as StringKey)}</span>;
}

/** 12주 언급 추이 — 한 줄, 마지막 주에만 점. 값은 옆 칸(4주 언급)과 aria-label 로도 읽힌다 */
export function Spark({ values, label, w = 84, h = 22 }: { values: number[]; label: string; w?: number; h?: number }) {
  if (values.length < 2) return <span className="n-meta">–</span>;
  const max = Math.max(...values, 1);
  const pad = 3;
  const x = (i: number) => pad + (i * (w - pad * 2)) / (values.length - 1);
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2);
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = values.length - 1;
  return (
    <svg className="n-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      <line x1={pad} x2={w - pad} y1={h - pad} y2={h - pad} stroke="#e5e5e5" strokeWidth="1" />
      <path d={d} fill="none" stroke="#000" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last])} r="2.5" fill="#000" />
    </svg>
  );
}

/** 말 표 — 말과 뜻 · 단계 · 퍼진 정도 · 브랜드 리스크 · 4주 언급 · 12주 · 마지막 쓰임. 휴대폰은 ledger.css 가 한 줄씩 쌓는다 */
export function WordTable({ cards, caption, locale, regions }: { cards: KeywordCard[]; caption: string; locale: Locale; regions: string[] }) {
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  return (
    <table className="n-table">
      <caption className="n-sr">{caption}</caption>
      <colgroup>
        <col style={{ width: "32%" }} /><col style={{ width: "13%" }} /><col style={{ width: "10%" }} /><col style={{ width: "17%" }} />
        <col style={{ width: "9%" }} /><col style={{ width: "11%" }} /><col style={{ width: "8%" }} />
      </colgroup>
      <thead>
        <tr>
          <th scope="col">{t(locale, "tb_word")}</th><th scope="col">{t(locale, "dr_why_stage")}</th><th scope="col">{t(locale, "dr_why_spread")}</th>
          <th scope="col">{t(locale, "dr_why_risk")}</th><th scope="col" className="n-r">{t(locale, "tb_mentions")}</th>
          <th scope="col" style={{ paddingLeft: 16 }}>{t(locale, "tb_12w")}</th><th scope="col">{t(locale, "tb_last")}</th>
        </tr>
      </thead>
      <tbody>
        {cards.map((c) => {
          const weekly = c.weekly.map((p) => p.count);
          const last = c.last_used ?? c.last_seen;
          return (
            <tr key={c.term_id}>
              <td>
                <span className="n-tw" lang={langTag(c.lang)}><Link href={`/dictionary/${encodeURIComponent(c.term_id)}${q}`}>{c.canonical}</Link></span>
                <span className="n-tg">{glossFor(c, locale)}</span>
              </td>
              <td data-label={t(locale, "dr_why_stage")}><StageMark stage={c.lifecycle} locale={locale} /></td>
              <td data-label={t(locale, "dr_why_spread")}>{c.diffusion ? t(locale, `diffusion_${c.diffusion}` as StringKey) : "–"}</td>
              <td data-label={t(locale, "dr_why_risk")}><RiskText risk={riskKey(c)} locale={locale} /></td>
              <td data-label={t(locale, "tb_mentions")} className="n-r">{c.mentions_4w.toLocaleString()}</td>
              <td data-label={t(locale, "tb_12w")} className="n-sparkcell">
                <Spark values={weekly} label={t(locale, "tb_spark").replace("{a}", String(weekly[0] ?? 0)).replace("{b}", String(weekly.at(-1) ?? 0))} />
              </td>
              <td data-label={t(locale, "tb_last")} className="n-num">{last ? fmtDate(last) : "–"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
