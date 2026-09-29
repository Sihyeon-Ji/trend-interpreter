"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { BASE, entryHref } from "@/lib/lab/f-editorial";
import { langTag } from "@/lib/lang";

export interface SearchCard { id: string; name: string; lang: string; gloss: string; glossLang?: string }

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, "");

/* 찾기 — 이번 호의 밈을 바로 거르고(cards 가 있을 때), 제출하면 호 화면이 서버에서 같은 규칙으로 결과를 낸다(자바스크립트 없이도 됨).
   이번 호에 없으면 사전 전체로 안내한다. */
export function SearchBox({ locale, edition, cards, initialQ = "" }: { locale: Locale; edition: string; cards?: SearchCard[]; initialQ?: string }) {
  const [q, setQ] = useState(initialQ);
  const id = useId();
  const router = useRouter();
  const k = norm(q);
  const hits = cards && k ? cards.filter((c) => norm(c.name).includes(k) || norm(c.gloss).includes(k)).slice(0, 7) : [];
  return (
    <form action={BASE} method="get" role="search" className="fe-search" onSubmit={(e) => { if (cards && hits.length === 0 && k) { e.preventDefault(); router.push(`/dictionary?q=${encodeURIComponent(q.trim())}`); } }}>
      <input type="hidden" name="edition" value={edition} />
      <div className="fe-search__row">
        <label htmlFor={id} className="sr-only">{fe(locale, "search_label")}</label>
        <input id={id} name="q" className="fe-search__input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={fe(locale, "search_placeholder")} autoComplete="off" maxLength={80} />
        <button type="submit" className="fe-search__btn">{fe(locale, "search_button")}</button>
      </div>
      {cards && k && (
        <div className="fe-search__results">
          {hits.length > 0 ? (
            <ul>
              {hits.map((c) => (
                <li key={c.id}>
                  <Link href={entryHref(c.id, edition)} className="fe-search__hit">
                    <strong lang={langTag(c.lang)}>{c.name}</strong>
                    <span className="fe-search__gloss" lang={c.glossLang}>{c.gloss}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="fe-search__none">{fe(locale, "search_none")} <a className="fe-link" href={`/dictionary?q=${encodeURIComponent(q.trim())}`}>{fe(locale, "search_whole")}</a></p>
          )}
        </div>
      )}
    </form>
  );
}
