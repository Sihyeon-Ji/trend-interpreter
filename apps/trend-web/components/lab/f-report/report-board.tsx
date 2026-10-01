"use client";

import Link from "next/link";
import { Suspense, use, useMemo, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c, categoryLabel, diffusionLabel, kindLabel, regionName, riskLabel, stageLabel } from "@/lib/lab/f-report/copy";
import { fitClass, fmtDay, type RiskNote, type Row, type SourceRef } from "@/lib/lab/f-report";
import type { KeywordList } from "@/lib/types";
import { GenCurves, Sparkline, growthText } from "./charts";
import { loadDetail, useMounted } from "./detail-client";
import { WatchButton } from "./watch-button";

interface Props {
  locale: Locale;
  lists: Record<KeywordList, Row[]>;
  totals: Record<KeywordList, number>;
  page: number;
  pageSize: number;
  initialList: KeywordList;
  q: string;
  regionsParam: string;
  hasCurves: boolean;      // 이 리포트에 검색 곡선이 하나라도 있나(한국이 들어 있을 때만)
}

const LISTS: KeywordList[] = ["rising", "fading", "caution"];
const entryHref = (id: string) => `/lab/f-report/m/${encodeURIComponent(id)}`;

/** 순위 목록 + (넓은 화면) 미리보기. 행은 링크다 — 넓은 화면에서 보통 클릭은 미리보기에 띄우고, 새 탭·휴대폰은 항목 화면으로 간다.
 *  순위 숫자는 '늘어난 순' 일 때만 — 기본 순은 백엔드 규칙(퍼진 정도 → 단계 → 언급 → 최근 쓰임)의 순서라 순위라 부르지 않는다. */
