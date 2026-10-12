"use client";

import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { c, regionName } from "@/lib/lab/f-report/copy";
import { fmtDay } from "@/lib/lab/f-report";
import { useLastVisit } from "./visit";

/** 서버가 고른 시장으로 걸러 내려 준 최근 7일의 변화 한 줄 */
export interface UpdateLite { kind: string; at: string; label: string; term_id?: string | null; region?: string | null; lang?: string | null }

const WEEK = 7 * 86_400_000;

/** "새로 오른 밈 15" / "15 new memes" — 말 순서가 다르다 */
function Count({ n, label, locale, title }: { n: number; label: string; locale: Locale; title?: string }) {
  return locale === "ko"
    ? <span title={title}>{label} <b className="fr-num">{n}</b></span>
    : <span title={title}><b className="fr-num">{n}</b> {label}</span>;
}

/** '지난 방문 이후' — 서버의 최근 변화(GET /updates, 고른 시장만)와 브라우저에 적어 둔 지난 방문 시각을 견준다. 서버는 아무것도 모른다.
 *  처음 왔거나 그사이 바뀐 것이 없으면 이번 주 것을 보인다 — 띠가 비는 일은 없다. */
export function SinceVisit({ locale, items, scoped }: { locale: Locale; items: UpdateLite[]; scoped: boolean }) {
  const visit = useLastVisit();
  if (visit === undefined) return <div className="fr-since" aria-hidden><span className="fr-since-when">&nbsp;</span></div>;
  const base = visit.at ? Date.parse(visit.at) : null;
  const sinceBase = base === null ? [] : items.filter((i) => Date.parse(i.at) > base);
  const weekItems = items.filter((i) => visit.now - Date.parse(i.at) <= WEEK);
  const useWeek = base === null || sinceBase.length === 0;
  const shown = useWeek ? weekItems : sinceBase;
  const verified = shown.filter((i) => i.kind === "verified" && i.term_id);
  const changed = shown.filter((i) => i.kind === "meaning_changed" && i.term_id);
  const spikes = shown.filter((i) => i.kind === "spike");
  const named = [...verified, ...changed].slice(0, 8);
  const old = base !== null && visit.now - base > WEEK;

  let when: string;
  if (base === null) when = c(locale, "since_first");
  else if (useWeek) when = locale === "ko" ? `${c(locale, "since_prefix")}(${fmtDay(visit.at)}) ${c(locale, "since_after")} ${c(locale, "since_none")}` : `${c(locale, "since_prefix")} (${fmtDay(visit.at)}) ${c(locale, "since_none")}`;
  else when = locale === "ko" ? `${c(locale, "since_prefix")}(${fmtDay(visit.at)}) ${c(locale, "since_after")}` : `${c(locale, "since_prefix")} (${fmtDay(visit.at)})`;

  return (
    <div className="fr-since" role="status">
      <span className="fr-since-when">{when}</span>
      <span className="fr-since-counts">
        <Count n={verified.length} label={c(locale, "since_verified")} locale={locale} />
        <Count n={changed.length} label={c(locale, "since_changed")} locale={locale} />
        <Count n={spikes.length} label={c(locale, "since_spike")} locale={locale} title={c(locale, "since_spike_note")} />
      </span>
      {named.length > 0 && (
        <span className="fr-since-items">
          {named.map((i) => (
            <Link key={`${i.kind}-${i.term_id}`} href={`/lab/f-report/m/${encodeURIComponent(i.term_id!)}`} prefetch={false} className={i.kind === "meaning_changed" ? "is-changed" : undefined}>
              <span lang={langTag(i.lang) ?? scriptLang(i.label, i.region)}>{i.label}</span>
              {i.region ? <span className="fr-steel"> {regionName(locale, i.region)}</span> : null}
            </Link>
          ))}
        </span>
      )}
      <span className="fr-since-tail">
        {scoped && <span className="fr-steel">{c(locale, "since_scope")}</span>}
        {old && <span className="fr-steel">{c(locale, "since_week_only")}</span>}
        <Link href="/updates" className="fr-link">{c(locale, "since_all")}</Link>
      </span>
    </div>
  );
}
