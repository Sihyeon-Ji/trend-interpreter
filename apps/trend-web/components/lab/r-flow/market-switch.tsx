"use client";

/* 둘러보기의 시장 고르기 — 레이아웃에 있어 시장을 바꿔도 남아 있고, 고른 표시가 새 자리로 미끄러져 간다(누른 즉시).
   표는 화면(page)이 View Transitions 로 그 방향으로 바꾼다. */
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { useState } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { MARKETS, isMarket, marketName, num, tr, type Market } from "./copy";

const BASE = "/lab/r-flow";

export function MarketSwitch({ locale, counts }: { locale: Locale; counts: Record<string, number> | null }) {
  const sp = useSearchParams();
  const raw = sp.get("m");
  const current: Market = isMarket(raw) ? raw : "KR";
  const list = sp.get("l");
  const [clicked, setClicked] = useState<{ from: Market; to: Market } | null>(null);
  const shown = clicked && clicked.from === current ? clicked.to : current;
  const at = MARKETS.indexOf(current);
  return (
    <nav className="rf-seg" aria-label={tr(locale, "ex_markets")}>
      {MARKETS.map((m, i) => (
        <Link key={m} href={`${BASE}/explore?m=${m}${list && list !== "rising" ? `&l=${list}` : ""}`} aria-current={m === current ? "page" : undefined} scroll={false}
          transitionTypes={[i > at ? "rf-right" : i < at ? "rf-left" : "rf-same"]}
          onClick={() => { if (m !== current) setClicked({ from: current, to: m }); }}>
          {m === shown && <motion.span layoutId="rf-mseg-thumb" className="rf-seg-thumb" aria-hidden="true" transition={{ type: "spring", duration: 0.34, bounce: 0 }} />}
          {marketName(locale, m)}<small>{counts?.[m] != null ? num(counts[m]) : ""}</small>
        </Link>
      ))}
    </nav>
  );
}

/** '이 시장으로 초안 만들기' — 지금 고른 시장을 넘긴다 */
export function MakeForMarket({ locale }: { locale: Locale }) {
  const sp = useSearchParams();
  const raw = sp.get("m");
  const m: Market = isMarket(raw) ? raw : "KR";
  return <Link className="rf-btn" data-kind="line" data-size="s" href={`${BASE}?regions=${m}`}>{tr(locale, "ex_make")}</Link>;
}
