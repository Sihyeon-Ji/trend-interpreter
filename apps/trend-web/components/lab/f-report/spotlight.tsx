import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, stageLabel } from "@/lib/lab/f-report-copy";
import { fmtDay, type Row } from "@/lib/lab/f-report";
import { AreaCurve, growthText } from "./charts";

/** 이번 주 주목 셋 — 낱말이 곧 그림인 타일. 영상 썸네일이 있을 때만 그림이 위에 앉는다. */
export function Spotlight({ rows, curves, byGrowth, locale }: { rows: Row[]; curves: Record<string, number[]>; byGrowth: boolean; locale: Locale }) {
  if (!rows.length) return null;
  return (
    <section aria-labelledby="fr-spot">
      <div className="fr-section-head">
        <h2 id="fr-spot" className="fr-h2">{c(locale, "spotlight_title")}</h2>
        <p className="fr-sub m-0">{byGrowth ? c(locale, "spotlight_by_growth") : c(locale, "spotlight_by_rank")}</p>
      </div>
      <ol className="fr-tiles m-0 list-none p-0">
        {rows.map((r) => {
          const g = growthText(r.pct, locale);
          const curve = curves[r.id];
          const hasChart = !!curve && curve.length > 1;
          return (
            <li key={r.id} className="min-w-0">
              <Link href={`/lab/f-report/m/${encodeURIComponent(r.id)}`} className={`fr-tile${r.thumb ? " has-thumb" : ""}${hasChart ? "" : " no-chart"}`} prefetch={false}>
                {r.thumb && (
                  // eslint-disable-next-line @next/next/no-img-element -- 유튜브 썸네일은 밖의 주소만 쓰고 저장하지 않는다
                  <img src={r.thumb} alt="" className="fr-tile-thumb" loading="lazy" />
                )}
                <div className="fr-tile-body">
                  {r.isNew && <span className="fr-tile-rank">{c(locale, "new_mark")}</span>}
                  <h3 className="fr-tile-name" lang={langTag(r.lang)}>{r.name}</h3>
                  <p className="fr-tile-gloss">{r.gloss}</p>
                </div>
                <div className="fr-tile-foot">
                  {r.pct !== null && g.dir !== "none" ? (
                    <span className="fr-tile-growth fr-num">{g.text}<small>{c(locale, "spotlight_growth")}</small></span>
                  ) : (
                    <span className="fr-tile-stage">{stageLabel(locale, r.stage)}{r.lastSeen && <span className="fr-tile-meta fr-num">{c(locale, "last_seen")} {fmtDay(r.lastSeen)}</span>}</span>
                  )}
                  {r.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
                  {r.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
                </div>
                {hasChart ? (
                  <AreaCurve values={curve} className="fr-tile-chart fr-signal" label={`${c(locale, "interest")}: ${g.text}`} />
                ) : (
                  <div className="fr-hero-pad" aria-hidden />
                )}
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
