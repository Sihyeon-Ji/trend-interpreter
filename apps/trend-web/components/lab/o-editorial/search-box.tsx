"use client";

/* 찾기 칸 — '이 밈, 써도 되나' 를 올리기 직전 몇 초 안에. 치는 동안 확인된 사전의 밈을 이름·뜻 한 줄·쓸 때 조심과 함께 바로 보인다.
   스크립트가 없거나 사전을 못 받으면 평범한 GET 폼(/search?q=)으로 그대로 동작한다. 색인은 칸을 처음 쓸 때 한 번 받는다. */
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { BASE, copy, entryHref, riskTone, riskWord, type RiskKind } from "@/lib/lab/o-editorial";
import type { IndexEntry } from "@/lib/lab/o-editorial/data";

const norm = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[\s·・\-_'’"“”.,!?~]+/g, "");

/** 찾기 쪽(searchDictionary)과 같은 순서 — 이름이 같으면 먼저, 이름의 앞머리, 이름 안, 다른 표기, 뜻 */
function score(it: IndexEntry, q: string): number {
  const name = norm(it.name);
  if (name === q) return 0;
  if (name.startsWith(q)) return 1;
  if (name.includes(q)) return 2;
  if (it.aliases.some((a) => norm(a).includes(q))) return 3;
  if (norm(it.gloss).includes(q)) return 4;
  return 99;
}

type Index = { status: "idle" | "loading" | "ready" | "failed"; items: IndexEntry[] };

export function SearchBox({ locale, id, className = "", defaultValue = "", big = false }: {
  locale: Locale; id: string; className?: string; defaultValue?: string; big?: boolean;
}) {
  const c = copy(locale);
  const router = useRouter();
  const [q, setQ] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [index, setIndex] = useState<Index>({ status: "idle", items: [] });
  const listId = `${id}-list`;

  const load = () => {
    if (index.status === "loading" || index.status === "ready") return;
    setIndex({ status: "loading", items: [] });
    fetch(`${BASE}/api/index?l=${locale}`)
      .then((r) => (r.ok ? (r.json() as Promise<IndexEntry[]>) : Promise.reject(new Error(String(r.status)))))
      .then((items) => setIndex({ status: "ready", items }))
      .catch(() => setIndex({ status: "failed", items: [] }));
  };

  const results = useMemo(() => {
    const key = norm(q);
    if (!key) return [];
    return index.items.map((it) => ({ it, s: score(it, key) })).filter((x) => x.s < 99)
      .sort((a, b) => a.s - b.s || a.it.name.length - b.it.name.length).slice(0, 6).map((x) => x.it);
  }, [q, index.items]);

  const term = q.trim();
  const showList = open && term.length > 0;
  const allIndex = results.length;                       // 마지막 줄 '결과 모두 보기'
  const optionId = (i: number) => `${id}-opt-${i}`;
  // 지금 보고 있는 판을 기사로 넘긴다(주소에서 읽는다 — useSearchParams 없이)
  const hrefFor = (termId: string) => {
    const regions = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("regions") : null;
    return `${entryHref(termId)}${regions ? `?regions=${encodeURIComponent(regions)}` : ""}`;
  };
  const allHref = `${BASE}/search?q=${encodeURIComponent(term)}`;
  const go = (href: string) => {
    setOpen(false);
    setActive(-1);
    router.push(href);
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); load(); setOpen(true); setActive((a) => Math.min(allIndex, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(-1, a - 1)); }
    else if (e.key === "Escape") { if (open) { e.preventDefault(); setOpen(false); setActive(-1); } }
    else if (e.key === "Enter" && showList && active >= 0) {
      e.preventDefault();
      go(active < allIndex ? hrefFor(results[active].id) : allHref);
    }
  };

  const status = index.status === "loading" ? c.suggestLoading
    : index.status === "failed" ? c.suggestFailed
      : index.status === "ready" && !results.length ? c.suggestEmpty : "";

  return (
    <form action={`${BASE}/search`} method="get" role="search" className={`oe-search ${big ? "oe-search-big" : ""} ${className}`}>
      <label htmlFor={id} className="oe-sr">{c.searchLabel}</label>
      <div className="oe-suggest">
        <input
          id={id}
          name="q"
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          placeholder={c.searchPlaceholder}
          autoComplete="off"
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1); load(); }}
          onFocus={() => { load(); setOpen(true); }}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKey}
        />
        {showList && (
          <div className="oe-suggest-panel">
            {status && <p className="oe-suggest-status">{status}</p>}
            <ul id={listId} role="listbox" aria-label={c.searchLabel}>
              {results.map((r, i) => {
                const tone = riskTone(r.risk as RiskKind);
                return (
                  <li key={r.id} id={optionId(i)} role="option" aria-selected={i === active} className="oe-suggest-item"
                    onMouseDown={(e) => { e.preventDefault(); go(hrefFor(r.id)); }} onMouseEnter={() => setActive(i)}>
                    <span className="oe-suggest-text">
                      <span className="oe-suggest-name" lang={r.lang}>{r.name}</span>
                      {r.gloss && <span className="oe-suggest-gloss" lang={r.glossLang}>{r.gloss}</span>}
                    </span>
                    {tone ? <span className="oe-tape" data-tone={tone}>{riskWord(locale, r.risk as RiskKind)}</span>
                      : <span className="oe-suggest-safe">{riskWord(locale, r.risk as RiskKind)}</span>}
                  </li>
                );
              })}
              <li id={optionId(allIndex)} role="option" aria-selected={active === allIndex} className="oe-suggest-item oe-suggest-all"
                onMouseDown={(e) => { e.preventDefault(); go(allHref); }} onMouseEnter={() => setActive(allIndex)}>
                {c.suggestAll(term)}
              </li>
            </ul>
          </div>
        )}
        <p className="oe-sr" aria-live="polite">{showList && index.status === "ready" ? (results.length ? c.suggestCount(results.length) : c.suggestEmpty) : ""}</p>
      </div>
      <button type="submit">{c.searchButton}</button>
    </form>
  );
}
