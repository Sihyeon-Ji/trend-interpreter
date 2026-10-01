"use client";

/* 목록 + 오른쪽 미리보기. 목록이 일꾼이다: 밈(원문 + 뜻 한 줄) · 검색 추이 · 증감 · 단계, 쓸 때 조심은 주의·사용 자제일 때만.
   '쓰이는 밈' 은 기본 순(백엔드 순서)이 먼저다 — 늘어난 순위는 위 표지 셋이 맡고, 같은 1·2·3 을 두 번 늘어놓지 않는다(09-29 검토).
   '검색 증가 순' 을 누르면 증가 순위와 순위 변화 칸이 선다. '조심할 밈' 은 판정 장부(수준 · 밈과 이유 · 단계)다.
   데스크톱(1024px 이상)에서 줄을 누르면 오른쪽에서 미리 보고(사전 항목은 그때 받는다), 휴대폰에서는 줄이 곧 항목 화면 링크다.
   탭·정렬·고른 밈은 주소에도 적어 둔다(history.replaceState) — 새로 고치거나 링크를 보내도 같은 화면. */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { fmtDay, type Change, type ListKey, type Preview, type RiskKey, type Row, type SortKey, type Weeks } from "@/lib/lab/o-report";
import type { Lifecycle } from "@/lib/contract/types";
import { riskWord, spreadWord, stageWord, tr, type CopyKey } from "@/lib/lab/o-report/copy";
import { scriptLang } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import { Growth, RankChange, RiskMark, RiskNotes, Tag } from "./bits";
import { Sparkline, WeeklyBars } from "./charts";
import { afterVisit } from "./since-visit";
import { diffOf, nowOf, toggleWatch, useLastVisit, useOutsideStates, useWatchlist, type Watched, type WatchDiff } from "./store";

interface Props {
  locale: Locale;
  lists: { rising: Row[]; fading: Row[]; caution: Row[] };
  totals: { rising: number; fading: number; caution: number };
  previews: Record<string, Preview>;   // 처음 고른 밈 하나(서버가 그린다)
  searchable: boolean;
  weeks: Weeks;
  ranked: number;                      // 쓰이는 밈 가운데 증가 순위를 매긴 수
  regionsParam: string;                // 주소의 regions 값 ('' = 한국 기본)
  page: number;
  pageSize: number;
  initialTab: ListKey;
  initialSort: SortKey;
  initialSelected: string | null;
  changes: Change[];
  keep: string;                        // 쪽 링크에 이어 붙일 주소 조각 (regions, w)
  refAt: string;                       // 날짜에 해를 붙일지 정하는 기준 시각(보드 갱신 시각)
}

const TABS: ListKey[] = ["rising", "fading", "caution", "watch"];
const DESKTOP = "(min-width: 1024px)";
const isDesktop = () => window.matchMedia(DESKTOP).matches;

