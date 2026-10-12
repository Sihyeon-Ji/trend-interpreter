"use client";

import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { entryHref, type ChangeRow } from "@/lib/lab/f-editorial";
import { fmtDate, fmtDateTime, regionLabel } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import { lifecycleWord, riskClass, riskLabel } from "./stickers";
import { useLastVisit } from "./store";

/* 지난 호 이후 달라진 것 — 서버가 이 판에 맞게 거른 최근 변화(7일)를 브라우저에 남은 지난 방문 시각과 견준다.
   띠(band)는 지난 방문 이후의 건수만, 절(section)은 이번 주 전체를 싣고 지난 방문 뒤의 것에 '새로' 를 붙인다. */
function useChanges(rows: ChangeRow[]) {
  const prev = useLastVisit();
  const since = prev ? Date.parse(prev) : NaN;
  const isNew = (r: ChangeRow) => !Number.isNaN(since) && Date.parse(r.at) > since;
  const groups = {
    verified: rows.filter((r) => r.kind === "verified"),
    changed: rows.filter((r) => r.kind === "meaning_changed"),
    spike: rows.filter((r) => r.kind === "spike"),
  };
  return { prev, isNew, groups };
}

export function ChangesBand({ rows, locale }: { rows: ChangeRow[]; locale: Locale }) {
  const { prev, isNew, groups } = useChanges(rows);
  const scoped = prev ? rows.filter(isNew) : rows;
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
              {title} <span className="fe-band__count">{fe(locale, "ch_count", { n: scoped.length })}</span>
              {": "}
              {parts.map(([n, label], i) => <span key={label}>{i > 0 && ", "}{label} {n}</span>)}
            </>
          )}
        </p>
        {rows.length > 0 && <a href="#fe-changes" className="fe-link">{fe(locale, "ch_jump")}</a>}
      </div>
    </div>
  );
}

const MAX = 5;   // 열마다 다섯 건을 펼치고 나머지는 접는다

export function ChangesSection({ rows, locale, edition }: { rows: ChangeRow[]; locale: Locale; edition: string }) {
  const { prev, isNew, groups } = useChanges(rows);
  if (rows.length === 0) return null;
  const tag = (r: ChangeRow) => isNew(r) && <span className="fe-new">{fe(locale, "ch_new")}</span>;
  const stickers = (r: ChangeRow) => (
    <span className="fe-stickers">
      {r.lifecycle && <span className="fe-sticker">{lifecycleWord(locale, r.lifecycle)}</span>}
      {r.risk && <span className={riskClass(r.risk)}>{riskLabel(locale, r.risk)}</span>}
    </span>
  );
  const item = (r: ChangeRow, n: number) => (
    <li key={`${r.kind}-${r.id ?? r.label}-${n}`} className="fe-changes__item">
      <span className="fe-changes__name">
        {r.id ? <Link href={entryHref(r.id, edition)} lang={langTag(r.lang)}>{r.label}</Link> : <span lang={r.lang}>{r.label}</span>}
        {tag(r)}
      </span>
      {r.kind === "verified" && r.gloss && <span className="fe-changes__sub" lang={r.glossLang}>{r.gloss}</span>}
      {r.kind === "meaning_changed" && r.previous && <span className="fe-changes__sub" lang="ko">{fe(locale, "ch_prev")}: {r.previous}</span>}
      {r.kind === "spike" && r.reason && <span className="fe-changes__sub">{r.region && edition !== r.region ? `${regionLabel(locale, r.region)}. ` : ""}{r.reason}</span>}
      {(r.kind === "verified" || r.kind === "meaning_changed") && stickers(r)}
    </li>
  );
  const col = (key: keyof typeof groups, title: string, note?: string) => {
    const list = groups[key];
    if (!list.length) return null;
    return (
      <div className="fe-changes__col">
        <h3 className="fe-h3">{title} <span>{list.length}</span></h3>
        {note && <p className="fe-changes__note">{note}</p>}
        <ul className="fe-changes__list">{list.slice(0, MAX).map(item)}</ul>
        {list.length > MAX && (
          <details className="fe-rest fe-changes__rest">
            <summary>{fe(locale, "ch_more", { n: list.length - MAX })}</summary>
            <ul className="fe-changes__list">{list.slice(MAX).map((r, i) => item(r, i + MAX))}</ul>
          </details>
        )}
      </div>
    );
  };
  return (
    <section id="fe-changes" className="fe-changes" aria-labelledby="fe-changes-title">
      <div className="fe-rubric__head">
        <h2 id="fe-changes-title" className="fe-h2">{fe(locale, "ch_week")}</h2>
        <p className="fe-rubric__note">
          {prev && <>{fe(locale, "ch_since", { date: fmtDateTime(prev, locale) })}: {fe(locale, "ch_count", { n: rows.filter(isNew).length })}. </>}
          {fe(locale, "ch_scope")}
        </p>
      </div>
      <div className="fe-changes__cols">
        {col("verified", fe(locale, "ch_verified"))}
        {col("changed", fe(locale, "ch_changed"))}
        {col("spike", fe(locale, "ch_spike"), fe(locale, "ch_spike_note"))}
      </div>
    </section>
  );
}
