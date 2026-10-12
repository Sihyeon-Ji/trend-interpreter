import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, stageLabel } from "@/lib/lab/f-report/copy";
import { fitClass, fmtDay, type Row } from "@/lib/lab/f-report";
import { Ground, growthText } from "./charts";

export interface SpotCurve { values: number[]; recent: number; base: number }

/** 이번 주 주목 셋 — 낱말이 제 검색 곡선 위에 선 타일. 곡선의 진한 부분이 최근 4주, 옅은 부분이 그 전 4주라 무엇을 견줬는지 곡선이 말한다.
 *  곡선이 없는 시장(일본·동남아)은 단계와 마지막 쓰임으로, 영상 썸네일이 있으면(드물다) 이름 위에 앉는다. */
export function Spotlight({ rows, curves, byGrowth, locale }: { rows: Row[]; curves: Record<string, SpotCurve>; byGrowth: boolean; locale: Locale }) {
  if (!rows.length) return null;
  return (
    <section aria-labelledby="fr-spot" className="fr-spot">
      <div className="fr-section-head">
        <h2 id="fr-spot" className="fr-h2">{c(locale, "spotlight_title")}</h2>
        <p className="fr-sub m-0">{byGrowth ? c(locale, "spotlight_by_growth") : c(locale, "spotlight_by_rank")}</p>
      </div>
      <ol className="fr-tiles m-0 list-none p-0">
        {rows.map((r) => {
          const g = growthText(r.pct, locale);
          const curve = curves[r.id];
          const hasChart = !!curve && curve.values.length > 1 && r.pct !== null;
          return (
            <li key={r.id} className="min-w-0">
              <Link href={`/lab/f-report/m/${encodeURIComponent(r.id)}`} className={`fr-tile${r.thumb ? " has-thumb" : ""}${hasChart ? "" : " no-chart"}`} prefetch={false}>
                {r.thumb && (
                  // eslint-disable-next-line @next/next/no-img-element -- 유튜브 썸네일은 밖의 주소만 쓰고 저장하지 않는다
                  <img src={r.thumb} alt="" className="fr-tile-thumb" loading="lazy" />
                )}
                <div className="fr-tile-body">
                  <div className="fr-tile-marks">
                    {r.isNew && <span className="fr-mark is-new">{c(locale, "new_mark")}</span>}
                    {r.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
                    {r.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
                  </div>
                  <h3 className={`fr-tile-name ${fitClass(r.name)}`} lang={langTag(r.lang)}>{r.name}</h3>
                  <p className="fr-tile-gloss" lang={r.glossLang}>{r.gloss}</p>
                </div>
                <div className="fr-tile-foot">
                  <span className="fr-tile-stage">
                    {r.list === "fading" && r.pct !== null && r.pct > 0 ? c(locale, "spotlight_fading") : stageLabel(locale, r.stage)}
                    {!hasChart && r.lastUsed && <span className="fr-tile-meta fr-num">{c(locale, "last_used")} {fmtDay(r.lastUsed)}</span>}
                  </span>
                  {hasChart && g.dir !== "none" && (
                    <span className={`fr-tile-growth fr-num is-${g.dir}`}>{g.text}<small>{c(locale, "spotlight_growth")}</small></span>
                  )}
                </div>
                {hasChart ? (
                  <Ground values={curve.values} recent={curve.recent} base={curve.base} className="fr-tile-chart" label={`${c(locale, "interest")}: ${g.text}`} />
                ) : (
                  <div className="fr-tile-floor" aria-hidden />
                )}
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
