"use client";

/* 프레임의 찾기 칸 — '이 밈, 써도 되나' 를 어디서든 몇 초 안에. 사전 색인(확인된 밈만)은 처음 칸을 쓸 때 한 번 받는다.
   맞추는 규칙은 사전 화면과 같다(lib/lab/o-report.ts matchScore).
   휴대폰에서는 단추를 누르면 화면을 덮는 칸이 열린다(fixed inset-0 + flex, 변형 없이). */
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report/copy";
import { matchScore, normQuery } from "@/lib/lab/o-report";
import type { IndexItem } from "@/lib/lab/o-report/data";
import { RiskMark } from "./bits";

type State = { status: "idle" | "loading" | "ready" | "failed"; items: IndexItem[] };

export function SearchBox({ locale }: { locale: Locale }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [sheet, setSheet] = useState(false);          // 휴대폰 전체 화면 칸
  const [active, setActive] = useState(0);
  const [index, setIndex] = useState<State>({ status: "idle", items: [] });
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const sheetInputRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);

  const load = () => {
    if (index.status === "loading" || index.status === "ready") return;
    setIndex({ status: "loading", items: [] });
    fetch(`/lab/o-report/api/index?locale=${locale}`)
      .then((r) => (r.ok ? (r.json() as Promise<IndexItem[]>) : Promise.reject(new Error(String(r.status)))))
      .then((items) => setIndex({ status: "ready", items }))
      .catch(() => setIndex({ status: "failed", items: [] }));
  };

  const results = useMemo(() => {
    const n = normQuery(q);
    if (!n) return [];
    return index.items.map((it) => ({ it, s: matchScore(it, n) })).filter((x) => x.s < 99).sort((a, b) => a.s - b.s || a.it.name.length - b.it.name.length).slice(0, 7).map((x) => x.it);
  }, [q, index.items]);

  const regions = sp.get("regions");
  const hrefFor = (id: string) => `/lab/o-report/m/${encodeURIComponent(id)}${regions ? `?regions=${encodeURIComponent(regions)}` : ""}`;
  // 전체 결과는 이 초안의 사전 화면으로(09-29 검토: 앱의 예전 화면으로 넘어갔다)
  const allHref = `/lab/o-report/search?q=${encodeURIComponent(q.trim())}`;
  const options = [...results.map((r) => ({ key: r.id, href: hrefFor(r.id) })), ...(q.trim() ? [{ key: "__all", href: allHref }] : [])];

  const go = (href: string) => {
    setOpen(false);
    setSheet(false);
    setQ("");
    router.push(href);
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(options.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter") { const o = options[active] ?? options[0]; if (o) { e.preventDefault(); go(o.href); } }
    else if (e.key === "Escape") { if (sheet) closeSheet(); else { setOpen(false); setQ(""); } }
  };

  const closeSheet = () => { setSheet(false); setOpen(false); openerRef.current?.focus(); };

  useEffect(() => {
    if (!sheet) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sheetInputRef.current?.focus();
    return () => { document.body.style.overflow = prev; };
  }, [sheet]);

  const showList = open && q.trim().length > 0;
  const status = index.status === "loading" ? tr(locale, "search_loading") : index.status === "failed" ? tr(locale, "search_failed") : results.length === 0 && q.trim() ? tr(locale, "search_empty") : "";

  const field = (ref: React.RefObject<HTMLInputElement | null>, big: boolean) => (
    <div className="relative w-full">
      <svg viewBox="0 0 20 20" aria-hidden className={`pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[var(--or-slate)] ${big ? "h-5 w-5" : "h-4 w-4"}`}>
        <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M12.8 12.8l4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <input
        ref={ref}
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && options[active] ? `${listId}-${active}` : undefined}
        aria-label={tr(locale, "search_label")}
        placeholder={tr(locale, "search_placeholder")}
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => { load(); setOpen(true); }}
        onBlur={() => { if (!big) window.setTimeout(() => setOpen(false), 120); }}
        onKeyDown={onKey}
        className={`w-full appearance-none rounded-[6px] border border-[var(--or-edge)] bg-white pr-3 [&::-webkit-search-cancel-button]:hidden text-[var(--or-ink)] placeholder:text-[var(--or-slate)] hover:border-[var(--or-slate)] focus:border-[var(--or-petrol)] focus-visible:outline-offset-0 ${big ? "h-12 pl-10 text-[16px]" : "h-10 pl-9 text-[14px]"}`}
      />
    </div>
  );

  const list = (floating: boolean) => (
    <div className={floating ? "absolute top-[calc(100%+6px)] right-0 left-0 z-40 rounded-[6px] border border-[var(--or-line-strong)] bg-white" : "mt-3"}>
      {status && <p className="px-3 py-3 text-[13px] text-[var(--or-slate)]" role="status">{status}</p>}
      <ul id={listId} role="listbox" aria-label={tr(locale, "search_label")} className="py-1">
        {results.map((r, i) => (
          <li key={r.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}
            onMouseDown={(e) => { e.preventDefault(); go(hrefFor(r.id)); }} onMouseEnter={() => setActive(i)}
            className={`flex cursor-pointer items-start gap-3 px-3 py-2.5 ${i === active ? "bg-[var(--or-mist)]" : ""}`}>
            <span className="min-w-0 flex-1">
              <span lang={r.lang} className="block truncate text-[16px] font-semibold text-[var(--or-ink)]">{r.name}</span>
              {r.gloss && <span lang={r.glossLang} className="or-clamp-1 mt-0.5 text-[13px] text-[var(--or-slate)]">{r.gloss}</span>}
            </span>
            <RiskMark risk={r.risk === "caution" || r.risk === "avoid" ? r.risk : null} locale={locale} />
          </li>
        ))}
        {q.trim() && (
          <li id={`${listId}-${results.length}`} role="option" aria-selected={active === results.length}
            onMouseDown={(e) => { e.preventDefault(); go(allHref); }} onMouseEnter={() => setActive(results.length)}
            className={`cursor-pointer border-t border-[var(--or-line)] px-3 py-2.5 text-[13px] text-[var(--or-petrol)] ${active === results.length ? "bg-[var(--or-mist)]" : ""}`}>
            {tr(locale, "search_all", { q: q.trim() })}
          </li>
        )}
      </ul>
    </div>
  );

  return (
    <>
      <div className="relative hidden w-[300px] md:block lg:w-[340px]">
        {field(inputRef, false)}
        {showList && !sheet && list(true)}
      </div>
      <button ref={openerRef} type="button" onClick={() => { setSheet(true); load(); }} aria-label={tr(locale, "search_open")}
        className="inline-flex h-10 w-10 items-center justify-center rounded-[6px] border border-[var(--or-line-strong)] text-[var(--or-ink)] md:hidden">
        <svg viewBox="0 0 20 20" aria-hidden className="h-[18px] w-[18px]"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M12.8 12.8l4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
      </button>
      {sheet && (
        <div className="fixed inset-0 z-50 flex flex-col bg-white md:hidden" role="dialog" aria-modal="true" aria-label={tr(locale, "search_label")}>
          <div className="flex items-center gap-2 border-b border-[var(--or-line)] px-4 py-3">
            {field(sheetInputRef, true)}
            <button type="button" onClick={closeSheet} className="h-12 shrink-0 px-2 text-[16px] font-medium text-[var(--or-ink)]">{tr(locale, "search_close")}</button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-1">
            {q.trim() ? list(false) : <p className="px-4 py-4 text-[14px] text-[var(--or-slate)]">{tr(locale, "search_hint")}</p>}
          </div>
        </div>
      )}
    </>
  );
}
