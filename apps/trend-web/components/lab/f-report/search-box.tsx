"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { c } from "@/lib/lab/f-report/copy";
import { searchHits, type SearchHit } from "@/lib/lab/f-report/search";

/* 색인은 칸을 처음 쓸 때 한 번 받는다(확인된 밈의 이름·다른 표기·뜻 한 줄, 수십 KB). */
let indexPromise: Promise<SearchHit[] | null> | null = null;
let indexLocale = "";
function loadIndex(locale: Locale) {
  if (!indexPromise || indexLocale !== locale) {
    indexLocale = locale;
    indexPromise = fetch(`/lab/f-report/api/search?locale=${locale}`).then((r) => (r.ok ? (r.json() as Promise<SearchHit[]>) : null)).catch(() => null);
  }
  return indexPromise;
}
const entryHref = (id: string) => `/lab/f-report/m/${encodeURIComponent(id)}`;

/** 틀의 찾기 칸 — 사전 전체를 바로 찾는 콤보박스. 고른 항목은 밈 항목으로, 그냥 Enter 는 리포트 목록을 그 말로 거른다. 시장 선택은 그대로 둔다. */
export function SearchBox({ locale }: { locale: Locale }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [index, setIndex] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const form = useRef<HTMLFormElement>(null);

  const ensure = () => {
    if (status !== "idle") return;
    setStatus("loading");
    loadIndex(locale).then((v) => { if (v) { setIndex(v); setStatus("ready"); } else setStatus("failed"); });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const hits = status === "ready" ? searchHits(index, q) : [];
  const showList = open && q.trim().length > 0;
  const filterHref = () => {
    const next = new URLSearchParams();
    const regions = sp.get("regions");
    if (regions) next.set("regions", regions);
    if (q.trim()) next.set("q", q.trim().slice(0, 60));
    return `/lab/f-report${next.size ? `?${next}` : ""}`;
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setOpen(false);
    if (active >= 0 && hits[active]) router.push(entryHref(hits[active].id));
    else router.push(filterHref());
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, -1)); }
  };

  return (
    <form className="fr-search" role="search" onSubmit={submit} ref={form}
      onBlur={(e) => { if (!form.current?.contains(e.relatedTarget as Node | null)) setOpen(false); }}>
      <label htmlFor="fr-q" className="sr-only">{c(locale, "search_label")}</label>
      <svg width="15" height="15" viewBox="0 0 20 20" aria-hidden className="fr-steel"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M13 13l4.5 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
      <input id="fr-q" name="q" value={q} role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1); ensure(); }}
        onFocus={() => { ensure(); setOpen(true); }} onKeyDown={onKeyDown}
        placeholder={c(locale, "search_placeholder")} autoComplete="off" />
      <button type="submit">{c(locale, "search_button")}</button>
      {showList && (
        <div className="fr-search-pop">
          {status === "loading" && <p className="fr-search-note">{c(locale, "search_loading")}</p>}
          {status === "ready" && hits.length === 0 && <p className="fr-search-note">{c(locale, "search_none")}</p>}
          <ul role="listbox" id={listId} aria-label={c(locale, "search_results")} className="fr-search-list">
            {hits.map((h, i) => (
              <li key={h.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}>
                <Link href={entryHref(h.id)} prefetch={false} tabIndex={-1} onMouseDown={(e) => e.preventDefault()} onClick={() => setOpen(false)}>
                  <b lang={langTag(h.lang)}>{h.name}</b>
                  {h.risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
                  {h.risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
                  {h.gloss && <span className="fr-search-gloss">{h.gloss}</span>}
                </Link>
              </li>
            ))}
          </ul>
          <p className="fr-search-foot"><button type="submit" className="fr-link" tabIndex={-1} onMouseDown={(e) => e.preventDefault()}>{c(locale, "search_filter_list")} ‘{q.trim()}’</button></p>
        </div>
      )}
    </form>
  );
}
