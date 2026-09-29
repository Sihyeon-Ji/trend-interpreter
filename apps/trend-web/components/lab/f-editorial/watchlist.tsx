"use client";

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { entryHref } from "@/lib/lab/f-editorial";
import { langTag } from "@/lib/lang";
import { toggleWatch, useWatchlist, type WatchItem } from "./store";

function Star({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M12 3.5l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17.5 6.6 20.4l1-6.1-4.4-4.3 6.1-.9z" />
    </svg>
  );
}

/** 별표 — 누르면 이 브라우저의 내 목록에 담긴다. 서버 렌더에서는 빈 별로 나온다. */
export function StarButton({ item, locale }: { item: WatchItem; locale: Locale }) {
  const on = useWatchlist().some((x) => x.id === item.id);
  const label = fe(locale, on ? "watch_remove" : "watch_add");
  return (
    <button type="button" className="fe-star" aria-pressed={on} aria-label={label} title={label} onClick={() => toggleWatch(item)}>
      <Star filled={on} />
    </button>
  );
}

/** 제호 오른쪽의 '내 목록 n' */
export function WatchCount({ locale, href }: { locale: Locale; href: string }) {
  const n = useWatchlist().length;
  return (
    <a href={href} className="fe-quiet">
      {fe(locale, "watch")}{n > 0 && <span className="fe-count"> {n}</span>}
    </a>
  );
}

export interface WatchCardInfo { id: string; stage: string; risk: string | null; riskKey: string | null }

/** 내가 지켜보는 밈 — 이번 호에 실린 것은 단계·조심을 같이 보이고, 없는 것은 없다고 말한다. */
export function WatchSection({ locale, edition, cards }: { locale: Locale; edition: string; cards: WatchCardInfo[] }) {
  const items = useWatchlist();
  const byId = new Map(cards.map((c) => [c.id, c]));
  return (
    <section id="fe-watch" className="fe-watch" aria-labelledby="fe-watch-title">
      <div className="fe-rubric__head">
        <h2 id="fe-watch-title" className="fe-h2">{fe(locale, "watch_title")}{items.length > 0 && <span className="fe-rubric__count">{items.length}</span>}</h2>
        <p className="fe-rubric__note">{fe(locale, "watch_note")}</p>
      </div>
      {items.length === 0 ? (
        <p className="fe-watch__empty">{fe(locale, "watch_empty")}</p>
      ) : (
        <ul className="fe-watch__list">
          {items.map((it) => {
            const c = byId.get(it.id);
            return (
              <li key={it.id} className="fe-watch__item">
                <span className="fe-watch__name"><Link href={entryHref(it.id, edition)} lang={langTag(it.lang)}>{it.name}</Link></span>
                <span className="fe-watch__right">
                  {c ? (
                    <span className="fe-stickers">
                      <span className="fe-sticker">{c.stage}</span>
                      {c.risk && <span className={`fe-sticker fe-sticker--${c.riskKey === "unknown" ? "muted" : c.riskKey}`}>{c.risk}</span>}
                    </span>
                  ) : <span className="fe-cell__meta">{fe(locale, "watch_not_here")}</span>}
                  <button type="button" className="fe-watch__remove" onClick={() => toggleWatch(it)}>{fe(locale, "watch_remove_short")}</button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
