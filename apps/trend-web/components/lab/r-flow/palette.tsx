"use client";

/* 명령 팔레트(⌘K) — 밈 찾기와 바로 가기. 초점은 입력 칸에 머물고 고른 줄은 aria-activedescendant 로 알린다.
   키보드로 움직이는 선택은 애니메이션하지 않는다(자주 되풀이되는 동작). 열릴 때만 짧게 떠오른다. */
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Compass, CornerDownLeft, Languages, Plus, Search } from "lucide-react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { MARKETS, marketName, tr } from "./copy";
import { rememberMeme, recentMemes, useStore } from "./store";

const BASE = "/lab/r-flow";

interface Hit { id: string; name: string; lang: string; gloss: string; pending?: boolean; risk: string | null; life: string | null }
type Item =
  | { kind: "cmd"; id: string; label: string; icon: "new" | "explore" | "lang"; run: () => void }
  | { kind: "meme"; id: string; hit: Hit };

const riskWord = (locale: Locale, r: string | null) =>
  r === "avoid" ? tr(locale, "risk_avoid") : r === "caution" ? tr(locale, "risk_caution") : null;

export function Palette({ locale, onClose, onLocale }: { locale: Locale; onClose: () => void; onLocale: (l: Locale) => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [res, setRes] = useState<{ q: string; items: Hit[]; error?: boolean } | null>(null);
  const recent = useStore(recentMemes);
  const input = useRef<HTMLInputElement>(null);
  const back = useRef<Element | null>(null);
  const query = q.trim();

  useEffect(() => {
    back.current = document.activeElement;
    input.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
      if (back.current instanceof HTMLElement) back.current.focus();
    };
  }, []);

  // 찾기: 입력이 멈추고 120ms 뒤 한 번. 결과는 그 질의와 함께 담아 '찾는 중' 을 따로 두지 않는다
  useEffect(() => {
    if (!query) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      fetch(`${BASE}/api/search?q=${encodeURIComponent(query)}&locale=${locale}`, { signal: ctrl.signal })
        .then(async (r) => {
          if (!r.ok) throw new Error(String(r.status));
          const j = (await r.json()) as { items: Hit[] };
          setRes({ q: query, items: j.items });
        })
        .catch(() => { if (!ctrl.signal.aborted) setRes({ q: query, items: [], error: true }); });
    }, 120);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [query, locale]);

  const open = (hit: Pick<Hit, "id" | "name" | "lang">) => {
    rememberMeme({ id: hit.id, name: hit.name, lang: hit.lang });
    onClose();
    router.push(`${BASE}/term/${encodeURIComponent(hit.id)}`);
  };

  const commands = useMemo<Item[]>(() => {
    const all: Item[] = [
      { kind: "cmd", id: "new", label: tr(locale, "pl_cmd_new"), icon: "new", run: () => router.push(BASE) },
      ...MARKETS.map((m): Item => ({ kind: "cmd", id: `ex-${m}`, label: tr(locale, "pl_cmd_explore", { market: marketName(locale, m) }), icon: "explore", run: () => router.push(`${BASE}/explore?m=${m}`) })),
      { kind: "cmd", id: "lang", label: tr(locale, "pl_cmd_lang"), icon: "lang", run: () => onLocale(locale === "ko" ? "en" : "ko") },
    ];
    if (!query) return all;
    const n = query.toLowerCase();
    return all.filter((c) => c.kind === "cmd" && c.label.toLowerCase().includes(n));
  }, [locale, query, router, onLocale]);

  const memes: Item[] = query
    ? (res?.q === query ? res.items : []).map((hit) => ({ kind: "meme", id: hit.id, hit }))
    : recent.map((r) => ({ kind: "meme", id: r.id, hit: { ...r, gloss: "", risk: null, life: null } }));
  const items = [...memes, ...commands];
  const loading = !!query && res?.q !== query;
  const at = items.length ? Math.min(active, items.length - 1) : -1;

  const run = (it: Item) => {
    if (it.kind === "meme") open(it.hit);
    else { onClose(); it.run(); }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) setActive((at + 1) % items.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) setActive((at - 1 + items.length) % items.length); }
    else if (e.key === "Enter") { e.preventDefault(); if (at >= 0) run(items[at]); }
    else if (e.key === "Tab") e.preventDefault();   // 초점은 입력 칸에만
  };

  useEffect(() => {
    if (at < 0) return;
    document.getElementById(`rf-pal-${at}`)?.scrollIntoView({ block: "nearest" });
  }, [at]);

  const icon = (k: "new" | "explore" | "lang") =>
    k === "new" ? <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> : k === "explore" ? <Compass size={16} strokeWidth={1.75} aria-hidden="true" /> : <Languages size={16} strokeWidth={1.75} aria-hidden="true" />;

  const row = (it: Item, idx: number) => {
    const sel = idx === at;
    if (it.kind === "cmd") {
      return (
        <li key={it.id} id={`rf-pal-${idx}`} role="option" aria-selected={sel} className="rf-pal-item" onMouseMove={() => { if (!sel) setActive(idx); }} onClick={() => run(it)}>
          {icon(it.icon)}
          <b style={{ fontWeight: 550 }}>{it.label}</b>
          {sel ? <CornerDownLeft size={14} strokeWidth={1.75} aria-hidden="true" /> : <span />}
        </li>
      );
    }
    const risk = riskWord(locale, it.hit.risk);
    return (
      <li key={it.id} id={`rf-pal-${idx}`} role="option" aria-selected={sel} className="rf-pal-item" onMouseMove={() => { if (!sel) setActive(idx); }} onClick={() => run(it)}>
        <Search size={15} strokeWidth={1.75} aria-hidden="true" />
        <span style={{ minWidth: 0 }}>
          <b lang={langTag(it.hit.lang)}>{it.hit.name}</b>
          {it.hit.gloss ? <p lang={locale === "en" && it.hit.pending ? "ko" : undefined}>{it.hit.gloss}</p> : null}
        </span>
        {risk ? <span className="rf-risk" data-r={it.hit.risk ?? ""}>{risk}</span> : sel ? <CornerDownLeft size={14} strokeWidth={1.75} aria-hidden="true" /> : <span />}
      </li>
    );
  };

  return (
    <div className="rf-pal-wrap" data-enter="true" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
        <div className="rf-pal" data-enter="true" role="dialog" aria-modal="true" aria-label={tr(locale, "pl_title")}>
          <div className="rf-pal-input">
            <Search size={18} strokeWidth={1.75} aria-hidden="true" />
            <input
              ref={input} value={q} placeholder={tr(locale, "pl_ph")} aria-label={tr(locale, "pl_ph")}
              role="combobox" aria-expanded="true" aria-controls="rf-pal-list" aria-autocomplete="list"
              aria-activedescendant={at >= 0 ? `rf-pal-${at}` : undefined}
              onChange={(e) => { setQ(e.target.value); setActive(0); }} onKeyDown={onKey}
            />
            <span className="rf-kbd" aria-hidden="true">esc</span>
          </div>
          <ul className="rf-pal-list" id="rf-pal-list" role="listbox" aria-label={tr(locale, "pl_title")}>
            {memes.length > 0 && <li role="presentation" className="rf-pal-group">{query ? tr(locale, "pl_memes") : tr(locale, "pl_recent")}</li>}
            {memes.map((it, k) => row(it, k))}
            {query && loading && <li role="presentation" className="rf-pal-msg">{tr(locale, "pl_loading")}</li>}
            {query && !loading && res?.error && <li role="presentation" className="rf-pal-msg">{tr(locale, "pl_error")}</li>}
            {query && !loading && !res?.error && memes.length === 0 && (
              <li role="presentation" className="rf-pal-msg">{tr(locale, "pl_none", { q: query })} {tr(locale, "pl_none_hint")}</li>
            )}
            {commands.length > 0 && <li role="presentation" className="rf-pal-group">{tr(locale, "pl_go")}</li>}
            {commands.map((it, k) => row(it, memes.length + k))}
          </ul>
          <p className="rf-sr" aria-live="polite">{query && !loading ? tr(locale, "pl_results", { n: memes.length }) : ""}</p>
          <div className="rf-pal-foot" aria-hidden="true">
            <span><span className="rf-kbd">↑</span><span className="rf-kbd">↓</span>{tr(locale, "pl_move")}</span>
            <span><span className="rf-kbd">↵</span>{tr(locale, "pl_open")}</span>
            <span><span className="rf-kbd">esc</span>{tr(locale, "pl_close")}</span>
          </div>
        </div>
    </div>
  );
}
