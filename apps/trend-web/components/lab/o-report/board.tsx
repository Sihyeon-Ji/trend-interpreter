"use client";

/* 순위 목록 + 오른쪽 미리보기. 목록이 일꾼이다: 순위 · 밈(원문 + 뜻 한 줄) · 검색 추이 · 변화 · 단계, 쓸 때 조심은 주의·사용 자제일 때만.
   데스크톱(1024px 이상)에서 줄을 누르면 오른쪽에서 미리 보고, 휴대폰에서는 줄이 곧 항목 화면으로 가는 링크다.
   탭·고른 밈은 주소에도 적어 둔다(history.replaceState) — 새로 고치거나 링크를 보내도 같은 화면. */
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import type { Change, ListKey, Preview, Row, Weeks } from "@/lib/lab/o-report";
import { spreadWord, stageWord, tr, type CopyKey } from "@/lib/lab/o-report-copy";
import { fmtDay } from "@/lib/lab/o-report";
import { scriptLang } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import { Growth, RankChange, RiskMark, Tag } from "./bits";
import { Sparkline, WeeklyBars } from "./charts";
import { afterVisit } from "./since-visit";
import { toggleWatch, useLastVisit, useWatchlist } from "./store";

interface Props {
  locale: Locale;
  lists: { rising: Row[]; fading: Row[]; caution: Row[] };
  totals: { rising: number; fading: number; caution: number };
  previews: Record<string, Preview>;
  searchable: boolean;
  weeks: Weeks;
  regionsParam: string;        // 주소의 regions 값 ('' = 한국 기본)
  page: number;
  pageSize: number;
  initialTab: ListKey;
  initialSelected: string | null;
  changes: Change[];
  keep: string;                // 쪽 링크에 이어 붙일 주소 조각 (regions, w)
  refAt: string;               // 날짜에 해를 붙일지 정하는 기준 시각(보드 갱신 시각)
}

const TABS: ListKey[] = ["rising", "fading", "caution", "watch"];
const DESKTOP = "(min-width: 1024px)";

