"use client";

import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { entryHref } from "@/lib/lab/f-editorial";
import { fmtDate, fmtDateTime, regionLabel } from "@/lib/labels";
import { scriptLang } from "@/lib/lang";
import { TARGET_REGIONS } from "@/lib/reader";
import type { UpdateItem } from "@/lib/trends/types";
import { useLastVisit } from "./store";
import type { WatchCardInfo } from "./watchlist";

/* 지난 방문 이후 달라진 것 — 백엔드의 최근 변화(7일)를 브라우저에 남은 지난 방문 시각과 견준다.
   띠(band)는 지난 방문 이후의 건수만, 절(section)은 이번 주 전체를 싣고 지난 방문 뒤의 것에 '새로' 를 붙인다. */
const inScope = (i: UpdateItem, edition: string) => {
  if (i.kind !== "spike") return true;
  if (!i.region) return false;
  if (edition === "ALL") return TARGET_REGIONS.includes(i.region);
  if (edition === "GLOBAL") return true;
  return i.region === edition;
};

function useChanges(items: UpdateItem[], edition: string) {
  const prev = useLastVisit();
  const since = prev ? Date.parse(prev) : NaN;
  const week = items.filter((i) => inScope(i, edition) && (i.kind !== "spike" || !!i.reason));
  const isNew = (i: UpdateItem) => !Number.isNaN(since) && Date.parse(i.at) > since;
  const groups = {
    verified: week.filter((i) => i.kind === "verified"),
    changed: week.filter((i) => i.kind === "meaning_changed"),
    spike: week.filter((i) => i.kind === "spike"),
  };
  return { prev, week, isNew, groups };
}

export function ChangesBand({ items, locale, edition }: { items: UpdateItem[]; locale: Locale; edition: string }) {
  const { prev, week, isNew, groups } = useChanges(items, edition);
  const scoped = prev ? week.filter(isNew) : week;
  const count = (k: keyof typeof groups) => (prev ? groups[k].filter(isNew) : groups[k]).length;
  const title = prev ? fe(locale, "ch_since", { date: fmtDate(prev) }) : fe(locale, "ch_week");
  const parts = [
    [count("verified"), fe(locale, "ch_verified")],
    [count("changed"), fe(locale, "ch_changed")],
    [count("spike"), fe(locale, "ch_spike")],
  ].filter(([n]) => (n as number) > 0);
  return (
    <div className="fe-band">
      <div className="fe-wrap fe-band__row">
        <p>
          {scoped.length === 0 ? (
            fe(locale, prev ? "ch_none" : "ch_none_week")
          ) : (
            <>
              {title}: <span className="fe-band__count">{fe(locale, "ch_count", { n: scoped.length })}</span>
              {" — "}
              {parts.map(([n, label], i) => <span key={label}>{i > 0 && ", "}{label} {n}</span>)}
            </>
          )}
        </p>
        {week.length > 0 && <a href="#fe-changes" className="fe-link">{fe(locale, "ch_jump")}</a>}
      </div>
    </div>
  );
}

const MAX = 6;

export function ChangesSection({ items, locale, edition, known = [] }: { items: UpdateItem[]; locale: Locale; edition: string; known?: WatchCardInfo[] }) {
  const { prev, week, isNew, groups } = useChanges(items, edition);
  const byId = new Map(known.map((c) => [c.id, c]));
  if (week.length === 0) return null;
  const tag = (i: UpdateItem) => isNew(i) && <span className="fe-new">{fe(locale, "ch_new")}</span>;
  // 이번 호에 실린 밈이면 단계·조심을 같이(시각보다 쓸모 있다), 아니면 실린 때
  const stageOf = (i: UpdateItem) => {
    const c = i.term_id ? byId.get(i.term_id) : undefined;
    if (!c) return <span className="fe-changes__sub">{fmtDateTime(i.at, locale)}</span>;
    return (
      <span className="fe-stickers" style={{ marginTop: 4 }}>
        <span className="fe-sticker">{c.stage}</span>
        {c.risk && <span className={`fe-sticker fe-sticker--${c.riskKey === "unknown" ? "muted" : c.riskKey}`}>{c.risk}</span>}
      </span>
    );
  };
  const col = (key: keyof typeof groups, title: string, note?: string) => {
    const list = groups[key];
    if (!list.length) return null;
    return (
      <div className="fe-changes__col">
        <h3 className="fe-h3">{title} <span>{list.length}</span></h3>
        {note && <p className="fe-changes__note">{note}</p>}
        <ul className="fe-changes__list">
          {list.slice(0, MAX).map((i, n) => (
            <li key={`${i.kind}-${i.term_id ?? i.label}-${n}`} className="fe-changes__item">
              <span className="fe-changes__name">
                {i.term_id ? <Link href={entryHref(i.term_id, edition)} lang={scriptLang(i.label, i.region)}>{i.label}</Link> : <span lang={scriptLang(i.label, i.region)}>{i.label}</span>}
                {tag(i)}
              </span>
              {i.kind === "meaning_changed" && i.previous && <span className="fe-changes__sub" lang="ko">{fe(locale, "ch_prev")}: {i.previous}</span>}
              {i.kind === "spike" && i.reason && <span className="fe-changes__sub">{i.region && edition !== i.region ? `${regionLabel(locale, i.region)} — ` : ""}{i.reason[locale]}</span>}
              {i.kind === "verified" && stageOf(i)}
            </li>
          ))}
        </ul>
        {list.length > MAX && <p className="fe-changes__note">{fe(locale, "ch_more", { n: list.length - MAX })}</p>}
      </div>
    );
  };
  return (
    <section id="fe-changes" className="fe-changes" aria-labelledby="fe-changes-title">
      <div className="fe-rubric__head">
        <h2 id="fe-changes-title" className="fe-h2">{fe(locale, "ch_week")}</h2>
        {prev && <p className="fe-rubric__note">{fe(locale, "ch_since", { date: fmtDateTime(prev, locale) })}: {fe(locale, "ch_count", { n: week.filter(isNew).length })}</p>}
      </div>
      <div className="fe-changes__cols">
        {col("verified", fe(locale, "ch_verified"))}
        {col("changed", fe(locale, "ch_changed"))}
        {col("spike", fe(locale, "ch_spike"), fe(locale, "ch_spike_note"))}
      </div>
    </section>
  );
}