export function ReportBoard({ locale, lists, totals, page, pageSize, initialList, q, regionsParam, hasCurves }: Props) {
  const [list, setList] = useState<KeywordList>(initialList);
  const [sort, setSort] = useState<"default" | "growth">("default");
  const [selected, setSelected] = useState<string | null>(lists[initialList][0]?.id ?? null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const rows = useMemo(() => {
    const base = lists[list];
    if (sort !== "growth") return base;
    return base.map((r, i) => ({ r, i })).sort((a, b) => (b.r.pct ?? -Infinity) - (a.r.pct ?? -Infinity) || a.i - b.i).map((x) => x.r);
  }, [lists, list, sort]);
  const ranked = sort === "growth" && hasCurves;
  const rankOf = useMemo(() => { let n = 0; return new Map(rows.map((r) => [r.id, r.pct === null ? null : ++n])); }, [rows]);
  const all = useMemo(() => new Map(LISTS.flatMap((l) => lists[l]).map((r) => [r.id, r])), [lists]);
  const current = selected ? all.get(selected) ?? null : null;
  const someMissing = hasCurves && rows.some((r) => !r.spark);

  const pick = (l: KeywordList) => { setList(l); setSelected(lists[l][0]?.id ?? null); };
  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    const n = LISTS.length;
    const j = e.key === "ArrowRight" ? (i + 1) % n : e.key === "ArrowLeft" ? (i - 1 + n) % n : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : -1;
    if (j < 0) return;
    e.preventDefault();
    pick(LISTS[j]);
    tabRefs.current[j]?.focus();
  };
  const onRow = (e: React.MouseEvent, id: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    if (!window.matchMedia("(min-width: 1024px)").matches) return;
    e.preventDefault();
    setSelected(id);
  };

  const qs = (extra: Record<string, string>) => {
    const p = new URLSearchParams();
    if (regionsParam) p.set("regions", regionsParam);
    if (q) p.set("q", q);
    for (const [k, v] of Object.entries(extra)) if (v) p.set(k, v); else p.delete(k);
    return `/lab/f-report${p.size ? `?${p}` : ""}`;
  };
  const totalPages = Math.max(1, Math.ceil((totals[list] ?? 0) / pageSize));

  return (
    <div className="fr-board">
      <section aria-labelledby="fr-list-h">
        <h2 id="fr-list-h" className="sr-only">{c(locale, "col_name")}</h2>
        <div className="fr-tabs" role="tablist" aria-label={c(locale, "col_name")}>
          {LISTS.map((l, i) => (
            <button key={l} type="button" role="tab" id={`fr-tab-${l}`} aria-selected={list === l} aria-controls="fr-panel" tabIndex={list === l ? 0 : -1}
              ref={(el) => { tabRefs.current[i] = el; }} className="fr-tab" onClick={() => pick(l)} onKeyDown={(e) => onTabKey(e, i)}>
              {c(locale, `tab_${l}`)}<span className="fr-num">{totals[l] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="fr-tools">
          {q ? (
            <span>
              <b className="text-[var(--fr-ink)] font-medium">‘{q}’</b> {c(locale, "search_result")} <span className="fr-num">{rows.length}</span>
              <span className="mx-2" aria-hidden>|</span>
              <Link href={qs({ q: "" })} className="fr-link">{c(locale, "search_clear")}</Link>
              <span className="mx-2" aria-hidden>|</span>
              <Link href={`/dictionary?q=${encodeURIComponent(q)}`} className="fr-link">{c(locale, "search_more")}</Link>
            </span>
          ) : (
            <span>{hasCurves ? (sort === "growth" ? c(locale, "sort_growth_note") : c(locale, "sort_default_note")) : null}</span>
          )}
          {hasCurves && (
            <span className="fr-sort">
              <span className="sr-only">{c(locale, "sort_label")}</span>
              <button type="button" aria-pressed={sort === "default"} onClick={() => setSort("default")}>{c(locale, "sort_default")}</button>
              <button type="button" aria-pressed={sort === "growth"} onClick={() => setSort("growth")}>{c(locale, "sort_growth")}</button>
            </span>
          )}
        </div>
        {rows.length > 0 && !hasCurves && <p className="fr-note">{c(locale, "no_curve_list")}</p>}
        {rows.length > 0 && someMissing && <p className="fr-note">{c(locale, "no_curve_some")}</p>}
        <div id="fr-panel" role="tabpanel" aria-labelledby={`fr-tab-${list}`} className={`${hasCurves ? "" : "no-curves"}${ranked ? " has-rank" : ""}`}>
          {rows.length > 0 && (
            <div className="fr-cols" aria-hidden>
              {ranked && <span className="text-right">{c(locale, "col_rank")}</span>}
              <span>{c(locale, "col_name")}</span>
              {hasCurves ? <><span>{c(locale, "col_trend")}</span><span className="text-right">{c(locale, "col_change")}</span></> : <span>{c(locale, "col_last")}</span>}
              <span>{c(locale, "col_stage")}</span>
            </div>
          )}
          {rows.length === 0 ? (
            <div className="fr-empty"><strong>{c(locale, "list_empty")}</strong>{c(locale, "list_empty_hint")}</div>
          ) : (
            <ol className="fr-list">
              {rows.map((r) => {
                const g = growthText(r.pct, locale);
                const last = r.lastUsed ? fmtDay(r.lastUsed) : "";
                const spark = r.spark ? <Sparkline values={r.spark} recent={r.sparkRecent} className={`fr-spark is-${g.dir}`} label={`${c(locale, "interest")} ${g.text}`} /> : null;
                return (
                  <li key={r.id}>
                    <Link href={entryHref(r.id)} className="fr-row" aria-current={selected === r.id ? "true" : undefined} onClick={(e) => onRow(e, r.id)} prefetch={false}>
                      {ranked && <span className="fr-rank fr-num">{rankOf.get(r.id) ?? ""}</span>}
                      <span className="fr-name-cell">
                        <span className="fr-name">
                          <span lang={langTag(r.lang)}>{r.name}</span>
                          {r.isNew && <span className="fr-mark is-new">{c(locale, "new_mark")}</span>}
                          {r.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
                          {r.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
                        </span>
                        <span className="fr-gloss" lang={r.glossLang}>{r.gloss}</span>
                      </span>
                      <span className="fr-row-desk">
                        {hasCurves ? (
                          <>
                            <span>{spark ?? <span className="fr-last fr-num" title={r.stale ? c(locale, "stale_note") : undefined}>{last && `${c(locale, "last_used")} ${last}`}</span>}</span>
                            <span className={`fr-change fr-num is-${g.dir}`}>{g.text}</span>
                          </>
                        ) : (
                          <span className="fr-last fr-num">{last}</span>
                        )}
                        <span className="fr-stage">{stageLabel(locale, r.stage)}</span>
                      </span>
                      <span className="fr-row-mobile">
                        {spark ? <Sparkline values={r.spark!} recent={r.sparkRecent} className={`fr-spark is-${g.dir} !h-[22px] !w-[76px]`} label={`${c(locale, "interest")} ${g.text}`} /> : null}
                        {g.dir !== "none" ? <span className={`fr-change fr-num is-${g.dir}`}>{g.text}</span> : last ? <span className="fr-last fr-num">{last}</span> : null}
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
      <aside className="fr-preview" aria-label={c(locale, "preview_of")}>
        <p className="sr-only" aria-live="polite">{current ? `${c(locale, "preview_of")}: ${current.name}` : ""}</p>
        {current ? <Preview row={current} locale={locale} /> : <p className="fr-preview-empty m-0">{c(locale, "preview_pick")}</p>}
      </aside>
    </div>
  );
}

/** 쓸 때 조심의 이유 — 사전 뜻풀이의 주의점은 인용으로(사전의 글이다) */
export function RiskNotes({ notes }: { notes: RiskNote[] }) {
  if (!notes.length) return null;
  return (
    <ul className="fr-risk-notes">
      {notes.map((n) => <li key={n.text + (n.quote ?? "")}>{n.text}{n.quote && <q className="fr-risk-quote" lang="ko">{n.quote}</q>}</li>)}
    </ul>
  );
}

/* ---- 미리보기: 카드가 이미 아는 것은 바로, 유래·쓰임·대표 장면은 항목 요약을 받아 채운다 ---- */
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
      <h3 className={`fr-preview-name ${fitClass(row.name)}`} lang={langTag(row.lang)}>{row.name}</h3>
      <p className="fr-preview-gloss" lang={row.glossLang}>{row.gloss}</p>
      <div className="fr-preview-actions">
        {canMake ? <Link href={`/recommend?term=${encodeURIComponent(row.id)}`} className="fr-btn is-primary">{c(locale, "make")}</Link> : null}
        <WatchButton item={{ id: row.id, name: row.name, lang: row.lang, stage: row.stage, risk: row.risk }} locale={locale} />
        <Link href={entryHref(row.id)} className="fr-btn" prefetch={false}>{c(locale, "preview_open")}</Link>
      </div>
      {!canMake && <p className="fr-steel m-0 mt-2 text-[13px]">{c(locale, "make_blocked")}</p>}

      <dl className="fr-facts">
        <dt>{c(locale, "stage")}</dt>
        <dd>{stageLabel(locale, row.stage)}</dd>
        {diffusionLabel(locale, row.diffusion) && <><dt>{c(locale, "spread")}</dt><dd>{diffusionLabel(locale, row.diffusion)}</dd></>}
        <dt>{c(locale, "risk")}</dt>
        <dd>{riskLabel(locale, row.risk)}<RiskNotes notes={row.riskNotes} /></dd>
        <dt>{c(locale, "regions")}</dt>
        <dd>{row.regions.length ? row.regions.map((r) => regionName(locale, r)).join(", ") : "—"}</dd>
        <dt>{c(locale, "last_used")}</dt>
        <dd className="fr-num">{row.lastUsed ? fmtDay(row.lastUsed) : "—"}</dd>
        {!row.byGen && <><dt>{c(locale, "interest")}</dt><dd className="fr-steel">{c(locale, "no_data")}</dd></>}
      </dl>

      {row.byGen && (
        <div className="fr-block">
          <h3>{c(locale, "interest")}</h3>
          {row.pct !== null ? (
            <p className="fr-num"><span className={`font-semibold is-${g.dir} fr-change`}>{g.text}</span> <span className="fr-steel text-[13px]">{c(locale, "growth_vs")}</span></p>
          ) : (
            <p className="fr-steel text-[13.5px]">{row.stale ? c(locale, "stale_note") : c(locale, "interest_thin")}</p>
          )}
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
  const detail = use(loadDetail(row.id, locale));
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
          <span className="fr-kind">{kindLabel(locale, s.kind)}</span>
          <a href={s.url} target="_blank" rel="noopener noreferrer" title={s.title}>{s.title}</a>
          <span className="fr-src-name">{s.name}{s.license ? ` (${s.license})` : ""}</span>
          <time className="fr-num" dateTime={s.at}>{fmtDay(s.at)}</time>
        </li>
      ))}
    </ul>
  );
}