export function Board(p: Props) {
  const { locale, lists, previews, searchable, weeks } = p;
  const watch = useWatchlist();
  const last = useLastVisit();
  const [tab, setTab] = useState<ListKey>(p.initialTab);
  const [picked, setPicked] = useState<string | null>(p.initialSelected);

  const all = useMemo(() => {
    const m = new Map<string, Row>();
    for (const r of [...lists.rising, ...lists.fading, ...lists.caution]) if (!m.has(r.id)) m.set(r.id, r);
    return m;
  }, [lists]);

  const watchedRows = watch.map((w) => all.get(w.id)).filter((r): r is Row => !!r);
  const watchedElsewhere = watch.filter((w) => !all.has(w.id));
  const rows = tab === "watch" ? watchedRows : lists[tab];
  const selectedId = picked && all.has(picked) ? picked : rows[0]?.id ?? lists.rising[0]?.id ?? null;
  const selected = selectedId ? all.get(selectedId) ?? null : null;

  const fresh = p.changes.filter((c) => afterVisit(c.at, last));
  const newIds = new Set(fresh.filter((c) => c.kind === "verified").map((c) => c.id));
  const changedIds = new Set(fresh.filter((c) => c.kind === "meaning_changed").map((c) => c.id));

  // 머리의 '지켜보는 밈 n개' 가 이 탭을 연다
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

  const writeUrl = (next: { tab?: ListKey; m?: string | null }) => {
    const u = new URL(window.location.href);
    const t = next.tab ?? tab;
    if (t === "rising") u.searchParams.delete("tab"); else u.searchParams.set("tab", t);
    const m = next.m === undefined ? picked : next.m;
    if (m) u.searchParams.set("m", m); else u.searchParams.delete("m");
    window.history.replaceState(null, "", u);
  };

  const chooseTab = (t: ListKey) => { setTab(t); writeUrl({ tab: t }); };
  const onRow = (e: React.MouseEvent, id: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (!window.matchMedia(DESKTOP).matches) return;      // 휴대폰은 링크 그대로 항목 화면으로
    e.preventDefault();
    setPicked(id);
    writeUrl({ m: id });
  };

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
  const ranked = tab === "rising" ? rows.filter((r) => r.rank != null) : [];
  const rest = tab === "rising" ? rows.filter((r) => r.rank == null) : rows;
  const pages = tab === "fading" || tab === "caution" ? Math.ceil(p.totals[tab] / p.pageSize) : 1;

  // 칸: 순위 | 밈 | 추이 | 변화 | 단계. 순위 칸은 순위를 매긴 '쓰이는 밈' 에만 둔다(다른 목록에 빈 칸을 남기지 않게).
  // 검색 자료가 없는 지역은 추이·변화 대신 '마지막 쓰임' 날짜. 1024–1279px 은 미리보기와 폭을 나눠 쓰므로 단계를 뜻 아래 한 줄로 둔다.
  const showRank = searchable && ranked.length > 0;
  const cols = showRank
    ? "grid-cols-[36px_minmax(0,1fr)_auto] sm:grid-cols-[48px_minmax(0,1fr)_120px_76px_96px] lg:grid-cols-[44px_minmax(0,1fr)_104px_68px] xl:grid-cols-[48px_minmax(0,1fr)_120px_76px_96px]"
    : searchable
      ? "grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_120px_76px_96px] lg:grid-cols-[minmax(0,1fr)_104px_68px] xl:grid-cols-[minmax(0,1fr)_120px_76px_96px]"
      : "grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_112px_96px] lg:grid-cols-[minmax(0,1fr)_104px] xl:grid-cols-[minmax(0,1fr)_112px_96px]";

  const line = (r: Row) => (
    <li key={r.id} className="or-row" aria-current={r.id === selectedId ? "true" : undefined}>
      <Link href={entry(r.id)} onClick={(e) => onRow(e, r.id)} prefetch={false}
        className={`or-row-link grid ${cols} items-center gap-x-3 py-3.5 pr-1 pl-3 sm:gap-x-4`}>
        {showRank && (
          <span className="flex flex-col items-start gap-1 self-start pt-0.5">
            {r.rank != null && <span className="or-num text-[21px] leading-none font-bold">{r.rank}</span>}
            <RankChange n={r.rankChange} locale={locale} fresh={r.rank != null && weeks === 4} />
          </span>
        )}
        <span className="min-w-0">
          <span className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
            <span lang={r.lang} className="or-row-name truncate text-[16px] leading-[1.35] font-bold">{r.name}</span>
            {r.reading && <span lang={r.readingLang} className="text-[13px] text-[var(--or-slate)]">{r.reading}</span>}
            {newIds.has(r.id) && <Tag kind="new" locale={locale} />}
            {changedIds.has(r.id) && <Tag kind="changed" locale={locale} />}
            <RiskMark risk={r.risk === "caution" || r.risk === "avoid" ? r.risk : null} locale={locale} />
          </span>
          <span lang={r.glossLang} className="or-clamp-1 mt-1 text-[14px] leading-[1.45] text-[var(--or-slate)]">{r.gloss}</span>
          {tab === "caution" && (r.risk === "caution" || r.risk === "avoid") && (
            <span className="or-clamp-1 mt-0.5 text-[13px] leading-[1.45] text-[var(--or-ink)]">
              {r.riskNote ?? tr(locale, r.risk === "avoid" ? "risk_avoid_why" : "risk_caution_why")}
            </span>
          )}
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

  const header = (
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
          {tab === "caution" && rows.length > 0 && <p className="pt-3 text-[13px] text-[var(--or-slate)]">{tr(locale, "caution_overlap")}</p>}
          {rows.length > 0 && header}

          {tab === "rising" && ranked.length > 0 && <ol className="list-none">{ranked.map(line)}</ol>}
          {tab === "rising" && rest.length > 0 && (
            <>
              {/* 검색 자료가 없는 지역은 위 '요즘 쓰이는 밈' 이 이미 순서를 말했다 — 같은 문장을 되풀이하지 않는다 */}
              {searchable && (
                <p className="border-b border-[var(--or-line)] bg-[var(--or-paper)] py-3 pl-1 text-[13px] text-[var(--or-slate)] sm:pl-3">
                  {ranked.length ? tr(locale, "unranked", { n: rest.length }) : tr(locale, "unranked_all")}
                </p>
              )}
              <ul>{rest.map(line)}</ul>
            </>
          )}
          {tab !== "rising" && rows.length > 0 && <ul>{rows.map(line)}</ul>}

          {rows.length === 0 && (
            <p className="py-10 text-[16px] text-[var(--or-slate)]">
              {tab === "watch" ? tr(locale, "watch_empty") : tr(locale, tab === "rising" ? "list_empty_rising" : tab === "fading" ? "list_empty_fading" : "list_empty_caution")}
            </p>
          )}

          {tab === "watch" && watchedElsewhere.length > 0 && (
            <div className="mt-6">
              <h3 className="text-[14px] font-semibold">{tr(locale, "watch_elsewhere")}</h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {watchedElsewhere.map((w) => (
                  <li key={w.id}><Link href={entry(w.id)} lang={w.lang} className="inline-flex h-9 items-center rounded-[6px] border border-[var(--or-line-strong)] px-3 text-[14px] font-medium hover:border-[var(--or-ink)]">{w.name}</Link></li>
                ))}
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
        <div className="or-preview sticky top-[88px] -mx-1 max-h-[calc(100dvh-104px)] overflow-y-auto overscroll-contain px-1 pb-4">
          {selected ? <PreviewPanel key={selected.id} row={selected} preview={previews[selected.id] ?? null} locale={locale} weeks={weeks} searchable={searchable} href={entry(selected.id)} watching={watch.some((w) => w.id === selected.id)} refAt={p.refAt} /> : <p className="text-[14px] text-[var(--or-slate)]">{tr(locale, "select_hint")}</p>}
        </div>
      </aside>
    </div>
  );
}

function PreviewPanel({ row, preview, locale, weeks, searchable, href, watching, refAt }: {
  row: Row; preview: Preview | null; locale: Locale; weeks: Weeks; searchable: boolean; href: string; watching: boolean; refAt: string;
}) {
  const canMake = !!preview?.verified && row.risk !== "avoid";
  const riskWhy = row.riskNote ?? tr(locale, `risk_${row.risk ?? "none"}_why` as CopyKey);
  const media = preview?.media ?? null;
  // 쓰기 전에 볼 것(뜻 → 써도 되나 → 만들기)을 위에, 더 알아볼 것(추이 → 유래 → 쓰임)을 아래에
  return (
    <article className="or-swap">
      <div className="flex items-start justify-between gap-4">
        <h2 lang={row.lang} className="min-w-0 text-[36px] leading-[1.1] font-extrabold tracking-[-0.035em] [overflow-wrap:anywhere]">{row.name}</h2>
        <WatchButton id={row.id} name={row.name} lang={row.lang} watching={watching} locale={locale} />
      </div>
      {preview?.aliases.length ? (
        <p className="mt-1.5 text-[13px] text-[var(--or-slate)]">
          <span className="sr-only">{tr(locale, "aliases")} </span>
          {preview.aliases.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>)}
        </p>
      ) : null}

      {media && (
        <figure className="mt-4">
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

      <p lang={preview?.textLang ?? row.glossLang} className="or-clamp-4 mt-4 text-[16px] leading-[1.6]">{preview?.definition ?? (row.gloss || tr(locale, "no_meaning"))}</p>

      <dl className="mt-5 grid grid-cols-3 gap-4 border-y border-[var(--or-line)] py-4">
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
          <dd className="mt-1.5"><RiskMark risk={row.risk ?? "none"} locale={locale} withNone /></dd>
        </div>
        <p className="col-span-3 -mt-1 text-[13px] leading-[1.5] text-[var(--or-slate)]">{riskWhy}</p>
      </dl>

      <div className="mt-4 flex gap-2">
        {canMake && <Link href={`/recommend?term=${encodeURIComponent(row.id)}`} className="inline-flex h-12 flex-1 items-center justify-center rounded-[6px] bg-[var(--or-ink)] px-4 text-[16px] font-semibold text-white hover:bg-[var(--or-petrol-deep)]">{tr(locale, "make")}</Link>}
        <Link href={href} className={`inline-flex h-12 items-center justify-center rounded-[6px] border border-[var(--or-line-strong)] px-4 text-[14px] font-medium hover:border-[var(--or-ink)] ${canMake ? "" : "flex-1"}`}>{tr(locale, "open_entry")}</Link>
      </div>

      <div className="mt-6">
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
          <p className="mt-2 text-[13px] leading-[1.55] text-[var(--or-slate)]">{tr(locale, "no_search")}</p>
        )}
      </div>

      {preview?.origin && (
        <div className="mt-5">
          <h3 className="text-[14px] font-semibold">{tr(locale, "origin")}</h3>
          <p lang={preview.textLang} className="or-clamp-3 mt-1.5 text-[14px] leading-[1.6]">{preview.origin}</p>
          {preview.refs.length > 0 && (
            <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[13px]">
              {preview.refs.map((r) => (
                <a key={r.url} href={r.url} target="_blank" rel="noreferrer noopener" className="text-[var(--or-petrol)] underline-offset-4 hover:underline">
                  {r.name} <span className="or-num">{fmtDay(r.date, locale, refAt)}</span><span className="sr-only"> ({tr(locale, "new_tab")})</span>
                </a>
              ))}
            </p>
          )}
        </div>
      )}

      {(preview?.nuance || preview?.plain) && (
        <div className="mt-5">
          <h3 className="text-[14px] font-semibold">{tr(locale, "usage")}</h3>
          {preview.plain && <p className="mt-1.5 text-[14px]"><span className="text-[var(--or-slate)]">{tr(locale, "plainly")} </span><span lang={preview.textLang} className="font-semibold">{preview.plain}</span></p>}
          {preview.nuance && <p lang={preview.textLang} className="or-clamp-3 mt-1.5 text-[14px] leading-[1.6]">{preview.nuance}</p>}
        </div>
      )}

      {row.regions.length > 0 && (
        <p className="mt-5 pb-1 text-[13px] text-[var(--or-slate)]">{tr(locale, "where")} <span className="text-[var(--or-ink)]">{row.regions.map((r) => regionLabel(locale, r)).join(", ")}</span></p>
      )}
    </article>
  );
}

export function WatchButton({ id, name, lang, watching, locale, big = false }: { id: string; name: string; lang?: string; watching: boolean; locale: Locale; big?: boolean }) {
  return (
    <button type="button" onClick={() => toggleWatch({ id, name, lang })} aria-pressed={watching}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-[6px] border px-3 font-medium ${big ? "h-12 text-[16px]" : "h-9 text-[13px]"} ${watching ? "border-[var(--or-petrol)] text-[var(--or-petrol)]" : "border-[var(--or-line-strong)] text-[var(--or-ink)] hover:border-[var(--or-ink)]"}`}>
      <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden><path d="M8 1.6l1.9 4 4.3.5-3.2 3 .9 4.3L8 11.2l-3.9 2.2.9-4.3-3.2-3 4.3-.5z" fill={watching ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>
      {tr(locale, watching ? "watch_on" : "watch_add")}
    </button>
  );
}
