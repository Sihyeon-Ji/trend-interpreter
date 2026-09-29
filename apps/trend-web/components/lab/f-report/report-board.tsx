"use client";

import Link from "next/link";
import { Suspense, use, useMemo, useState, useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, categoryLabel, diffusionLabel, regionName, riskLabel, stageLabel } from "@/lib/lab/f-report-copy";
import { fmtDay, type Row, type SourceRef } from "@/lib/lab/f-report";
import type { TermDetail } from "@/lib/lab/f-report-detail";
import type { KeywordList } from "@/lib/types";
import { GenCurves, Sparkline, growthText } from "./charts";
import { WatchButton } from "./watch-button";

interface Props {
  locale: Locale;
  lists: Record<KeywordList, Row[]>;
  totals: Record<KeywordList, number>;
  page: number;
  pageSize: number;
  initialList: KeywordList;
  q: string;
  regions: string[];
  hasCurves: boolean;
}

const LISTS: KeywordList[] = ["rising", "fading", "caution"];
const entryHref = (id: string) => `/lab/f-report/m/${encodeURIComponent(id)}`;

/** 순위 목록 + (넓은 화면) 미리보기. 행은 링크다 — 넓은 화면에서 보통 클릭은 미리보기에 띄우고, 새 탭·휴대폰은 항목 화면으로 간다. */
export function ReportBoard({ locale, lists, totals, page, pageSize, initialList, q, regions, hasCurves }: Props) {
  const [list, setList] = useState<KeywordList>(initialList);
  const [sort, setSort] = useState<"default" | "growth">("default");
  const [selected, setSelected] = useState<string | null>(lists[initialList][0]?.id ?? null);
  const rows = useMemo(() => {
    const base = lists[list];
    if (sort !== "growth") return base;
    return base.map((r, i) => ({ r, i })).sort((a, b) => (b.r.pct ?? -Infinity) - (a.r.pct ?? -Infinity) || a.i - b.i).map((x) => x.r);
  }, [lists, list, sort]);
  const rankOf = useMemo(() => new Map(lists[list].map((r, i) => [r.id, (page - 1) * pageSize + i + 1])), [lists, list, page, pageSize]);
  const all = useMemo(() => new Map(LISTS.flatMap((l) => lists[l]).map((r) => [r.id, r])), [lists]);
  const current = selected ? all.get(selected) ?? null : null;

  const pick = (l: KeywordList) => { setList(l); setSelected(lists[l][0]?.id ?? null); };
  const onRow = (e: React.MouseEvent, id: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    if (!window.matchMedia("(min-width: 1024px)").matches) return;
    e.preventDefault();
    setSelected(id);
  };

  const qs = (extra: Record<string, string>) => {
    const p = new URLSearchParams();
    if (regions.length) p.set("regions", regions.join(","));
    if (q) p.set("q", q);
    for (const [k, v] of Object.entries(extra)) p.set(k, v);
    return `/lab/f-report?${p}`;
  };
  const totalPages = Math.max(1, Math.ceil((totals[list] ?? 0) / pageSize));

  return (
    <div className="fr-board">
      <section aria-labelledby="fr-list-h">
        <h2 id="fr-list-h" className="sr-only">{c(locale, "col_name")}</h2>
        <div className="fr-tabs" role="tablist" aria-label={c(locale, "col_name")}>
          {LISTS.map((l) => (
            <button key={l} type="button" role="tab" id={`fr-tab-${l}`} aria-selected={list === l} aria-controls="fr-panel" className="fr-tab" onClick={() => pick(l)}>
              {c(locale, `tab_${l}`)}<span className="fr-num">{totals[l] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="fr-tools">
          {q ? (
            <span>
              <b className="text-[var(--fr-ink)] font-medium">‘{q}’</b> {c(locale, "search_result")} <span className="fr-num">{rows.length}</span>
              <span className="mx-2" aria-hidden>|</span>
              <Link href={qs({ q: "" }).replace(/[?&]q=(&|$)/, "$1").replace(/\?$/, "")} className="fr-link">{c(locale, "search_clear")}</Link>
              <span className="mx-2" aria-hidden>|</span>
              <Link href={`/dictionary?q=${encodeURIComponent(q)}`} className="fr-link">{c(locale, "search_more")}</Link>
            </span>
          ) : (
            <span>{hasCurves ? c(locale, "growth_vs") : null}</span>
          )}
          {hasCurves && (
            <span className="flex items-center gap-2">
              <span className="sr-only">{c(locale, "sort_label")}</span>
              <button type="button" className="fr-toggle" aria-pressed={sort === "default"} onClick={() => setSort("default")}>{c(locale, "sort_default")}</button>
              <button type="button" className="fr-toggle" aria-pressed={sort === "growth"} onClick={() => setSort("growth")}>{c(locale, "sort_growth")}</button>
            </span>
          )}
        </div>
        {!hasCurves && rows.length > 0 && <p className="fr-note">{c(locale, "no_curve_list")}</p>}
        <div id="fr-panel" role="tabpanel" aria-labelledby={`fr-tab-${list}`} className={hasCurves ? undefined : "no-curves"}>
          {rows.length > 0 && (
            <div className="fr-cols" aria-hidden>
              <span className="text-right">{c(locale, "col_rank")}</span><span>{c(locale, "col_name")}</span><span>{hasCurves ? c(locale, "col_trend") : ""}</span><span>{hasCurves ? c(locale, "col_change") : ""}</span><span>{c(locale, "col_stage")}</span>
            </div>
          )}
          {rows.length === 0 ? (
            <div className="fr-empty"><strong>{c(locale, "list_empty")}</strong>{c(locale, "list_empty_hint")}</div>
          ) : (
            <ol className="fr-list">
              {rows.map((r) => {
                const g = growthText(r.pct, locale);
                const sparkClass = `fr-spark ${g.dir === "down" ? "fr-steel" : "fr-signal"}`;
                return (
                  <li key={r.id}>
                    <Link href={entryHref(r.id)} className="fr-row" aria-current={selected === r.id ? "true" : undefined} onClick={(e) => onRow(e, r.id)} prefetch={false}>
                      <span className="fr-rank fr-num">{rankOf.get(r.id)}</span>
                      <span className="fr-name-cell">
                        <span className="fr-name">
                          <span lang={langTag(r.lang)}>{r.name}</span>
                          {r.isNew && <span className="fr-mark is-new">{c(locale, "new_mark")}</span>}
                          {r.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
                          {r.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
                        </span>
                        <span className="fr-gloss">{r.gloss}</span>
                      </span>
                      <span className="fr-row-desk">
                        <span>{r.spark && r.spark.length > 1 ? <Sparkline values={r.spark} className={sparkClass} label={`${c(locale, "interest")} ${g.text}`} /> : null}</span>
                        <span className={`fr-change fr-num is-${g.dir}`}>{hasCurves ? g.text : ""}</span>
                        <span className="fr-stage">{stageLabel(locale, r.stage)}</span>
                      </span>
                      <span className="fr-row-mobile">
                        {r.spark && r.spark.length > 1 ? <Sparkline values={r.spark} className={`${sparkClass} !h-[22px] !w-[76px]`} label={`${c(locale, "interest")} ${g.text}`} /> : null}
                        {hasCurves && g.dir !== "none" && <span className={`fr-change fr-num is-${g.dir}`}>{g.text}</span>}
                        <span className="fr-stage-mobile">{stageLabel(locale, r.stage)}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          )}
          {totalPages > 1 && !q && (
            <nav className="fr-pager" aria-label={c(locale, "page_of")}>
              <span>{page > 1 ? <Link href={qs({ page: String(page - 1), list })} className="fr-link">{c(locale, "prev_page")}</Link> : null}</span>
              <span className="fr-num fr-steel">{page} / {totalPages}</span>
              <span>{page < totalPages ? <Link href={qs({ page: String(page + 1), list })} className="fr-link">{c(locale, "more_page")}</Link> : null}</span>
            </nav>
          )}
        </div>
      </section>
      <aside className="fr-preview" aria-live="polite" aria-label={c(locale, "preview_open")}>
        {current ? <Preview row={current} locale={locale} /> : <p className="fr-preview-empty m-0">{c(locale, "preview_pick")}</p>}
      </aside>
    </div>
  );
}

/* ---- 미리보기: 카드가 이미 아는 것은 바로, 유래·쓰임·대표 장면은 항목 요약을 받아 채운다(약속을 id 마다 한 번만 만들어 use() 로 읽는다) ---- */
const detailPromises = new Map<string, Promise<TermDetail | null>>();
function loadDetail(id: string) {
  let p = detailPromises.get(id);
  if (!p) {
    p = fetch(`/lab/f-report/api/term/${encodeURIComponent(id)}`).then((r) => (r.ok ? (r.json() as Promise<TermDetail>) : null)).catch(() => null);
    detailPromises.set(id, p);
  }
  return p;
}
const noop = () => () => {};
/** 서버 렌더에서는 요약을 부르지 않는다(상대 주소 fetch 불가) — 물을 붙인 뒤에만 */
const useMounted = () => useSyncExternalStore(noop, () => true, () => false);

function Preview({ row, locale }: { row: Row; locale: Locale }) {
  const mounted = useMounted();
  const g = growthText(row.pct, locale);
  const canMake = row.risk !== "avoid";
  return (
    <article>
      <div className="flex flex-wrap items-center gap-2">
        <span className="fr-mark is-plain">{categoryLabel(locale, row.category)}</span>
        {row.isNew && <span className="fr-mark is-new">{c(locale, "new_mark")}</span>}
        {row.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
        {row.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
      </div>
      <h3 className="fr-preview-name" lang={langTag(row.lang)}>{row.name}</h3>
      <p className="fr-preview-gloss">{row.gloss}</p>
      <div className="fr-preview-actions">
        {canMake ? <Link href={`/recommend?term=${encodeURIComponent(row.id)}`} className="fr-btn is-primary">{c(locale, "make")}</Link> : null}
        <WatchButton item={{ id: row.id, name: row.name, lang: row.lang }} locale={locale} />
        <Link href={entryHref(row.id)} className="fr-btn" prefetch={false}>{c(locale, "preview_open")}</Link>
      </div>
      {!canMake && <p className="fr-steel m-0 mt-2 text-[13px]">{c(locale, "make_blocked")}</p>}

      <dl className="fr-facts">
        <dt>{c(locale, "stage")}</dt>
        <dd>{stageLabel(locale, row.stage)}{diffusionLabel(locale, row.diffusion) ? <span className="fr-steel"> · {diffusionLabel(locale, row.diffusion)}</span> : null}</dd>
        <dt>{c(locale, "risk")}</dt>
        <dd>
          {riskLabel(locale, row.risk)}
          {row.riskReasons.length > 0 && <ul className="m-0 mt-1 list-disc pl-4 text-[13px] leading-[1.5] fr-steel">{row.riskReasons.map((r) => <li key={r}>{r}</li>)}</ul>}
        </dd>
        <dt>{c(locale, "regions")}</dt>
        <dd>{row.regions.length ? row.regions.map((r) => regionName(locale, r)).join(", ") : "—"}</dd>
        <dt>{c(locale, "last_seen")}</dt>
        <dd className="fr-num">{row.lastSeen ? fmtDay(row.lastSeen) : "—"}</dd>
        {!row.byGen && <><dt>{c(locale, "interest")}</dt><dd className="fr-steel">{c(locale, "no_curve_row")}</dd></>}
      </dl>

      {row.byGen && (
        <div className="fr-block">
          <h3>{c(locale, "interest")}</h3>
          <p className="fr-num"><span className={g.dir === "up" ? "fr-signal font-semibold" : "font-semibold"}>{g.text}</span> <span className="fr-steel text-[13px]">{c(locale, "growth_vs")}</span></p>
          <GenCurves byGen={row.byGen} locale={locale} />
          <p className="fr-steel mt-2 text-[12.5px]">{c(locale, "interest_note")}</p>
        </div>
      )}

      {mounted ? (
        <Suspense fallback={<PreviewLoading locale={locale} />}>
          <PreviewDetail row={row} locale={locale} />
        </Suspense>
      ) : (
        <PreviewLoading locale={locale} />
      )}
    </article>
  );
}

function PreviewLoading({ locale }: { locale: Locale }) {
  return <div className="fr-block"><h3>{c(locale, "origin")}</h3><p className="fr-steel">{c(locale, "loading_more")}</p></div>;
}

/** 나중에 오는 부분: 다른 표기·유래·이렇게 써요·대표 장면·출처 */
function PreviewDetail({ row, locale }: { row: Row; locale: Locale }) {
  const detail = use(loadDetail(row.id));
  const text = detail ? (locale === "en" ? detail.en ?? detail.ko : detail.ko ?? detail.en) : null;
  const sources = mergeSources(row.sources, detail?.sources ?? []).slice(0, 5);
  const media = detail?.video ?? null;
  return (
    <>
      {detail && detail.aliases.length > 0 && (
        <p className="fr-steel m-0 mt-3 text-[13px]">{c(locale, "aliases")}: <span lang={langTag(detail.lang)}>{detail.aliases.join(", ")}</span></p>
      )}
      {media && (
        <div className="fr-block">
          <h3>{c(locale, "entry_media")}</h3>
          <a href={media.url} target="_blank" rel="noopener noreferrer" className="fr-media">
            {/* eslint-disable-next-line @next/next/no-img-element -- 유튜브 썸네일은 밖의 주소만 쓰고 저장하지 않는다 */}
            <img src={media.thumb} alt={media.title} loading="lazy" />
          </a>
        </div>
      )}
      <div className="fr-block">
        <h3>{c(locale, "origin")}</h3>
        {text?.origin ? <p>{text.origin}</p> : <p className="fr-steel">{c(locale, "entry_no_origin")}</p>}
      </div>
      {(text?.plain || text?.nuance) && (
        <div className="fr-block">
          <h3>{c(locale, "usage_how")}</h3>
          {text?.plain && text.plain !== text.definition && <p className="mb-2 font-medium">“{text.plain}”</p>}
          {text?.nuance && <p>{text.nuance}</p>}
        </div>
      )}
      {sources.length > 0 && (
        <div className="fr-block">
          <h3>{c(locale, "sources")}</h3>
          <SourceList sources={sources} locale={locale} />
        </div>
      )}
    </>
  );
}

function mergeSources(a: SourceRef[], b: SourceRef[]) {
  const seen = new Set<string>();
  return [...a, ...b].filter((s) => (seen.has(s.url) ? false : (seen.add(s.url), true)));
}

export function SourceList({ sources, locale }: { sources: SourceRef[]; locale: Locale }) {
  return (
    <ul className="fr-src">
      {sources.map((s) => (
        <li key={s.url}>
          <span className="fr-kind">{c(locale, `kind_${s.kind}` as "kind_wiki")}</span>
          <a href={s.url} target="_blank" rel="noopener noreferrer" title={s.title}>{s.title || s.domain}</a>
          <time className="fr-num" dateTime={s.at}>{fmtDay(s.at)}</time>
        </li>
      ))}
    </ul>
  );
}