export function Board(p: Props) {
  const { locale, lists, searchable, weeks } = p;
  const watch = useWatchlist();
  const last = useLastVisit();
  const [tab, setTab] = useState<ListKey>(p.initialTab);
  const [sort, setSort] = useState<SortKey>(p.initialSort);
  const [picked, setPicked] = useState<string | null>(p.initialSelected);
  const [previews, setPreviews] = useState<Record<string, Preview | "failed">>(p.previews);
  const requested = useRef<Set<string>>(new Set(Object.keys(p.previews)));
  const hoverTimer = useRef<number | null>(null);

  const all = useMemo(() => {
    const m = new Map<string, Row>();
    for (const r of [...lists.rising, ...lists.fading, ...lists.caution]) if (!m.has(r.id)) m.set(r.id, r);
    return m;
  }, [lists]);
  const outside = useOutsideStates(watch, (id) => all.has(id), locale);

  const canRank = searchable && p.ranked > 0;
  const gain = sort === "gain" && canRank;
  const risingRows = useMemo(() => {
    if (!gain) return lists.rising;
    const ranked = lists.rising.filter((r) => r.rank != null).sort((a, b) => a.rank! - b.rank!);
    return [...ranked, ...lists.rising.filter((r) => r.rank == null)];
  }, [gain, lists.rising]);

  const watchedRows = watch.map((w) => all.get(w.id)).filter((r): r is Row => !!r);
  const watchedElsewhere = watch.filter((w) => !all.has(w.id));
  const rows = tab === "watch" ? watchedRows : tab === "rising" ? risingRows : lists[tab];
  const selectedId = picked && all.has(picked) ? picked : rows[0]?.id ?? lists.rising[0]?.id ?? null;
  const selected = selectedId ? all.get(selectedId) ?? null : null;

  const fresh = p.changes.filter((c) => afterVisit(c.at, last));
  const newIds = new Set(fresh.filter((c) => c.kind === "verified").map((c) => c.id));
  const changedIds = new Set(fresh.filter((c) => c.kind === "meaning_changed").map((c) => c.id));

  /* 미리보기는 누를 때 받는다(같은 사이트의 읽기 전용 경로). 한 번 받은 것은 이 화면에 둔다 */
  const load = useCallback((id: string) => {
    if (requested.current.has(id)) return;
    requested.current.add(id);
    fetch(`/lab/o-report/api/preview/${encodeURIComponent(id)}?locale=${locale}`)
      .then((r) => (r.ok ? (r.json() as Promise<Preview>) : Promise.reject(new Error(String(r.status)))))
      .then((pv) => setPreviews((c) => ({ ...c, [id]: pv })))
      .catch(() => { requested.current.delete(id); setPreviews((c) => ({ ...c, [id]: "failed" })); });
  }, [locale]);

  useEffect(() => { if (selectedId && isDesktop()) load(selectedId); }, [selectedId, load]);

  // 머리의 '조심해야 해요' · 지난 방문 줄의 '지켜보는 밈' 이 이 탭을 연다
  useEffect(() => {
    const on = (e: Event) => {
      const k = (e as CustomEvent<ListKey>).detail;
      if (!TABS.includes(k)) return;
      setTab(k);
      const u = new URL(window.location.href);
      if (k === "rising") u.searchParams.delete("tab"); else u.searchParams.set("tab", k);
      window.history.replaceState(null, "", u);
    };
    window.addEventListener("or-tab", on);
    return () => window.removeEventListener("or-tab", on);
  }, []);

  const writeUrl = (next: { tab?: ListKey; m?: string | null; sort?: SortKey }) => {
    const u = new URL(window.location.href);
    const t = next.tab ?? tab;
    if (t === "rising") u.searchParams.delete("tab"); else u.searchParams.set("tab", t);
    const s = next.sort ?? sort;
    if (s === "gain") u.searchParams.set("sort", "gain"); else u.searchParams.delete("sort");
    const m = next.m === undefined ? picked : next.m;
    if (m) u.searchParams.set("m", m); else u.searchParams.delete("m");
    window.history.replaceState(null, "", u);
  };

  const chooseTab = (t: ListKey) => { setTab(t); writeUrl({ tab: t }); };
  const chooseSort = (e: React.MouseEvent, s: SortKey) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    setSort(s);
    writeUrl({ sort: s });
  };
  const onRow = (e: React.MouseEvent, id: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (!isDesktop()) return;      // 휴대폰은 링크 그대로 항목 화면으로
    e.preventDefault();
    if (previews[id] === "failed") setPreviews((c) => { const next = { ...c }; delete next[id]; return next; });
    setPicked(id);
    writeUrl({ m: id });
  };
  // 마우스를 잠깐 올려 두면 미리 받아 둔다 — 눌렀을 때 바로 보이게
  const hoverIn = (id: string) => {
    if (!isDesktop()) return;
    if (hoverTimer.current) window.clearTimeout(hoverTimer.current);
    hoverTimer.current = window.setTimeout(() => load(id), 150);
  };
  const hoverOut = () => { if (hoverTimer.current) { window.clearTimeout(hoverTimer.current); hoverTimer.current = null; } };

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = TABS[(i + dir + TABS.length) % TABS.length];
    chooseTab(next);
    document.getElementById(`or-tab-${next}`)?.focus();
  };

  const q = p.regionsParam ? `?regions=${encodeURIComponent(p.regionsParam)}` : "";
  const entry = (id: string) => `/lab/o-report/m/${encodeURIComponent(id)}${q}`;
  const count = (t: ListKey) => (t === "watch" ? watch.length : p.totals[t]);
  const ranked = tab === "rising" && gain ? rows.filter((r) => r.rank != null) : [];
  const rest = tab === "rising" && gain ? rows.filter((r) => r.rank == null) : rows;
  const pages = tab === "fading" || tab === "caution" ? Math.ceil(p.totals[tab] / p.pageSize) : 1;
  const diffFor = (w: Watched) => diffOf(w, nowOf(w.id, all, outside.outside), p.changes);

  // 칸: (증가 순위) | 밈 | 추이 | 증감 | 단계. 증가 순위 칸은 '검색 증가 순' 일 때만 선다(다른 목록에 빈 칸을 남기지 않게).
  // 검색 자료가 없는 지역은 추이·증감 대신 '마지막 쓰임' 날짜. 1024–1279px 은 미리보기와 폭을 나눠 쓰므로 단계를 뜻 아래 한 줄로 둔다.
  const showRank = tab === "rising" && gain;
  const cols = showRank
    ? "grid-cols-[36px_minmax(0,1fr)_auto] sm:grid-cols-[48px_minmax(0,1fr)_120px_76px_96px] lg:grid-cols-[44px_minmax(0,1fr)_104px_68px] xl:grid-cols-[48px_minmax(0,1fr)_120px_76px_96px]"
    : searchable
      ? "grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_120px_76px_96px] lg:grid-cols-[minmax(0,1fr)_104px_68px] xl:grid-cols-[minmax(0,1fr)_120px_76px_96px]"
      : "grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_112px_96px] lg:grid-cols-[minmax(0,1fr)_104px] xl:grid-cols-[minmax(0,1fr)_112px_96px]";
  const ledger = "grid-cols-[minmax(0,1fr)] sm:grid-cols-[104px_minmax(0,1fr)_104px] lg:grid-cols-[96px_minmax(0,1fr)] xl:grid-cols-[104px_minmax(0,1fr)_104px]";

  const nameLine = (r: Row, lead?: React.ReactNode, trail?: React.ReactNode) => (
    <span className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
      {lead}
      <span lang={r.lang} className="or-row-name truncate text-[16px] leading-[1.35] font-bold">{r.name}</span>
      {r.reading && <span lang={r.readingLang} className="text-[13px] text-[var(--or-slate)]">{r.reading}</span>}
      {newIds.has(r.id) && <Tag kind="new" locale={locale} />}
      {changedIds.has(r.id) && <Tag kind="changed" locale={locale} />}
      {trail}
    </span>
  );

  const rowProps = (r: Row) => ({
    href: entry(r.id), prefetch: false as const,
    onClick: (e: React.MouseEvent) => onRow(e, r.id),
    onPointerEnter: () => hoverIn(r.id), onPointerLeave: hoverOut, onFocus: () => hoverIn(r.id),
  });

  const line = (r: Row, extra?: React.ReactNode) => (
    <li key={r.id} className="or-row" aria-current={r.id === selectedId ? "true" : undefined}>
      <Link {...rowProps(r)} className={`or-row-link grid ${cols} items-center gap-x-3 py-3.5 pr-1 pl-3 sm:gap-x-4`}>
        {showRank && (
          <span className="flex flex-col items-start gap-1 self-start pt-0.5">
            {r.rank != null && <span className="or-num text-[21px] leading-none font-bold">{r.rank}</span>}
            {r.rank != null && <RankChange n={r.rankChange} locale={locale} fresh={weeks === 4} none12={weeks === 12} />}
          </span>
        )}
        <span className="min-w-0">
          {nameLine(r, null, <RiskMark risk={r.risk === "caution" || r.risk === "avoid" ? r.risk : null} locale={locale} />)}
          <span lang={r.glossLang} className="or-clamp-1 mt-1 text-[14px] leading-[1.45] text-[var(--or-slate)]">{r.gloss}</span>
          {extra}
          <span className="mt-1 block text-[13px] text-[var(--or-slate)] sm:hidden lg:block xl:hidden">{stageWord(locale, r.lifecycle)}</span>
        </span>
        {searchable ? (
          <>
            {/* 휴대폰: 증감 숫자만 오른쪽에 — 72px 짜리 추이 선은 뺐다(모양은 표지와 항목 화면이 맡는다) */}
            <span className="self-start pt-0.5 sm:hidden">{r.growth != null && <Growth locale={locale} g={r.growth} />}</span>
            <span className="hidden sm:block">{r.spark && <Sparkline values={r.spark} recent={r.sparkRecent} className="lg:!w-[104px] xl:!w-[120px]" />}</span>
            <span className="hidden text-right sm:block">{r.growth != null && <Growth locale={locale} g={r.growth} />}</span>
          </>
        ) : (
          <span className="or-num self-start pt-0.5 text-right text-[13px] text-[var(--or-slate)] sm:self-center sm:text-left">
            {r.lastUsed && <><span className="sr-only">{tr(locale, "col_last_used")} </span>{fmtDay(r.lastUsed, locale, p.refAt)}</>}
          </span>
        )}
        <span className="hidden text-[13px] text-[var(--or-slate)] sm:block lg:hidden xl:block">{stageWord(locale, r.lifecycle)}</span>
      </Link>
    </li>
  );

  // 조심할 밈 — 판정 장부: 수준 · 밈과 이유(알아본 것 전부, 인용 없이) · 단계
  const ledgerLine = (r: Row) => {
    const level = r.risk === "caution" || r.risk === "avoid" ? r.risk : null;
    return (
      <li key={r.id} className="or-row" aria-current={r.id === selectedId ? "true" : undefined}>
        <Link {...rowProps(r)} className={`or-row-link grid ${ledger} items-start gap-x-4 py-3.5 pr-1 pl-3`}>
          <span className="hidden pt-0.5 sm:block"><RiskMark risk={level} locale={locale} /></span>
          <span className="min-w-0">
            {nameLine(r, <span className="sm:hidden"><RiskMark risk={level} locale={locale} /></span>)}
            <span lang={r.glossLang} className="or-clamp-1 mt-1 text-[14px] leading-[1.45] text-[var(--or-slate)]">{r.gloss}</span>
            <RiskNotes notes={r.riskNotes} fallback={tr(locale, level === "avoid" ? "risk_avoid_why" : "risk_caution_why")} className="mt-1.5 text-[13px] leading-[1.5] text-[var(--or-ink)]" />
            <span className="mt-1 block text-[13px] text-[var(--or-slate)] sm:hidden lg:block xl:hidden">{stageWord(locale, r.lifecycle)}</span>
          </span>
          <span className="hidden pt-0.5 text-[13px] text-[var(--or-slate)] sm:block lg:hidden xl:block">{stageWord(locale, r.lifecycle)}</span>
        </Link>
      </li>
    );
  };

  const header = tab === "caution" ? (
    <div className={`hidden ${ledger} gap-x-4 border-b border-[var(--or-ink)] py-2 pr-1 pl-3 text-[13px] font-medium text-[var(--or-slate)] sm:grid`} aria-hidden>
      <span>{tr(locale, "col_level")}</span>
      <span>{tr(locale, "col_meme_reason")}</span>
      <span className="lg:hidden xl:block">{tr(locale, "col_stage")}</span>
    </div>
  ) : (
    <div className={`hidden ${cols} gap-x-4 border-b border-[var(--or-ink)] py-2 pr-1 pl-3 text-[13px] font-medium text-[var(--or-slate)] sm:grid`} aria-hidden>
      {showRank && <span>{tr(locale, "col_rank")}</span>}
      <span>{tr(locale, "col_meme")}</span>
      {searchable ? (
        <>
          <span>{tr(locale, p.regionsParam && p.regionsParam !== "KR" ? "col_trend_kr" : "col_trend")}</span>
          <span className="text-right">{tr(locale, "col_change")}</span>
        </>
      ) : <span>{tr(locale, "col_last_used")}</span>}
      <span className="lg:hidden xl:block">{tr(locale, "col_stage")}</span>
    </div>
  );

  const pageHref = (n: number) => {
    const u = new URLSearchParams(p.keep);
    u.set("tab", tab);
    if (n > 1) u.set("page", String(n)); else u.delete("page");
    return `/lab/o-report?${u}`;
  };
  const sortHref = (s: SortKey) => {
    const u = new URLSearchParams(p.keep);
    if (s === "gain") u.set("sort", "gain");
    const qs = u.toString();
    return `/lab/o-report${qs ? `?${qs}` : ""}#or-board`;
  };

  const diffLine = (w: Watched, d: WatchDiff, known: boolean) => {
    const parts: string[] = [];
    if (d.gone) parts.push(tr(locale, "watch_gone"));
    if (d.stage) parts.push(tr(locale, "watch_stage", { a: stageWord(locale, d.stage[0]), b: stageWord(locale, d.stage[1]) }));
    if (d.risk) parts.push(tr(locale, "watch_risk", { a: riskWord(locale, d.risk[0]), b: riskWord(locale, d.risk[1]) }));
    if (d.meaning) parts.push(tr(locale, "watch_meaning"));
    return (
      <span className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[13px] leading-[1.5]">
        {parts.length > 0 && <span className="font-semibold text-[var(--or-petrol-deep)]">{tr(locale, "watch_changed")}</span>}
        {parts.map((t) => <span key={t} className="text-[var(--or-ink)]">{t}</span>)}
        {w.at && <span className="text-[var(--or-slate)]">{tr(locale, "watch_since", { d: fmtDay(w.at, locale, p.refAt) })}</span>}
        {!parts.length && known && <span className="text-[var(--or-slate)]">{tr(locale, "watch_same")}</span>}
      </span>
    );
  };

  const note = tab === "rising" && canRank ? tr(locale, !gain ? "sort_base_note" : weeks === 12 ? "sort_gain_note_12" : "sort_gain_note", { w: weeks }) : null;

  return (
    <div id="or-board" className="scroll-mt-20 grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_400px] xl:gap-12">
      <div className="min-w-0">
        <div role="tablist" aria-label={tr(locale, "tabs_label")} className="flex gap-1 overflow-x-auto border-b border-[var(--or-line)] or-snap">
          {TABS.map((t, i) => (
            <button key={t} id={`or-tab-${t}`} role="tab" type="button" aria-selected={tab === t} aria-controls="or-tabpanel" tabIndex={tab === t ? 0 : -1}
              onClick={() => chooseTab(t)} onKeyDown={(e) => onTabKey(e, i)}
              className="or-tab inline-flex h-12 shrink-0 items-center gap-1.5 px-2.5 text-[16px] font-semibold sm:gap-2 sm:px-3 text-[var(--or-slate)] hover:text-[var(--or-ink)]">
              {t === "watch" && <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden><path d="M8 1.6l1.9 4 4.3.5-3.2 3 .9 4.3L8 11.2l-3.9 2.2.9-4.3-3.2-3 4.3-.5z" fill={watch.length ? "var(--or-petrol)" : "none"} stroke="currentColor" strokeWidth="1.2" /></svg>}
              {tr(locale, `tab_${t}` as CopyKey)}
              <span className="or-num text-[14px] font-medium text-[var(--or-slate)]">{count(t)}</span>
            </button>
          ))}
        </div>

        <div id="or-tabpanel" role="tabpanel" aria-labelledby={`or-tab-${tab}`} tabIndex={0} className="focus-visible:outline-offset-4">
          {/* 정렬 — 기본 순(백엔드 순서) / 검색 증가 순. 스크립트가 없으면 주소(?sort=gain)로 서버가 그린다 */}
          {note && (
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pt-3 pb-1">
              <p className="max-w-[620px] text-[13px] leading-[1.5] text-[var(--or-slate)]">{note}</p>
              <div role="group" aria-label={tr(locale, "sort_label")} className="inline-flex shrink-0 rounded-[6px] border border-[var(--or-line-strong)] p-0.5">
                {(["base", "gain"] as const).map((s) => (
                  <a key={s} href={sortHref(s)} onClick={(e) => chooseSort(e, s)} aria-current={sort === s ? "true" : undefined}
                    className={`inline-flex h-9 items-center rounded-[4px] px-3 text-[14px] whitespace-nowrap ${sort === s ? "bg-[var(--or-mist)] font-semibold text-[var(--or-ink)] shadow-[inset_0_-2px_0_var(--or-petrol)]" : "text-[var(--or-slate)] hover:text-[var(--or-ink)]"}`}>
                    {tr(locale, s === "base" ? "sort_base" : "sort_gain")}
                  </a>
                ))}
              </div>
            </div>
          )}
          {tab === "caution" && rows.length > 0 && <p className="pt-3 text-[13px] text-[var(--or-slate)]">{tr(locale, "caution_overlap")}</p>}
          {rows.length > 0 && header}

          {tab === "rising" && ranked.length > 0 && <ol className="list-none">{ranked.map((r) => line(r))}</ol>}
          {tab === "rising" && rest.length > 0 && (
            <>
              {gain && (
                <p className="border-b border-[var(--or-line)] bg-[var(--or-paper)] py-3 pl-1 text-[13px] text-[var(--or-slate)] sm:pl-3">
                  {ranked.length ? tr(locale, "unranked", { n: rest.length }) : tr(locale, "unranked_all")}
                </p>
              )}
              <ul>{rest.map((r) => line(r))}</ul>
            </>
          )}
          {(tab === "fading") && rows.length > 0 && <ul>{rows.map((r) => line(r))}</ul>}
          {tab === "caution" && rows.length > 0 && <ul>{rows.map(ledgerLine)}</ul>}
          {tab === "watch" && rows.length > 0 && (
            <ul>{watchedRows.map((r) => { const w = watch.find((x) => x.id === r.id)!; return line(r, diffLine(w, diffFor(w), true)); })}</ul>
          )}

          {rows.length === 0 && !(tab === "watch" && watchedElsewhere.length > 0) && (
            <p className="max-w-[640px] py-10 text-[16px] leading-[1.6] text-[var(--or-slate)]">
              {tab === "watch" ? tr(locale, "watch_empty") : tr(locale, tab === "rising" ? "list_empty_rising" : tab === "fading" ? "list_empty_fading" : "list_empty_caution")}
            </p>
          )}

          {tab === "watch" && watchedElsewhere.length > 0 && (
            <div className="mt-6">
              <h3 className="text-[14px] font-semibold">{tr(locale, "watch_elsewhere")}</h3>
              {outside.status === "loading" && <p role="status" className="mt-2 text-[13px] text-[var(--or-slate)]">{tr(locale, "watch_loading")}</p>}
              {outside.status === "failed" && <p role="status" className="mt-2 text-[13px] text-[var(--or-slate)]">{tr(locale, "watch_failed")}</p>}
              <ul className="mt-2 border-t border-[var(--or-line)]">
                {watchedElsewhere.map((w) => {
                  const s = outside.outside.get(w.id);
                  const now = s && !s.gone ? s : null;
                  return (
                    <li key={w.id} className="border-b border-[var(--or-line)] py-3 pl-3">
                      <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                        <Link href={entry(w.id)} lang={w.lang} className="text-[16px] font-bold underline-offset-4 hover:underline">{w.name}</Link>
                        {now?.risk && (now.risk === "caution" || now.risk === "avoid") && <RiskMark risk={now.risk} locale={locale} />}
                        {now?.lifecycle && <span className="text-[13px] text-[var(--or-slate)]">{stageWord(locale, now.lifecycle)}</span>}
                        {now?.regions && now.regions.length > 0 && <span className="text-[13px] text-[var(--or-slate)]">{now.regions.map((r) => regionLabel(locale, r)).join(", ")}</span>}
                      </span>
                      {now?.gloss && <span lang={now.glossLang} className="or-clamp-1 mt-1 text-[14px] text-[var(--or-slate)]">{now.gloss}</span>}
                      {diffLine(w, diffFor(w), outside.status === "ready")}
                      {s?.gone && (
                        <button type="button" onClick={() => toggleWatch({ id: w.id, name: w.name })}
                          className="mt-2 inline-flex h-9 items-center rounded-[6px] border border-[var(--or-line-strong)] px-3 text-[13px] font-medium hover:border-[var(--or-ink)]">
                          {tr(locale, "watch_remove")}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {pages > 1 && (
            <nav className="flex flex-wrap items-center justify-between gap-3 py-4 text-[13px] text-[var(--or-slate)]" aria-label={tr(locale, "tabs_label")}>
              <span className="or-num">{tr(locale, "more_pages", { n: p.totals[tab as "fading" | "caution"], from: (p.page - 1) * p.pageSize + 1, to: Math.min(p.page * p.pageSize, p.totals[tab as "fading" | "caution"]) })}</span>
              <span className="flex gap-2">
                {p.page > 1 && <Link href={pageHref(p.page - 1)} className="inline-flex h-10 items-center rounded-[6px] border border-[var(--or-line-strong)] px-3 text-[var(--or-ink)] hover:border-[var(--or-ink)]">{tr(locale, "page_prev")}</Link>}
                {p.page < pages && <Link href={pageHref(p.page + 1)} className="inline-flex h-10 items-center rounded-[6px] border border-[var(--or-line-strong)] px-3 text-[var(--or-ink)] hover:border-[var(--or-ink)]">{tr(locale, "page_next")}</Link>}
              </span>
            </nav>
          )}
        </div>
      </div>

      <aside aria-label={tr(locale, "preview_label")} className="hidden lg:block">
        <p className="sr-only" aria-live="polite">{selected ? tr(locale, "preview_now", { name: selected.name }) : ""}</p>
        {/* 붙박이 미리보기: 이름·뜻·판단·할 일은 늘 보이고, 그 아래(추이·유래·쓰임)만 안에서 넘긴다(09-29 검토: 짧은 화면에서 할 일이 잘렸다) */}
        <div className="sticky top-[88px] flex max-h-[calc(100dvh-104px)] flex-col">
          {selected ? (
            <PreviewPanel key={selected.id} row={selected} preview={previews[selected.id]} locale={locale} weeks={weeks} searchable={searchable}
              href={entry(selected.id)} watching={watch.some((w) => w.id === selected.id)} refAt={p.refAt} />
          ) : <p className="text-[14px] text-[var(--or-slate)]">{tr(locale, "select_hint")}</p>}
        </div>
      </aside>
    </div>
  );
}

function PreviewPanel({ row, preview, locale, weeks, searchable, href, watching, refAt }: {
  row: Row; preview: Preview | "failed" | undefined; locale: Locale; weeks: Weeks; searchable: boolean; href: string; watching: boolean; refAt: string;
}) {
  const pv = preview && preview !== "failed" ? preview : null;
  const canMake = row.risk !== "avoid" && (pv ? pv.verified : true);   // 목록의 밈은 모두 확인된 밈이다
  const riskKey: RiskKey = row.risk ?? "none";
  const media = pv?.media ?? null;
  // 쓰기 전에 볼 것(뜻 → 써도 되나 → 만들기)은 머리에 붙여 두고, 더 알아볼 것(추이 → 그림 → 유래 → 쓰임)만 아래에서 넘긴다
  return (
    <article className="or-swap flex min-h-0 flex-col">
      <div className="shrink-0 pb-4">
        <div className="flex items-start justify-between gap-4">
          <h2 lang={row.lang} className="min-w-0 text-[36px] leading-[1.1] font-extrabold tracking-[-0.035em] [overflow-wrap:anywhere]">{row.name}</h2>
          <WatchButton id={row.id} name={row.name} lang={row.lang} lifecycle={row.lifecycle} risk={riskKey} watching={watching} locale={locale} />
        </div>
        {row.reading && <p lang={row.readingLang} className="mt-1 text-[14px] text-[var(--or-slate)]">{row.reading}</p>}
        <p lang={pv ? pv.textLang : row.glossLang} className="or-clamp-3 mt-3 text-[16px] leading-[1.6]">{pv?.definition ?? (row.gloss || tr(locale, "no_meaning"))}</p>

        <dl className="mt-4 grid grid-cols-3 gap-x-4 gap-y-3 border-y border-[var(--or-line)] py-3.5">
          <div>
            <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "stage")}</dt>
            <dd className="mt-1.5 text-[14px] font-semibold">{stageWord(locale, row.lifecycle)}</dd>
          </div>
          <div>
            <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "spread")}</dt>
            <dd className={`mt-1.5 text-[14px] font-semibold ${row.diffusion ? "" : "text-[var(--or-slate)]"}`}>{row.diffusion ? spreadWord(locale, row.diffusion) : "–"}</dd>
          </div>
          <div>
            <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "risk")}</dt>
            <dd className="mt-1.5"><RiskMark risk={riskKey} locale={locale} withNone /></dd>
          </div>
          <div className="col-span-3">
            <RiskNotes notes={row.riskNotes} fallback={tr(locale, `risk_${riskKey}_why` as CopyKey)} max={2} className="text-[13px] leading-[1.5] text-[var(--or-slate)]" />
          </div>
        </dl>

        <div className="mt-4 flex flex-wrap gap-2">
          {canMake && <Link href={`/recommend?term=${encodeURIComponent(row.id)}`} className="inline-flex h-12 flex-1 items-center justify-center rounded-[6px] bg-[var(--or-ink)] px-4 text-[16px] font-semibold whitespace-nowrap text-white hover:bg-[var(--or-petrol-deep)]">{tr(locale, "make")}</Link>}
          <Link href={href} className={`inline-flex h-12 items-center justify-center rounded-[6px] border border-[var(--or-line-strong)] px-4 text-[14px] font-medium whitespace-nowrap hover:border-[var(--or-ink)] ${canMake ? "" : "flex-1"}`}>{tr(locale, "open_entry")}</Link>
        </div>
      </div>

      <div className="or-preview-more min-h-0 flex-1 overflow-y-auto overscroll-contain border-t border-[var(--or-line)] pt-4 pb-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-[14px] font-semibold">{tr(locale, "search_trend")}</h3>
          {row.growth != null && <span className="flex items-baseline gap-2"><Growth locale={locale} g={row.growth} size="md" /><span className="text-[12px] text-[var(--or-slate)]">{tr(locale, weeks === 4 ? "spot_caption_4" : "spot_caption_12")}</span></span>}
        </div>
        {searchable && row.spark ? (
          <div className="mt-3">
            <WeeklyBars values={row.spark} recent={row.sparkRecent} height={56} />
            <p className="mt-1.5 text-[12px] text-[var(--or-slate)]">{tr(locale, "search_trend_note")}</p>
          </div>
        ) : (
          <p className="mt-2 text-[13px] leading-[1.55] text-[var(--or-slate)]">{tr(locale, row.searched ? "no_growth" : "no_search")}</p>
        )}

        {preview === undefined && <p role="status" className="mt-5 text-[13px] text-[var(--or-slate)]">{tr(locale, "preview_loading")}</p>}
        {preview === "failed" && <p role="status" className="mt-5 text-[13px] text-[var(--or-slate)]">{tr(locale, "preview_failed")}</p>}

        {/* 다른 표기 — 이름 밑에 이미 쓴 읽기 도움은 되풀이하지 않는다 */}
        {pv && pv.aliases.filter((a) => a !== row.reading).length > 0 && (
          <p className="mt-5 text-[13px] text-[var(--or-slate)]">
            {tr(locale, "aliases")} {pv.aliases.filter((a) => a !== row.reading).map((a, i) => <span key={a} className="text-[var(--or-ink)]">{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>)}
          </p>
        )}

        {media && (
          <figure className="mt-5">
            <a href={media.href} target="_blank" rel="noreferrer noopener" className="block overflow-hidden rounded-[4px] bg-[var(--or-mist)]">
              {/* 주소만 쓴다 — 파일을 받지 않는다(저작권) */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={media.src} alt={media.title || row.name} loading="lazy" className={`w-full ${media.kind === "video" ? "aspect-video object-cover" : "max-h-[200px] object-contain"}`} />
              <span className="sr-only"> ({tr(locale, "new_tab")})</span>
            </a>
            <figcaption className="mt-1.5 truncate text-[12px] text-[var(--or-slate)]">
              {media.kind === "video" ? tr(locale, "media_video") : `${tr(locale, "media_photo")} ${[media.attribution, media.license].filter(Boolean).join(", ")}`}
            </figcaption>
          </figure>
        )}

        {pv?.origin && (
          <div className="mt-5">
            <h3 className="text-[14px] font-semibold">{tr(locale, "origin")}</h3>
            <p lang={pv.textLang} className="or-clamp-3 mt-1.5 text-[14px] leading-[1.6]">{pv.origin}</p>
            {pv.refs.length > 0 && (
              <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[13px]">
                {pv.refs.map((r) => (
                  <a key={r.url} href={r.url} target="_blank" rel="noreferrer noopener" className="text-[var(--or-petrol)] underline-offset-4 hover:underline">
                    <span lang={r.nameLang}>{r.name}</span> <span className="or-num">{fmtDay(r.date, locale, refAt)}</span><span className="sr-only"> ({tr(locale, "new_tab")})</span>
                  </a>
                ))}
              </p>
            )}
          </div>
        )}

        {(pv?.nuance || pv?.plain) && (
          <div className="mt-5">
            <h3 className="text-[14px] font-semibold">{tr(locale, "usage")}</h3>
            {pv.plain && <p className="mt-1.5 text-[14px]"><span className="text-[var(--or-slate)]">{tr(locale, "plainly")} </span><span lang={pv.textLang} className="font-semibold">{pv.plain}</span></p>}
            {pv.nuance && <p lang={pv.textLang} className="or-clamp-3 mt-1.5 text-[14px] leading-[1.6]">{pv.nuance}</p>}
          </div>
        )}

        {row.regions.length > 0 && (
          <p className="mt-5 text-[13px] text-[var(--or-slate)]">{tr(locale, "where")} <span className="text-[var(--or-ink)]">{row.regions.map((r) => regionLabel(locale, r)).join(", ")}</span></p>
        )}
      </div>
    </article>
  );
}

export function WatchButton({ id, name, lang, lifecycle, risk, watching, locale, big = false }: {
  id: string; name: string; lang?: string; lifecycle: Lifecycle; risk: RiskKey; watching: boolean; locale: Locale; big?: boolean;
}) {
  return (
    <button type="button" onClick={() => toggleWatch({ id, name, lang, lifecycle, risk })} aria-pressed={watching}
      className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[6px] border px-3 font-medium whitespace-nowrap ${big ? "h-12 text-[16px]" : "h-9 text-[13px]"} ${watching ? "border-[var(--or-petrol)] text-[var(--or-petrol)]" : "border-[var(--or-line-strong)] text-[var(--or-ink)] hover:border-[var(--or-ink)]"}`}>
      <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden><path d="M8 1.6l1.9 4 4.3.5-3.2 3 .9 4.3L8 11.2l-3.9 2.2.9-4.3-3.2-3 4.3-.5z" fill={watching ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>
      {tr(locale, watching ? "watch_on" : "watch_add")}
    </button>
  );
}
