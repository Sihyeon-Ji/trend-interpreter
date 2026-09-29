"use client";

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, stageLabel } from "@/lib/lab/f-report-copy";
import type { Row } from "@/lib/lab/f-report";
import { Sparkline, growthText } from "./charts";
import { useWatchlist } from "./watch";

/** 홈의 '내가 지켜보는 밈' — 고른 지역 목록에 있으면 지금 단계·증감을, 없으면 이름만. 비어 있으면 절 자체를 내지 않는다. */
export function Watchlist({ locale, rows }: { locale: Locale; rows: Row[] }) {
  const { items, remove } = useWatchlist();
  if (!items.length) return null;
  const byId = new Map(rows.map((r) => [r.id, r]));
  return (
    <section className="fr-watch" aria-labelledby="fr-watch-h">
      <div className="fr-section-head" style={{ margin: 0 }}>
        <h2 id="fr-watch-h" className="fr-h2">{c(locale, "watchlist_title")} <span className="fr-num fr-steel" style={{ fontWeight: 400 }}>{items.length}</span></h2>
      </div>
      <ul className="fr-watch-grid m-0 list-none p-0">
        {items.map((w) => {
          const r = byId.get(w.id);
          const g = r ? growthText(r.pct, locale) : null;
          return (
            <li key={w.id} className="fr-watch-item">
              <div className="min-w-0">
                <Link href={`/lab/f-report/m/${encodeURIComponent(w.id)}`} className="fr-name" prefetch={false}><span lang={langTag(w.lang)}>{w.name}</span></Link>
                <p className="fr-watch-meta m-0">
                  {r ? <>{stageLabel(locale, r.stage)}{g && g.dir !== "none" && <> · <span className={`fr-num ${g.dir === "up" ? "fr-signal" : ""}`}>{g.text}</span></>}</> : c(locale, "watchlist_not_here")}
                </p>
              </div>
              <div className="fr-watch-side">
                {r?.spark && r.spark.length > 1 ? <Sparkline values={r.spark} className={`fr-spark ${r.pct !== null && r.pct < 0 ? "fr-steel" : "fr-signal"}`} label={`${c(locale, "interest")} ${g?.text ?? ""}`} /> : null}
                <button type="button" className="fr-watch-remove" onClick={() => remove(w.id)}>{c(locale, "watchlist_remove")}</button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
