"use client";

import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { entryHref } from "@/lib/lab/f-editorial";
import { fmtDate } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { Lifecycle } from "@/lib/types";
import { lifecycleWord, riskClass, riskLabel, type RiskKey } from "./stickers";
import { toggleWatch, useWatchlist, type WatchItem } from "./store";

/** 담을 때 같이 적어 두는 지금 상태 */
export interface WatchState { stage: Lifecycle; risk: RiskKey | null }

function Star({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M12 3.5l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17.5 6.6 20.4l1-6.1-4.4-4.3 6.1-.9z" />
    </svg>
  );
}

/** 별표 — 누르면 이 브라우저의 내 목록에 담긴다(지금 단계·조심 수준과 함께). 서버 렌더에서는 빈 별로 나온다. */
export function StarButton({ item, state, locale }: { item: WatchItem; state?: WatchState; locale: Locale }) {
  const on = useWatchlist().some((x) => x.id === item.id);
  const label = fe(locale, on ? "watch_remove" : "watch_add");
  const save = () => toggleWatch({ ...item, stage: state?.stage, risk: state?.risk ?? undefined });
  return (
    <button type="button" className="fe-star" aria-pressed={on} aria-label={label} title={label} onClick={save}>
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

const asLifecycle = (s: string | undefined): Lifecycle | null => (s ? (s as Lifecycle) : null);
const asRisk = (s: string | undefined): RiskKey | null => (s === "caution" || s === "avoid" || s === "unknown" || s === "none" ? s : null);

/** 담을 때와 지금이 다르면 그 문장들, 같으면 빈 목록 */
function diffLines(it: WatchItem, now: WatchState, locale: Locale): string[] {
  const out: string[] = [];
  const was = asLifecycle(it.stage);
  if (was && was !== now.stage) out.push(fe(locale, "watch_stage_moved", { from: lifecycleWord(locale, was), to: lifecycleWord(locale, now.stage) }));
  const wasRisk = asRisk(it.risk);
  if (wasRisk && now.risk && wasRisk !== now.risk) out.push(fe(locale, "watch_risk_moved", { from: riskLabel(locale, wasRisk), to: riskLabel(locale, now.risk) }));
  return out;
}

/** 항목 머리에서 — 이 밈을 담아 두었고 그 뒤 단계·조심이 바뀌었으면 그렇다고 말한다 */
export function WatchDiff({ id, state, locale }: { id: string; state: WatchState; locale: Locale }) {
  const it = useWatchlist().find((x) => x.id === id);
  if (!it) return null;
  const lines = diffLines(it, state, locale);
  if (!lines.length) return null;
  return <p className="fe-entry__note">{lines.map((l, i) => <span key={i}>{i > 0 && <br />}{l}</span>)}</p>;
}

export interface WatchCardInfo { id: string; lifecycle: Lifecycle; risk: RiskKey | null }

/** 내가 지켜보는 밈 — 이번 호에 실린 것은 지금 단계·조심과 담은 뒤 달라진 점을, 없는 것은 없다고 말한다. 비어 있으면 한 줄. */
export function WatchSection({ locale, edition, cards }: { locale: Locale; edition: string; cards: WatchCardInfo[] }) {
  const items = useWatchlist();
  const byId = new Map(cards.map((c) => [c.id, c]));
  if (items.length === 0) {
    return (
      <section id="fe-watch" className="fe-rubric-line" aria-labelledby="fe-watch-title">
        <h2 id="fe-watch-title" className="fe-rubric-line__title">{fe(locale, "watch_title")}</h2>
        <p>{fe(locale, "watch_empty")}</p>
      </section>
    );
  }
  return (
    <section id="fe-watch" className="fe-watch" aria-labelledby="fe-watch-title">
      <div className="fe-rubric__head">
        <h2 id="fe-watch-title" className="fe-h2">{fe(locale, "watch_title")}<span className="fe-rubric__count">{items.length}</span></h2>
        <p className="fe-rubric__note">{fe(locale, "watch_note")}</p>
      </div>
      <ul className="fe-watch__list">
        {items.map((it) => {
          const c = byId.get(it.id);
          const lines = c ? diffLines(it, { stage: c.lifecycle, risk: c.risk }, locale) : [];
          return (
            <li key={it.id} className="fe-watch__item">
              <div className="fe-watch__main">
                <span className="fe-watch__name"><Link href={entryHref(it.id, edition)} lang={langTag(it.lang)}>{it.name}</Link></span>
                <span className="fe-watch__sub">
                  {c ? (lines.length ? lines.map((l, i) => <span key={i}>{i > 0 && <br />}{l}</span>) : it.at ? fe(locale, "watch_same") : null) : fe(locale, "watch_not_here")}
                  {it.at && <span className="fe-watch__date">{fe(locale, "watch_saved", { date: fmtDate(it.at) })}</span>}
                </span>
              </div>
              <span className="fe-watch__right">
                {c && (
                  <span className="fe-stickers">
                    <span className="fe-sticker">{lifecycleWord(locale, c.lifecycle)}</span>
                    {c.risk && c.risk !== "none" && <span className={riskClass(c.risk)}>{riskLabel(locale, c.risk)}</span>}
                  </span>
                )}
                <button type="button" className="fe-watch__remove" onClick={() => toggleWatch(it)}>{fe(locale, "watch_remove_short")}</button>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
