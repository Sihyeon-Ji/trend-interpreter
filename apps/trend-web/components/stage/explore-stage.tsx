"use client";

import { ArrowUpRight, X } from "lucide-react";
import { animate, useReducedMotion } from "motion/react";
import Link from "next/link";
import { ViewTransition, useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { sep } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import type { Tone, TermRelated, WeeklyPoint } from "@/lib/types";
import { MemeWord, Reading, RiskMark, Verdict, fmtDay, fmtN, fmtStamp, type VerdictKind, wordVT } from "./bits";
import { Spark, TrendChart } from "./chart";
import { MARKETS, diffusionWord, marketName, tx, type CopyKey, type Market } from "./copy";
import { MiniGlobe } from "./globe";
import { RelGraph, hasGraph } from "./graph";

export type XList = "rising" | "fading" | "caution";
export interface XRow {
  id: string; word: string; lang: string; readings?: Record<string, string>; gloss: string; verdict: VerdictKind; life: string; diffusion: string | null;
  m4: number; weekly: WeeklyPoint[]; regions: string[]; tone: Tone; partial: boolean;
  refs: { url: string; label: string; title: string; date: string }[];
  related?: TermRelated | null;
}

const LIST_KEY: Record<XList, CopyKey> = { rising: "xp_rising", fading: "xp_fading", caution: "xp_caution" };
const NOTE_KEY: Record<XList, CopyKey> = { rising: "xp_rising_note", fading: "xp_fading_note", caution: "xp_caution_note" };
const href = (m: Market, l: XList, p = 1, w?: string | null) => `/trends?m=${m}${l !== "rising" ? `&l=${l}` : ""}${p > 1 ? `&p=${p}` : ""}${w ? `&w=${encodeURIComponent(w)}` : ""}`;
const termHref = (id: string, m: Market) => `/dictionary/${encodeURIComponent(id)}?m=${m}`;

function useNarrow() {
  return useSyncExternalStore(
    (fn) => { const q = window.matchMedia("(max-width: 900px)"); q.addEventListener("change", fn); return () => q.removeEventListener("change", fn); },
    () => window.matchMedia("(max-width: 900px)").matches,
    () => false,
  );
}

/** 무대 위의 말 — 목록에서 고른 낱말이 그 자리에서 날아와 크게 선다(처음 고를 때만, 움직임 줄이기면 그냥 나타남) */
function Spot({ row, market, locale, from, titleId }: {
  row: XRow; market: Market; locale: Locale; from: DOMRect | null; titleId: string;
}) {
  const related = row.related;
  const wordRef = useRef<HTMLHeadingElement>(null);
  const reduce = useReducedMotion();
  useLayoutEffect(() => {
    const el = wordRef.current?.querySelector<HTMLElement>(".rs-word");
    if (!el || !from || reduce) return;
    const to = el.getBoundingClientRect();
    if (!to.height) return;
    const dx = from.left - to.left, dy = from.top - to.top, s = from.height / to.height;
    const ctl = animate(el, { transform: [`translate(${dx}px, ${dy}px) scale(${s})`, "translate(0px, 0px) scale(1)"] }, { type: "spring", stiffness: 380, damping: 31 });
    return () => ctl.stop();
  }, [from, reduce]);
  const total = row.tone.positive + row.tone.neutral + row.tone.negative;
  return (
    <article className="rs-spot-card" aria-labelledby={titleId}>
      <div className="rs-spot-top">
        <Verdict kind={row.verdict} locale={locale} />
        <span className="rs-spot-life">{row.life}</span>
      </div>
      <ViewTransition name={wordVT(row.id, market)} share="rs-morph" default="none">
        <h2 id={titleId} className="rs-spot-word" ref={wordRef}><MemeWord text={row.word} lang={row.lang} max={104} min={34} /></h2>
      </ViewTransition>
      <Reading readings={row.readings} locale={locale} className="rs-spot-reading" />
      <p className="rs-spot-gloss" lang={scriptLang(row.gloss)}>{row.gloss}</p>
      <dl className="rs-facts">
        {row.diffusion ? <div><dt>{tx(locale, "pk_why_spread")}</dt><dd>{diffusionWord(row.diffusion, locale)}</dd></div> : null}
        {row.regions.length ? <div><dt>{tx(locale, "xp_where")}</dt><dd>{row.regions.join(sep(locale))}</dd></div> : null}
        <div><dt>{tx(locale, "xp_m4")}</dt><dd>{fmtN(row.m4)}</dd></div>
      </dl>
      <div className="rs-sub">
        <h3>{tx(locale, "xp_trend")}</h3>
        <TrendChart weekly={row.weekly} locale={locale} partial={row.partial} height={96} />
        {total >= 5 ? <p className="rs-quiet">{tx(locale, "xp_tone", { n: total, p: row.tone.positive, u: row.tone.neutral, g: row.tone.negative })}</p> : null}
      </div>
      <div className="rs-sub">
        <h3>{tx(locale, "tm_linked")}</h3>
        {related && hasGraph(related) ? <RelGraph word={row.word} lang={row.lang} graph={related} href={(id) => termHref(id, market)} locale={locale} />
          : <p className="rs-quiet">{tx(locale, "tm_linked_none")}</p>}
      </div>
      {row.refs.length ? (
        <div className="rs-sub">
          <h3>{tx(locale, "xp_refs")}</h3>
          <ul className="rs-refs">
            {row.refs.map((r) => (
              <li key={r.url}>
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="rs-ref">
                  <span className="rs-ref-src">{r.label}<ArrowUpRight aria-hidden="true" size={13} /></span>
                  <span className="rs-ref-title">{r.title}</span>
                  <span className="rs-ref-date rs-num">{fmtDay(r.date, locale, true)}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="rs-btns rs-spot-actions">
        <Link href={termHref(row.id, market)} className="rs-btn" data-kind="quiet" data-size="s">{tx(locale, "xp_detail")}</Link>
        {row.verdict !== "avoid" ? <Link href={`/?m=${market}&term=${encodeURIComponent(row.id)}`} className="rs-btn" data-kind="primary" data-size="s">{tx(locale, "xp_make")}</Link> : null}
      </div>
    </article>
  );
}

function Body({ locale, market, list, page, pageSize, totals, rows, initial }: {
  locale: Locale; market: Market; list: XList; page: number; pageSize: number; totals: Record<XList, number> | null; rows: XRow[]; initial: string | null;
}) {
  const [sel, setSel] = useState<string | null>(initial);
  const [fly, setFly] = useState<{ id: string; rect: DOMRect } | null>(null);
  const [sheet, setSheet] = useState(false);
  const narrow = useNarrow();
  const opener = useRef<HTMLButtonElement | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const row = rows.find((r) => r.id === sel) ?? null;

  // 휴대폰의 무대 창: 열리면 닫기 단추로 초점, Esc 로 닫고 연 줄로 초점을 돌려준다
  useEffect(() => {
    if (!(narrow && sheet)) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSheet(false);
        opener.current?.focus();
        return;
      }
      if (e.key !== "Tab") return;
      // 창 안에서만 초점이 돈다
      const card = closeRef.current?.closest(".rs-modal-card");
      const items = card ? [...card.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), [tabindex]:not([tabindex='-1'])")] : [];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [narrow, sheet]);

  const choose = (r: XRow, btn: HTMLButtonElement) => {
    const word = btn.querySelector<HTMLElement>(".rs-cast-word");
    if (word) setFly({ id: r.id, rect: word.getBoundingClientRect() });
    setSel(r.id);
    opener.current = btn;
    if (narrow) setSheet(true);
    window.history.replaceState(null, "", href(market, list, page, r.id));
  };
  function close() {
    setSheet(false);
    opener.current?.focus();
  }
  const move = (e: React.KeyboardEvent<HTMLButtonElement>, i: number) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const next = document.querySelectorAll<HTMLButtonElement>(".r-stage .rs-cast-row")[i + (e.key === "ArrowDown" ? 1 : -1)];
    next?.focus();
  };

  const total = totals?.[list] ?? 0;
  const last = Math.max(1, Math.ceil(total / pageSize));
  const spot = row ? <Spot key={row.id} row={row} market={market} locale={locale} from={fly?.id === row.id ? fly.rect : null} titleId={titleId} /> : null;

  return (
    <>
      <nav className="rs-x-lists" aria-label={tx(locale, "xp_lists")}>
        {(["rising", "fading", "caution"] as XList[]).map((l) => (
          <Link key={l} href={href(market, l)} aria-current={l === list ? "page" : undefined} data-list={l} scroll={false}>
            {tx(locale, LIST_KEY[l])}
            {totals ? <span>{fmtN(totals[l])}</span> : null}
          </Link>
        ))}
        <span className="rs-x-note">{tx(locale, NOTE_KEY[list])}</span>
      </nav>
      {rows.length ? (
        <div className="rs-x-body">
          <div className="rs-cast-wrap">
            <p className="rs-cast-head" aria-hidden="true"><span /><span>{tx(locale, "xp_12w")}</span><span>{tx(locale, "xp_m4")}</span></p>
            <ul className="rs-cast">
              {rows.map((r, i) => (
                <li key={r.id}>
                  <button type="button" className="rs-cast-row" aria-pressed={r.id === sel} onClick={(e) => choose(r, e.currentTarget)} onKeyDown={(e) => move(e, i)}>
                    <span className="rs-cast-main">
                      <span className="rs-cast-line">
                        <span className="rs-cast-word" lang={langTag(r.lang)}>{r.word}</span>
                        <Reading readings={r.readings} locale={locale} className="rs-inline-reading" />
                        <RiskMark kind={r.verdict} locale={locale} />
                      </span>
                      <span className="rs-cast-gloss" lang={scriptLang(r.gloss)}>{r.gloss}</span>
                    </span>
                    <Spark weekly={r.weekly} />
                    <span className="rs-cast-m4 rs-num"><span className="rs-sr">{tx(locale, "xp_m4")} </span>{fmtN(r.m4)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {last > 1 ? (
              <p className="rs-pager">
                {page > 1 ? <Link className="rs-btn" data-kind="quiet" data-size="s" href={href(market, list, page - 1)}>{tx(locale, "xp_prev", { n: pageSize })}</Link> : null}
                <span className="rs-num">{tx(locale, "xp_page", { a: (page - 1) * pageSize + 1, b: Math.min(total, page * pageSize) })} / {fmtN(total)}</span>
                {page < last ? <Link className="rs-btn" data-kind="quiet" data-size="s" href={href(market, list, page + 1)}>{tx(locale, "xp_more", { n: pageSize })}</Link> : null}
              </p>
            ) : null}
          </div>
          {!narrow ? <aside className="rs-spot" aria-live="polite">{spot ?? <p className="rs-quiet">{tx(locale, "xp_pick")}</p>}</aside> : null}
        </div>
      ) : (
        <p className="rs-x-empty">{tx(locale, "xp_empty", { market: marketName(locale, market) })}</p>
      )}
      {narrow && sheet && spot ? (
        <div className="rs-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
          <button type="button" className="rs-modal-scrim" aria-hidden="true" tabIndex={-1} onClick={close} />
          <div className="rs-modal-card">
            <button ref={closeRef} type="button" className="rs-modal-close" aria-label="Close" onClick={close}><X aria-hidden="true" size={18} /></button>
            {spot}
          </div>
        </div>
      ) : null}
    </>
  );
}

export function ExploreStage({ locale, market, list, page, pageSize, totals, count, updatedAt, rows, initial, failed }: {
  locale: Locale; market: Market; list: XList; page: number; pageSize: number; totals: Record<XList, number> | null; count: number;
  updatedAt: string | null; rows: XRow[]; initial: string | null; failed: boolean;
}) {
  const name = marketName(locale, market);
  return (
    <section className="rs-stage" data-scene="explore" aria-labelledby="rs-x-h">
      <header className="rs-x-head">
        <MiniGlobe market={market} size={64} tone="ink" className="rs-x-globe" />
        <div className="rs-x-title">
          <h1 id="rs-x-h">{tx(locale, "xp_lead", { market: name })}</h1>
          <p>
            {failed ? <span className="rs-error">{tx(locale, "xp_failed", { market: name })}</span> : <span>{tx(locale, "xp_count", { n: fmtN(count) })}</span>}
            {updatedAt ? <span>{tx(locale, "xp_updated")} <span>{fmtStamp(updatedAt, locale)}</span></span> : null}
          </p>
        </div>
        <nav className="rs-x-markets" aria-label={tx(locale, "dr_markets")}>
          {MARKETS.map((m) => (
            <Link key={m} href={href(m, list)} aria-current={m === market ? "page" : undefined} scroll={false}>
              <MiniGlobe market={m} size={22} tone={m === market ? "ink" : "mute"} />
              {marketName(locale, m)}
            </Link>
          ))}
        </nav>
        <Link className="rs-btn rs-x-make" data-kind="primary" data-size="s" href={`/?m=${market}`}>{tx(locale, "xp_make_market", { market: name })}</Link>
      </header>
      {failed ? (
        <div className="rs-alert" role="alert">
          <p>{tx(locale, "xp_failed", { market: name })}</p>
          <Link className="rs-btn" data-kind="quiet" data-size="s" href={href(market, list, page)}>{tx(locale, "xp_retry")}</Link>
        </div>
      ) : (
        <Body key={`${market}-${list}-${page}`} locale={locale} market={market} list={list} page={page} pageSize={pageSize} totals={totals} rows={rows} initial={initial} />
      )}
    </section>
  );
}
