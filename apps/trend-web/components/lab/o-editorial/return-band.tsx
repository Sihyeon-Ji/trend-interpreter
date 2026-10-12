"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import {
  copy, entryHref, fmtDay, fmtStamp, riskKind, riskTone, riskWord, stageTape,
  type EditionKey, type RiskKind, type SinceItem,
} from "@/lib/lab/o-editorial";
import type { Lifecycle } from "@/lib/types";
import { lastVisit, readScraps, subscribeNothing, subscribeScraps, type Scrap } from "./store";
import { Tape } from "./type";

const SHOW = 4;          // 칸마다 넷 — 나머지는 더 보기(휴대폰에서 세 칸이 위아래로 쌓이면 길다)

function Column({ locale, title, items, render, note, show = SHOW }: {
  locale: Locale; title: string; items: SinceItem[]; render: (i: SinceItem) => React.ReactNode; note?: string; show?: number;
}) {
  const c = copy(locale);
  const [open, setOpen] = useState(false);
  const shown = open ? items : items.slice(0, show);
  return (
    <div className="oe-since-col" data-empty={items.length === 0 || undefined}>
      <h3>{title}</h3>
      {note && <p className="oe-meta" style={{ marginTop: 4 }}>{note}</p>}
      {items.length > 0 && <ul>{shown.map((i) => <li key={`${i.kind}-${i.label}-${i.at}`}>{render(i)}</li>)}</ul>}
      {items.length > show && (
        <button type="button" className="oe-since-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? c.sinceLess : c.sinceMore(items.length - show)}
        </button>
      )}
    </div>
  );
}

/** 지난번 방문 이후 — 새로 실린 밈, 뜻이 바뀐 밈, 검색이 몰린 말. 방문 기록은 이 브라우저에만 있다.
 *  서버는 최근 7일 것을 그리고, 브라우저가 지난번 방문 시각을 읽으면 그 뒤의 것만 남긴다. */
export function SinceLastVisit({ locale, edition, items }: { locale: Locale; edition: EditionKey; items: SinceItem[] }) {
  const c = copy(locale);
  const prev = useSyncExternalStore(subscribeNothing, () => lastVisit() ?? "", () => "");
  const zone = useSyncExternalStore(subscribeNothing, () => Intl.DateTimeFormat().resolvedOptions().timeZone, () => undefined);
  const after = prev ? items.filter((i) => Date.parse(i.at) > Date.parse(prev)) : items;
  const nothingNew = !!prev && after.length === 0;
  const list = nothingNew ? items : after;
  const added = list.filter((i) => i.kind === "verified");
  const changed = list.filter((i) => i.kind === "meaning_changed");
  const spikes = list.filter((i) => i.kind === "spike");
  // 새로 실린 밈이 조심할 밈이면 목록에서도 그 표시를 붙인다 — 들어가 보기 전에 알 수 있게
  const memeLink = (i: SinceItem) => (
    <span className="oe-since-meme">
      {i.termId ? <a className="oe-link" href={entryHref(i.termId, edition)} lang={i.lang}>{i.label}</a> : <span lang={i.lang}>{i.label}</span>}
      {i.risk && <Tape tone={i.risk}>{riskWord(locale, i.risk)}</Tape>}
    </span>
  );

  return (
    <section id="since" aria-labelledby="oe-since" style={{ scrollMarginTop: 16 }}>
      <h2 id="oe-since">{prev ? c.sinceTitle : c.sinceFirstTitle}</h2>
      <p className="oe-meta" style={{ marginTop: 6, fontSize: 15 }}>
        {prev ? c.sinceWhen(fmtStamp(locale, prev, zone)) : c.sinceFirst}
        {nothingNew && <> {c.sinceNone}</>}
      </p>
      {!items.length ? (
        <p style={{ marginTop: 16, fontSize: 16 }}>{c.sinceEmptyWeek}</p>
      ) : (
        <div className="oe-since-cols">
          <Column locale={locale} title={c.sinceNew(added.length)} items={added} render={memeLink} />
          <Column locale={locale} title={c.sinceChanged(changed.length)} items={changed} render={memeLink} />
          <Column locale={locale} title={c.sinceSpikes(spikes.length)} items={spikes} note={spikes.length ? c.spikesNote : undefined} show={3}
            render={(i) => (
              <>
                <span lang={i.lang} style={{ fontWeight: 600 }}>{i.label}</span>
                {i.reason?.[locale] && <span className="oe-meta oe-since-reason">{i.reason[locale]}</span>}
              </>
            )} />
        </div>
      )}
    </section>
  );
}

