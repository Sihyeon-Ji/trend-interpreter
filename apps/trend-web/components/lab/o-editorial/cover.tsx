import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { textFor } from "@/lib/explain";
import { langTag } from "@/lib/lang";
import {
  ageName, copy, curvePaths, daysBetween, editionHref, editionName, entryHref, fmtDay, glossOf, hottestAge, regionName,
  riskKind, riskNotes, riskTone, riskWhy, riskWord, stageSentence, stageTapes, xOf,
  type AgeTrend, type EditionKey, type SearchSummary,
} from "@/lib/lab/o-editorial";
import { ledeFor } from "@/lib/lab/o-editorial-server";
import type { KeywordCard, TermRecord } from "@/lib/types";
import { ScrapButton } from "./client";
import { FitName, Tape } from "./type";

const W = 1000;
const H = 100;

/** 커버의 바닥선 — 지금 가장 뜨거운 나이대의 실제 네이버 검색 곡선. 장식이 아니라 '왜 지금' 의 근거다. */
function CoverCurve({ locale, age }: { locale: Locale; age: AgeTrend }) {
  const c = copy(locale);
  const from = age.points[0][0];
  const to = age.end ?? age.points.at(-1)![0];
  const { line, area } = curvePaths(age.points, from, to, W, H);
  const peakX = age.peak ? xOf(age.peak, from, to, W) : null;
  const peakV = age.peak ? age.points.find(([d]) => d.slice(0, 10) === age.peak)?.[1] ?? 100 : null;
  const peakY = peakV !== null ? H - (peakV / 100) * (H - 4) : null;
  const who = ageName(locale, age.gen);
  return (
    <figure className="oe-cover-curve">
      <div style={{ position: "relative" }}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={c.curveCaption(who, fmtDay(locale, from), fmtDay(locale, to))}>
          <line x1={0} x2={W} y1={H - 0.5} y2={H - 0.5} stroke="var(--oe-on-blue-2)" strokeOpacity={0.5} strokeWidth={1} vectorEffect="non-scaling-stroke" />
          <path d={area} fill="#fff" fillOpacity={0.1} />
          <path d={line} fill="none" stroke="#fff" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </svg>
        {peakX !== null && peakY !== null && (
          <span aria-hidden className="oe-curve-peak" style={{ position: "absolute", left: `${(peakX / W) * 100}%`, top: `${(peakY / H) * 100}%`, width: 10, height: 10, marginLeft: -5, marginTop: -5, borderRadius: 999, background: "#fff", boxShadow: "0 0 0 2px var(--oe-blue)" }} />
        )}
        {peakX !== null && (
          <span className="oe-meta oe-curve-peak" style={{ position: "absolute", left: `${(peakX / W) * 100}%`, top: -22, transform: peakX / W > 0.8 ? "translateX(-100%)" : "translateX(-50%)", whiteSpace: "nowrap", color: "#fff", fontWeight: 600 }}>
            {c.curvePeak(fmtDay(locale, age.peak))}
          </span>
        )}
      </div>
      <div className="oe-cover-axis oe-meta oe-num" aria-hidden>
        <span>{fmtDay(locale, from)}</span>
        <span>{fmtDay(locale, to)}</span>
      </div>
      <figcaption className="oe-meta">{c.curveCaption(who, fmtDay(locale, from), fmtDay(locale, to))}</figcaption>
    </figure>
  );
}

/** '왜 지금' — 데이터가 말하는 것만 두 문장 안에서. 마지막 쓰임, 그리고 한국어로 검색된 말이면 가장 뜨거운 나이대의 정점·4주 변화. */
function whyNow(locale: Locale, card: KeywordCard, ref: string, hot: AgeTrend | null): string {
  const c = copy(locale);
  const out: string[] = [];
  const used = card.last_used ?? card.last_seen;
  if (used) out.push(Math.abs(daysBetween(used, ref)) <= 14 ? c.usedRecently(fmtDay(locale, used, ref)) : c.usedLast(fmtDay(locale, used, ref)));
  if (hot?.peak && hot.end && daysBetween(hot.peak, hot.end) <= 21) out.push(c.peakNow(ageName(locale, hot.gen), fmtDay(locale, hot.peak, ref)));
  if (hot && hot.change !== null && hot.change >= 0.15) out.push(c.riseNow(ageName(locale, hot.gen), `${Math.round(hot.change * 100)}%`));
  return out.join(" ");
}

