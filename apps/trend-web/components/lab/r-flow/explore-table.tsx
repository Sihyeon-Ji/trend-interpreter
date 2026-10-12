"use client";

/* 둘러보기 표 — 줄을 누르거나 ↵ 하면 옆 패널로 밈이 열리고 표는 그대로 남는다(지금 연 줄은 칠해 둔다).
   ↑↓·J·K 로 줄 사이를 옮긴다. 판정(단계·위험)은 백엔드 값 그대로 글로만 옮긴다. */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { glossFor } from "@/lib/gloss";
import { langTag, scriptLang } from "@/lib/lang";
import { L } from "@/lib/labels";
import type { KeywordCard } from "@/lib/types";
import { Spark } from "./charts";
import { num, tr } from "./copy";
import { rememberMeme } from "./store";

const BASE = "/lab/r-flow";

function riskOf(c: KeywordCard): "avoid" | "caution" | "unknown" | "none" | "unchecked" {
  if (c.risk_level === "avoid" || c.risk_level === "caution") return c.risk_level;
  if (c.risk_level === "none") return "none";
  return c.risk_checked_at ? "unknown" : "unchecked";
}
const RISK_KEY = { avoid: "risk_avoid", caution: "risk_caution", unknown: "risk_unknown", none: "risk_none", unchecked: "risk_unchecked" } as const;

export function ExploreTable({ rows, market, locale, caption }: { rows: KeywordCard[]; market: string; locale: Locale; caption: string }) {
  const path = usePathname();
  const open = path.startsWith(`${BASE}/term/`) ? decodeURIComponent(path.slice(`${BASE}/term/`.length)) : null;
  const body = useRef<HTMLTableSectionElement>(null);
  const labels = L(locale);

  const move = (e: React.KeyboardEvent) => {
    const down = e.key === "ArrowDown" || e.key === "j";
    const up = e.key === "ArrowUp" || e.key === "k";
    if (!down && !up) return;
    const links = [...(body.current?.querySelectorAll<HTMLAnchorElement>("a[data-row]") ?? [])];
    const at = links.findIndex((a) => a === document.activeElement);
    if (at < 0) return;
    e.preventDefault();
    links[Math.max(0, Math.min(links.length - 1, at + (down ? 1 : -1)))]?.focus();
  };

  return (
    <table className="rf-table">
      <caption className="rf-sr">{caption}</caption>
      <colgroup>
        <col style={{ width: "22%" }} />
        <col />
        <col style={{ width: 132 }} />
        <col style={{ width: 104 }} />
        <col style={{ width: 64 }} />
        <col style={{ width: 96 }} />
        <col style={{ width: 104 }} />
      </colgroup>
      <thead>
        <tr>
          <th scope="col">{tr(locale, "ex_col_meme")}</th>
          <th scope="col">{tr(locale, "ex_col_gloss")}</th>
          <th scope="col">{tr(locale, "ex_col_stage")}</th>
          <th scope="col">{tr(locale, "ex_col_weeks")}</th>
          <th scope="col" className="rf-t-num">{tr(locale, "ex_col_m4")}</th>
          <th scope="col">{tr(locale, "ex_col_risk")}</th>
          <th scope="col">{tr(locale, "ex_col_markets")}</th>
        </tr>
      </thead>
      <tbody ref={body} onKeyDown={move}>
        {rows.map((c) => {
          const risk = riskOf(c);
          const gloss = glossFor(c, locale);
          const pending = (locale === "en" && c.en_pending) || (locale === "ko" && c.ko_pending);
          const others = c.regions.filter((r) => r !== market);
          return (
            <tr key={c.term_id} data-active={open === c.term_id}>
              <td data-col="w">
                <Link
                  data-row="" className="rf-row-link" lang={langTag(c.lang)} scroll={false}
                  href={`${BASE}/term/${encodeURIComponent(c.term_id)}?m=${market}`}
                  onClick={() => rememberMeme({ id: c.term_id, name: c.canonical, lang: c.lang })}
                >{c.canonical}</Link>
              </td>
              <td data-col="g"><div className="rf-cell-gloss" data-pending={pending} title={gloss} lang={scriptLang(gloss)}>{gloss}</div></td>
              <td data-col="s"><span className="rf-stage" data-life={c.lifecycle}><i aria-hidden="true" />{labels.lifecycle[c.lifecycle]}</span></td>
              <td data-col="k"><Spark values={c.weekly.map((p) => p.count)} label={tr(locale, "ex_spark", { a: c.weekly[0]?.count ?? 0, b: c.weekly.at(-1)?.count ?? 0 })} /></td>
              <td data-col="n" className="rf-t-num">{num(c.mentions_4w)}</td>
              <td data-col="r"><span className="rf-risk" data-r={risk}>{tr(locale, RISK_KEY[risk])}</span></td>
              <td data-col="m">{others.length ? <span className="rf-mkts">{others.slice(0, 3).map((r) => <span key={r}>{r === "GLOBAL" ? "EN" : r}</span>)}{others.length > 3 && <span>+{others.length - 3}</span>}</span> : <span className="rf-muted">–</span>}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