interface NowCard {
  term_id: string; canonical: string; lang: string; lifecycle: string; diffusion?: string | null;
  risk_level?: string | null; risk_checked_at?: string | null;
}

const EMPTY: Scrap[] = [];
const RISK_KINDS: RiskKind[] = ["none", "caution", "avoid", "unknown", "unchecked"];

/** 내 스크랩 — 스크랩할 때의 단계·쓸 때 조심과 지금을 견준다. 지금 상태는 같은 사이트의 읽기 전용 경로가 가져온다. */
export function MyScraps({ locale, edition }: { locale: Locale; edition: EditionKey }) {
  const c = copy(locale);
  const scraps = useSyncExternalStore(subscribeScraps, readScraps, () => EMPTY);
  const ids = useMemo(() => scraps.map((s) => s.id).join(","), [scraps]);
  const [got, setGot] = useState<{ ids: string; cards: NowCard[] | null } | null>(null);

  useEffect(() => {
    if (!ids) return;
    let live = true;
    fetch(`/lab/o-editorial/api/cards?ids=${encodeURIComponent(ids)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((cards: NowCard[]) => { if (live) setGot({ ids, cards }); })
      .catch(() => { if (live) setGot({ ids, cards: null }); });
    return () => { live = false; };
  }, [ids]);

  const ready = got && got.ids === ids;
  const byId = new Map((ready && got.cards ? got.cards : []).map((x) => [x.term_id, x]));

  return (
    <section id="scraps" aria-labelledby="oe-scraps" style={{ scrollMarginTop: 16 }}>
      <h2 id="oe-scraps">{c.scrapTitle}{scraps.length > 0 && <span className="oe-meta" style={{ marginLeft: 10, fontSize: 15, fontWeight: 600 }}>{scraps.length}</span>}</h2>
      {!scraps.length ? (
        <p className="oe-meta" style={{ marginTop: 10, fontSize: 15, maxWidth: "34em" }}>{c.scrapEmpty}</p>
      ) : (
        <>
          {!ready && <p className="oe-meta" role="status" style={{ marginTop: 10 }}>{c.scrapLoading}</p>}
          {ready && !got.cards && <p className="oe-meta" role="status" style={{ marginTop: 10 }}>{c.scrapFailed}</p>}
          <ul className="oe-scrap-list">
            {scraps.slice(0, 8).map((s) => {
              const now = byId.get(s.id);
              const was = stageTape(locale, { lifecycle: (s.lifecycle ?? "unknown") as Lifecycle, diffusion: s.diffusion });
              const is = now ? stageTape(locale, { lifecycle: now.lifecycle as Lifecycle, diffusion: now.diffusion }) : null;
              const wasKind = RISK_KINDS.includes(s.risk as RiskKind) ? (s.risk as RiskKind) : null;
              const wasRisk = wasKind ? riskWord(locale, wasKind) : null;
              const nowRiskKind = now ? riskKind(now) : null;
              const nowRisk = nowRiskKind ? riskWord(locale, nowRiskKind) : null;
              const moved = !!is && is.text !== was.text;
              const riskMoved = !!nowRisk && !!wasRisk && nowRisk !== wasRisk;
              const rt = nowRiskKind ? riskTone(nowRiskKind) : null;
              return (
                <li key={s.id} className="oe-scrap-item">
                  <a className="oe-scrap-name" href={entryHref(s.id, edition)} lang={s.lang}>{s.name}</a>
                  <span className="oe-tapes" style={{ justifyContent: "flex-end" }}>
                    {is && <span className="oe-tape" data-tone={is.tone}>{is.text}</span>}
                    {rt && nowRisk && <span className="oe-tape" data-tone={rt}>{nowRisk}</span>}
                  </span>
                  <p className="oe-scrap-move oe-meta" data-moved={moved || riskMoved}>
                    {ready && got.cards && !now ? c.scrapGone
                      : moved ? c.scrapMoved(was.text, is!.text)
                        : riskMoved ? c.scrapRiskMoved(wasRisk!, nowRisk!)
                          : ready && got.cards ? `${c.scrapSince(fmtDay(locale, s.at))}. ${c.scrapSame}` : c.scrapSince(fmtDay(locale, s.at))}
                  </p>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
