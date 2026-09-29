"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { c, regionName } from "@/lib/lab/f-report-copy";
import { fmtDay } from "@/lib/lab/f-report";

export interface UpdateLite { kind: string; at: string; label: string; term_id?: string | null; region?: string | null }
const KEY = "fr:lastVisit";

/* 지난 방문 시각은 페이지를 연 순간 한 번만 읽는다(모듈 변수) — 그 뒤 이번 방문 시각을 적어도 화면은 처음 읽은 값을 유지한다. */
let captured: string | null | undefined;
const noop = () => () => {};
const readPrev = () => (captured === undefined ? (captured = window.localStorage.getItem(KEY)) : captured);

/** '지난 방문 이후' — 서버의 최근 변화(GET /updates)와 브라우저에 적어 둔 마지막 방문 시각을 견준다. 서버는 아무것도 모른다. */
export function SinceVisit({ locale, items }: { locale: Locale; items: UpdateLite[] }) {
  const prev = useSyncExternalStore(noop, readPrev, () => undefined);
  const [hidden, setHidden] = useState(false);
  useEffect(() => { window.localStorage.setItem(KEY, new Date().toISOString()); }, []);
  if (prev === undefined || hidden) return <div className="fr-since" style={{ visibility: "hidden" }} aria-hidden>&nbsp;</div>;
  if (!prev) {
    return (
      <p className="fr-since">
        <span>{c(locale, "since_first")}</span>
        <button type="button" className="fr-since-dismiss" onClick={() => setHidden(true)}>{c(locale, "since_dismiss")}</button>
      </p>
    );
  }
  const since = Date.parse(prev);
  const fresh = items.filter((i) => Date.parse(i.at) > since);
  const verified = fresh.filter((i) => i.kind === "verified" && i.term_id);
  const changed = fresh.filter((i) => i.kind === "meaning_changed" && i.term_id);
  const spikes = fresh.filter((i) => i.kind === "spike");
  const named = [...verified, ...changed].slice(0, 8);
  const when = locale === "ko" ? `${c(locale, "since_prefix")}(${fmtDay(prev)}) ${c(locale, "since_after")}` : `${c(locale, "since_prefix")} (${fmtDay(prev)})`;
  return (
    <div className="fr-since" role="status">
      <span>{when}</span>
      {fresh.length === 0 ? (
        <span className="fr-steel">{c(locale, "since_none")}</span>
      ) : (
        <>
          <span><b className="fr-num">{verified.length}</b> {c(locale, "since_verified")}</span>
          <span><b className="fr-num">{changed.length}</b> {c(locale, "since_changed")}</span>
          <span title={c(locale, "since_spike_note")}><b className="fr-num">{spikes.length}</b> {c(locale, "since_spike")}</span>
          {named.length > 0 && (
            <span className="fr-since-items">
              {named.map((i) => (
                <Link key={`${i.kind}-${i.term_id}`} href={`/lab/f-report/m/${encodeURIComponent(i.term_id!)}`} prefetch={false}>
                  <span lang={scriptLang(i.label, i.region) ?? langTag(undefined)}>{i.label}</span>{i.region ? <span className="fr-steel"> {regionName(locale, i.region)}</span> : null}
                </Link>
              ))}
            </span>
          )}
          <Link href="/updates" className="fr-link">{c(locale, "since_all")}</Link>
        </>
      )}
      <button type="button" className="fr-since-dismiss" onClick={() => setHidden(true)}>{c(locale, "since_dismiss")}</button>
    </div>
  );
}
