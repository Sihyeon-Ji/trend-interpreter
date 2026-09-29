"use client";

/* 다시 오게 하는 이유 하나 — '지난번 이후 무엇이 바뀌었나'. 지난 방문 시각은 이 브라우저에만 있고, 서버 그림은 '최근 7일' 로 그린다.
   수는 고른 지역만: 새로 실린 밈·뜻이 바뀐 밈(둘러보는 목록에 있는 것), 검색이 갑자기 는 말(검색어라 밈이 아닐 수 있다 — 줄마다 '검색어' 표시,
   누르면 사전에서 찾아본다). 지켜보는 밈은 지켜보기 시작한 뒤 단계·쓸 때 조심·뜻이 바뀐 수를 함께 말한다. */
import Link from "next/link";
import { useId, useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { fmtDay, fmtTime, type Change } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report-copy";
import { regionLabel } from "@/lib/labels";
import { Tag } from "./bits";
import { changed, diffOf, nowOf, useLastVisit, useOutsideStates, useWatchlist, type Current, type LastVisit } from "./store";
import { jumpToTab } from "./tab-jump";

/** 지난 방문 뒤의 변화인가. 처음이거나 일주일보다 오래됐으면 받은 7일 전부 */
export function afterVisit(at: string, last: LastVisit | undefined): boolean {
  if (!last?.at || last.old) return true;
  return Date.parse(at) > Date.parse(last.at);
}

type Kind = Change["kind"];

export function SinceVisit({ locale, changes, regionsParam, current }: {
  locale: Locale; changes: Change[]; regionsParam: string; current: Record<string, Current>;
}) {
  const last = useLastVisit();
  const watch = useWatchlist();
  const [open, setOpen] = useState<Kind | null>(null);
  const panelId = useId();
  const rows = useMemo(() => new Map(Object.entries(current)), [current]);
  const outside = useOutsideStates(watch, (id) => rows.has(id), locale);
  const fresh = changes.filter((c) => afterVisit(c.at, last));
  const by = (k: Kind) => fresh.filter((c) => c.kind === k);
  const old = !!last?.old;
  const heading = last?.at && !old ? tr(locale, "since_back", { t: fmtTime(last.at, locale) }) : tr(locale, "since_first");
  const watchChanged = watch.filter((w) => changed(diffOf(w, nowOf(w.id, rows, outside.outside), changes))).length;
  const q = regionsParam ? `?regions=${encodeURIComponent(regionsParam)}` : "";

  const counters: { k: Kind; label: string }[] = [
    { k: "verified", label: tr(locale, "since_new") },
    { k: "meaning_changed", label: tr(locale, "since_changed") },
    { k: "spike", label: tr(locale, "since_spike") },
  ];
  const items = open ? by(open) : [];

  return (
    <section aria-labelledby={`${panelId}-h`} className="border-y border-[var(--or-line)]">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 py-3">
        <h2 id={`${panelId}-h`} className="text-[14px] font-semibold">{heading}</h2>
        <ul className="flex flex-wrap items-center gap-x-1 gap-y-1">
          {counters.map(({ k, label }) => {
            const n = by(k).length;
            return (
              <li key={k}>
                <button type="button" onClick={() => setOpen(open === k ? null : k)} aria-expanded={open === k} aria-controls={panelId} disabled={n === 0}
                  className={`inline-flex h-10 items-baseline gap-1.5 rounded-[6px] px-2.5 text-[14px] ${open === k ? "bg-[var(--or-mist)]" : "hover:bg-[var(--or-mist)]"} disabled:cursor-default disabled:hover:bg-transparent`}>
                  <span className={`or-num text-[21px] leading-none font-bold ${n ? "text-[var(--or-petrol)]" : "text-[var(--or-slate)]"}`}>{n}</span>
                  <span className={n ? "text-[var(--or-ink)]" : "text-[var(--or-slate)]"}>{label}</span>
                </button>
              </li>
            );
          })}
        </ul>
        {watch.length > 0 && (
          <button type="button" onClick={() => jumpToTab("watch")} className="ml-auto inline-flex h-10 items-center gap-2 rounded-[6px] px-2.5 text-[14px] hover:bg-[var(--or-mist)]">
            <svg viewBox="0 0 16 16" className="h-4 w-4 text-[var(--or-petrol)]" aria-hidden><path d="M8 1.6l1.9 4 4.3.5-3.2 3 .9 4.3L8 11.2l-3.9 2.2.9-4.3-3.2-3 4.3-.5z" fill="currentColor" /></svg>
            {tr(locale, "since_watch", { n: watch.length })}
            {watchChanged > 0 && <span className="font-semibold text-[var(--or-petrol-deep)]">{tr(locale, "since_watch_changed", { n: watchChanged })}</span>}
          </button>
        )}
      </div>
      {old && <p className="pb-3 text-[13px] text-[var(--or-slate)]">{tr(locale, "since_old")}</p>}
      <div id={panelId} hidden={!open} className="pb-5">
        {open === "spike" && <p className="mb-2 text-[13px] text-[var(--or-slate)]">{tr(locale, "since_spike_note")}</p>}
        <ul className="grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
          {items.slice(0, 18).map((c, i) => (
            <li key={`${c.kind}-${c.id ?? c.label}-${i}`} className="border-t border-[var(--or-line)] py-3">
              {/* 새 밈·뜻 바뀜은 그 항목으로, 검색 급증은 사전 찾기로(사전에 있으면 거기서 열린다) */}
              <Link href={c.id ? `/lab/o-report/m/${encodeURIComponent(c.id)}${q}` : `/lab/o-report/search?q=${encodeURIComponent(c.label)}`} className="group block">
                <span className="flex items-baseline justify-between gap-3">
                  <span className="flex min-w-0 items-baseline gap-2">
                    {c.kind === "spike" && <Tag kind="search" locale={locale} />}
                    <span lang={c.lang} className="truncate text-[16px] font-semibold group-hover:underline">{c.label}</span>
                  </span>
                  <span className="shrink-0 text-[12px] text-[var(--or-slate)]">{c.region ? `${regionLabel(locale, c.region)} ` : ""}<span className="or-num">{fmtDay(c.at, locale)}</span></span>
                </span>
                {c.note && (
                  <span lang={c.noteLang} className="or-clamp-2 mt-1 text-[13px] leading-[1.5] text-[var(--or-slate)]">
                    {c.kind === "meaning_changed" && <span className="font-medium text-[var(--or-ink)]" lang={locale}>{tr(locale, "since_prev")} </span>}
                    {c.note}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
        {items.length === 0 && open && <p className="text-[14px] text-[var(--or-slate)]">{tr(locale, "since_nothing")}</p>}
      </div>
    </section>
  );
}