export function Cover({ locale, edition, card, record, search, fallback, generatedAt }: {
  locale: Locale; edition: EditionKey; card: KeywordCard; record: TermRecord | null; search: SearchSummary | null;
  fallback: boolean; generatedAt: string;
}) {
  const c = copy(locale);
  const tx = record ? textFor(record, locale) : null;
  const txLang = locale === "en" && record && !record.en ? "ko" : undefined;
  const g = glossOf(locale, card);
  const lede = tx ? ledeFor(tx, locale) : g.text;
  const ledeLang = tx ? txLang : g.lang;
  const risk = riskKind(card);
  const notes = riskNotes(locale, card.risk_reasons).slice(0, 2);
  const hot = hottestAge(search);
  const why = whyNow(locale, card, generatedAt, hot);
  const canMake = risk !== "avoid";
  const lang = langTag(card.lang);
  const tone = riskTone(risk);

  return (
    <section className="oe-cover" aria-labelledby="oe-cover-name">
      <div className="oe-wrap oe-cover-inner">
        <div className="oe-cover-grid">
          <div className="oe-cover-main">
            <h2 id="oe-cover-name" className="oe-fit oe-cover-name" style={{ margin: 0 }}>
              <FitName name={card.canonical} lang={lang} maxLines={3} splitAbove={4.4} />
            </h2>
            <p className="oe-cover-lede" lang={ledeLang}>{lede}</p>
            {why && <p className="oe-cover-why">{why}</p>}
            <p className="oe-meta" style={{ marginTop: 16, fontSize: 14, maxWidth: "40em" }}>
              {fallback ? c.coverWhyFading(editionName(locale, edition)) : c.coverWhy}
            </p>
          </div>
          <div className="oe-cover-facts">
            <dl style={{ display: "grid", gap: 18 }}>
              <div className="oe-cover-fact">
                <dt>{c.stageLabel}</dt>
                <dd>
                  <span className="oe-tapes">{stageTapes(locale, card).map((s) => <Tape key={s.text} tone={s.tone}>{s.text}</Tape>)}</span>
                  <span style={{ display: "block", marginTop: 8 }}>{stageSentence(locale, card)}</span>
                </dd>
              </div>
              <div className="oe-cover-fact">
                <dt>{c.riskLabel}</dt>
                <dd>
                  {tone ? <Tape tone={tone}>{riskWord(locale, risk)}</Tape> : <strong style={{ fontWeight: 700 }}>{riskWord(locale, risk)}</strong>}
                  <span style={{ display: "block", marginTop: 8 }}>{riskWhy(locale, risk)}</span>
                  {notes.map((n) => <span key={n} style={{ display: "block", marginTop: 4, color: "var(--oe-on-blue-2)" }}>{n}</span>)}
                </dd>
              </div>
              {card.regions.length > 0 && (
                <div className="oe-cover-fact">
                  <dt>{c.whereLabel}</dt>
                  <dd>{card.regions.map((r) => regionName(locale, r)).join(", ")}</dd>
                </div>
              )}
            </dl>
            <div className="oe-cover-actions">
              {canMake && <Link href={`/recommend?term=${encodeURIComponent(card.term_id)}`} className="oe-btn oe-btn-primary">{c.make}</Link>}
              <Link href={entryHref(card.term_id, edition)} className="oe-btn oe-btn-line">{c.readEntry}</Link>
              <ScrapButton locale={locale} scrap={{ id: card.term_id, name: card.canonical, lang, lifecycle: card.lifecycle, diffusion: card.diffusion ?? null, risk }} />
            </div>
          </div>
        </div>
        {hot && <CoverCurve locale={locale} age={hot} />}
      </div>
    </section>
  );
}

/** 이 판에 실을 밈이 없을 때 — 비었다고 숨기지 않고, 무엇을 하면 되는지 알린다. */
export function EmptyCover({ locale, edition, counts, avoidOnly, spikes }: {
  locale: Locale; edition: EditionKey; counts: Record<string, number> | null; avoidOnly: number; spikes: number;
}) {
  const c = copy(locale);
  const title = c.emptyCoverTitle(editionName(locale, edition));
  const others = (["KR", "JP", "GLOBAL"] as EditionKey[]).filter((e) => e !== edition && (counts?.[e] ?? 0) > 0);
  const body = avoidOnly > 0 ? c.emptyCoverAvoidOnly(avoidOnly) : spikes > 0 ? c.emptyCoverBody : c.emptyCoverQuiet;
  return (
    <section className="oe-cover oe-cover-empty" aria-labelledby="oe-cover-name">
      <div className="oe-wrap oe-cover-inner">
        <h2 id="oe-cover-name" className="oe-fit" style={{ margin: 0 }}>
          <FitName name={title} maxLines={3} splitAbove={6} />
        </h2>
        <p className="oe-cover-lede" style={{ marginTop: 28 }}>{body}</p>
        <div className="oe-cover-actions" style={{ marginTop: 28 }}>
          <Link href={editionHref("ALL")} className="oe-btn oe-btn-primary">{c.emptyCoverAction}</Link>
          {others.map((e) => <Link key={e} href={editionHref(e)} className="oe-btn oe-btn-line">{editionName(locale, e)}</Link>)}
        </div>
      </div>
    </section>
  );
}
