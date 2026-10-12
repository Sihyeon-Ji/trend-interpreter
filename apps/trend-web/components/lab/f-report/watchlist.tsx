"use client";

import Link from "next/link";
import { Suspense, use } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, riskLabel, stageLabel } from "@/lib/lab/f-report/copy";
import { fitClass, fmtDay, type Row } from "@/lib/lab/f-report";
import { Sparkline, growthText } from "./charts";
import { loadDetail, useMounted } from "./detail-client";
import { useWatchlist, type WatchItem } from "./watch";

const entryHref = (id: string) => `/lab/f-report/m/${encodeURIComponent(id)}`;

/** 홈의 '내가 지켜보는 밈' — 저장할 때 적어 둔 단계·리스크와 지금을 견준다. 고른 시장 목록에 있으면 증감·곡선도, 없으면 항목 요약을 받아 지금 상태만. */
export function Watchlist({ locale, rows }: { locale: Locale; rows: Row[] }) {
  const { items, remove } = useWatchlist();
  const mounted = useMounted();
  if (!items.length) return null;
  const byId = new Map(rows.map((r) => [r.id, r]));
  return (
    <section className="fr-watch" aria-labelledby="fr-watch-h">
      <div className="fr-section-head">
        <h2 id="fr-watch-h" className="fr-h2">{c(locale, "watchlist_title")} <span className="fr-num fr-steel font-normal">{items.length}</span></h2>
      </div>
      <ul className="fr-watch-list">
        {items.map((w) => {
          const r = byId.get(w.id);
          return (
            <li key={w.id} className="fr-watch-item">
              {r ? (
                <Known w={w} r={r} locale={locale} />
              ) : mounted ? (
                <Suspense fallback={<Pending w={w} locale={locale} />}><Fetched w={w} locale={locale} /></Suspense>
              ) : (
                <Pending w={w} locale={locale} />
              )}
              <button type="button" className="fr-watch-remove" onClick={() => remove(w.id)}>{c(locale, "watchlist_remove")}</button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Name({ w, locale }: { w: WatchItem; locale: Locale }) {
  return (
    <span className="fr-name-cell">
      <Link href={entryHref(w.id)} className={`fr-name fr-watch-name ${fitClass(w.name)}`} prefetch={false}><span lang={langTag(w.lang)}>{w.name}</span></Link>
      <span className="fr-watch-meta fr-num">{c(locale, "watchlist_saved")} {fmtDay(w.at)}</span>
    </span>
  );
}

/** 저장할 때와 지금 — 단계나 리스크가 달라졌으면 그 줄을, 같으면 '같음' */
function Diff({ w, stage, risk, locale }: { w: WatchItem; stage: string; risk: string | null; locale: Locale }) {
  const lines: React.ReactNode[] = [];
  if (w.stage && w.stage !== stage) lines.push(<span key="s">{c(locale, "watchlist_saved")} {stageLabel(locale, w.stage)} → <b>{c(locale, "watchlist_now")} {stageLabel(locale, stage)}</b></span>);
  if ((w.risk ?? null) !== (risk ?? null) && (w.risk !== undefined)) lines.push(<span key="r">{c(locale, "watchlist_saved")} {riskLabel(locale, w.risk)} → <b>{c(locale, "watchlist_now")} {riskLabel(locale, risk)}</b></span>);
  if (!lines.length && w.stage) lines.push(<span key="=" className="fr-steel">{c(locale, "watchlist_same")}</span>);
  return <span className="fr-watch-diff">{lines}</span>;
}

function Known({ w, r, locale }: { w: WatchItem; r: Row; locale: Locale }) {
  const g = growthText(r.pct, locale);
  return (
    <>
      <Name w={w} locale={locale} />
      <span className="fr-watch-spark">
        {r.spark ? <Sparkline values={r.spark} recent={r.sparkRecent} className={`fr-spark is-${g.dir}`} label={`${c(locale, "interest")} ${g.text}`} />
          : r.lastUsed ? <span className="fr-last fr-num">{c(locale, "last_used")} {fmtDay(r.lastUsed)}</span> : null}
      </span>
      <span className={`fr-change fr-num is-${g.dir}`}>{g.text}</span>
      <span className="fr-watch-stage">
        <span>{stageLabel(locale, r.stage)}{r.risk === "caution" && <span className="fr-mark is-caution ml-2">{c(locale, "risk_caution")}</span>}{r.risk === "avoid" && <span className="fr-mark is-avoid ml-2">{c(locale, "risk_avoid")}</span>}</span>
        <Diff w={w} stage={r.stage} risk={r.risk} locale={locale} />
      </span>
    </>
  );
}

function Pending({ w, locale }: { w: WatchItem; locale: Locale }) {
  return (
    <>
      <Name w={w} locale={locale} />
      <span />
      <span />
      <span className="fr-watch-stage fr-steel">{c(locale, "watchlist_loading")}</span>
    </>
  );
}

function Fetched({ w, locale }: { w: WatchItem; locale: Locale }) {
  const d = use(loadDetail(w.id, locale));
  if (!d) return <Pending w={w} locale={locale} />;
  return (
    <>
      <Name w={w} locale={locale} />
      <span className="fr-watch-spark fr-steel text-[12.5px]">{c(locale, "watchlist_not_here")}</span>
      <span />
      <span className="fr-watch-stage">
        <span>{stageLabel(locale, d.stage)}{d.risk === "caution" && <span className="fr-mark is-caution ml-2">{c(locale, "risk_caution")}</span>}{d.risk === "avoid" && <span className="fr-mark is-avoid ml-2">{c(locale, "risk_avoid")}</span>}</span>
        <Diff w={w} stage={d.stage} risk={d.risk} locale={locale} />
      </span>
    </>
  );
}
