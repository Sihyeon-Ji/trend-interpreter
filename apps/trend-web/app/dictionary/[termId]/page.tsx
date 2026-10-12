import type { Metadata } from "next";
import { ArrowLeft, ArrowUpRight, ListChecks, Sparkles, Stamp } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ViewTransition } from "react";
import { ActorTag, MemeWord, Verdict, fmtDay, fmtN, verdictOf, wordVT, type Actor } from "@/components/stage/bits";
import { TrendChart } from "@/components/stage/chart";
import { diffusionWord, isMarket, marketName, tx, type Market } from "@/components/stage/copy";
import { RelGraph, hasGraph } from "@/components/stage/graph";
import { isPartialWeek } from "@/components/trend-chart";
import { getTermRecord, getTermRelated, getTermSignals } from "@/lib/data";
import { measuredUsage } from "@/lib/dictionary/regions";
import { currentMeaning, jaUntranslated, textFor } from "@/lib/explain";
import { t, type Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { L, gap, regionLabel, sep, termLangLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { getViewer } from "@/lib/reader-server";
import { LiveRiskPanel } from "@/components/stage/live-risk";
import { cleanSource } from "@/lib/sources";
import type { Evidence, Meaning } from "@/lib/types";

type Params = { params: Promise<{ termId: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const record = await getTermRecord(termId).catch(() => null);
  return { title: `${record ? record.term.canonical : tx(locale, "nav_explore")} — ${t(locale, "site")}` };
}

const REF_ORDER: Record<string, number> = { wiki: 0, web: 1, news: 2, short: 3 };
const HUMAN = (by?: string | null) => !!by && !/agent|auto|research|tracking/.test(by);

function versionStatus(m: Meaning, locale: Locale) {
  if (m.verification === "verified_human") return { text: tx(locale, "tm_v_human"), who: "human" as Actor };
  if (m.verification === "verified_auto") return { text: tx(locale, "tm_v_auto"), who: "rule" as Actor };
  if (m.verification === "rejected") return { text: tx(locale, "tm_v_rejected"), who: "rule" as Actor };
  return { text: tx(locale, "tm_v_unverified"), who: "rule" as Actor };
}

/* 사전 항목 (Plan 20, 시안 r-stage) — 무대 위에는 원문 표기를 크게, 바로 아래 '써도 되나요'. 그 아래 흰 종이에 뜻·유래·근거·추이·이어진 밈·뜻의 기록.
   둘러보기에서 고른 말은 같은 이름의 보기 전환으로 이 머리글자로 옮겨 온다. 판 번호·확신도 같은 내부 값은 내지 않는다 */
export default async function TermPage({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const asked = [sp.m ?? sp.regions].flat()[0]?.split(",")[0]?.toUpperCase();
  const market: Market | null = isMarket(asked) ? asked : null;
  const [record, related, signals, viewer] = await Promise.all([
    getTermRecord(termId),
    getTermRelated(termId),
    getTermSignals(termId, market ? [market] : []),
    getViewer(),
  ]);
  if (!record) notFound();

  const labels = L(locale);
  const term = record.term;
  const m = currentMeaning(record);
  const text = textFor(record, locale);
  // 일본어판이 없으면 원문 뜻과 '翻訳なし' 안내(영어 화면처럼 원문을 보이되, 일본어 화면은 안내를 붙인다 — 계획서 B §3.4)
  const noJa = locale === "ja" && jaUntranslated(record);
  // 번역이 없으면 원문 — 그 말의 음성으로 읽게(영어 화면은 한국어 원문, 일본어 화면은 원문 글자로 짐작)
  const txLang = locale === "en" && !record.en ? "ko" : noJa ? scriptLang(text?.definition ?? "") ?? "ko" : undefined;
  const verdict = verdictOf({ risk_level: term.risk_level, risk_checked_at: term.risk_checked_at });
  const byHuman = !!term.risk_human;
  const verdictWhy = tx(locale, verdict === "ok" ? "v_ok_why" : verdict === "caution" ? "v_caution_why" : verdict === "avoid" ? "v_avoid_why" : "v_unknown_why");
  const reason = locale === "ko" && (verdict === "caution" || verdict === "avoid") ? term.risk_reasons?.[0] : null;
  const decidedAt = byHuman ? term.risk_decided_at : term.risk_checked_at;
  const canMake = term.status === "verified" && term.risk_level !== "avoid";
  const regions = record.regions ?? m?.regions ?? [];
  // 세대는 데이터랩으로 잰 쓰임에서만 — 뜻의 세대와 다른 출처의 쓰임은 모델 추정이라 실측처럼 보이지 않게 한다 (Plan 15)
  const gens = [...new Set(measuredUsage(record.usage).map((u) => u.segment.generation))].filter((g) => g !== "all");
  const weekly = signals?.weekly ?? record.weekly.slice(-12);
  const hasTrend = weekly.some((p) => p.count > 0);
  const partial = isPartialWeek(weekly.at(-1));
  const m4 = signals?.mentions_4w ?? weekly.slice(-4).reduce((a, p) => a + p.count, 0);
  const refs = record.evidences
    .filter((e: Evidence) => e.kind !== "community" && e.kind !== "datalab")
    .sort((a, b) => (REF_ORDER[a.kind] ?? 9) - (REF_ORDER[b.kind] ?? 9) || b.observed_at.localeCompare(a.observed_at));
  const versions = [...record.meanings].sort((a, b) => b.version - a.version);
  const shownEvidence = refs.length;
  const creator = m?.created_by;
  const how: { who: Actor; text: string }[] = [
    { who: "rule", text: tx(locale, "tm_how1", { n: fmtN(shownEvidence) }) },
    { who: HUMAN(creator) ? "human" : "ai", text: tx(locale, HUMAN(creator) ? "tm_how2_human" : "tm_how2_ai") },
    m?.verification === "verified_human" ? { who: "human", text: tx(locale, "tm_how3_human") }
      : m?.verification === "verified_auto" ? { who: "rule", text: tx(locale, "tm_how3_auto") } : { who: "human", text: tx(locale, "tm_how3_wait") },
    ...(term.risk_checked_at ? [{ who: (byHuman ? "human" : "rule") as Actor, text: tx(locale, "tm_how4") }] : []),
  ];
  const back = market ? `/trends?m=${market}&w=${encodeURIComponent(termId)}` : `/trends`;

  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <section className="rs-stage rs-term" data-scene="term" aria-labelledby="rs-term-h">
        <nav className="rs-crumb" aria-label={tx(locale, "tm_back")}>
          <Link href={back} className="rs-link"><ArrowLeft aria-hidden="true" size={15} />{market ? tx(locale, "tm_back_m", { market: marketName(locale, market) }) : tx(locale, "tm_back")}</Link>
        </nav>
        <div className="rs-term-hero">
          <ViewTransition name={wordVT(termId, market)} share="rs-morph" default="none">
            <h1 id="rs-term-h" className="rs-term-word"><MemeWord text={term.canonical} lang={term.lang} max={168} min={44} /></h1>
          </ViewTransition>
          <p className="rs-term-sub">
            <span>{tx(locale, "tm_lang", { lang: termLangLabel(locale, term.lang ?? "ko") })}</span>
            {term.aliases?.length ? <span>{tx(locale, "tm_aliases")} {term.aliases.slice(0, 4).map((a) => <b key={a} lang={langTag(term.lang)}>{a}</b>)}</span> : null}
          </p>
        </div>
        <div className="rs-term-row">
        <div className="rs-term-verdict" data-kind={verdict}>
          <p className="rs-term-q">{tx(locale, "tm_can")}</p>
          <Verdict kind={verdict} locale={locale} size="l" />
          <p className="rs-term-why">{verdictWhy}</p>
          {reason ? <p className="rs-term-reason" lang="ko">{reason}</p> : null}
          <p className="rs-term-who">
            <ActorTag who={byHuman ? "human" : "rule"} locale={locale}>{tx(locale, byHuman ? "v_by_human" : "v_by_rule")}</ActorTag>
            {decidedAt ? <span>{tx(locale, "v_checked", { date: fmtDay(decidedAt, locale, true) })}</span> : null}
          </p>
        </div>
        <dl className="rs-term-now">
          <div><dt>{tx(locale, "tm_now")}</dt><dd>{term.lifecycle ? labels.lifecycleSentence[term.lifecycle] || labels.lifecycle[term.lifecycle] : "–"}</dd></div>
          {term.diffusion ? <div><dt>{tx(locale, "pk_why_spread")}</dt><dd>{diffusionWord(term.diffusion, locale)}</dd></div> : null}
          {regions.length ? <div><dt>{tx(locale, "tm_regions")}</dt><dd>{regions.map((r) => regionLabel(locale, r)).join(sep(locale))}</dd></div> : null}
          {gens.length ? <div><dt>{tx(locale, "tm_gens")}</dt><dd>{gens.map((g) => labels.generation[g]).join(sep(locale))}</dd></div> : null}
          {/* 검색 관심도는 생애주기와 따로 — 쓰임 단계가 아니라서 '지금 상태' 에 섞지 않는다(10-06 검증, Plan 02) */}
          {term.status === "verified" && term.interest ? (
            <div><dt>{t(locale, "term_sum_interest")}</dt><dd>{t(locale, `interest_${term.interest}`)}<span className="rs-term-now-why">{t(locale, "interest_why")}</span></dd></div>
          ) : null}
        </dl>
        </div>
        {canMake ? (
          <div className="rs-btns rs-term-actions">
            <Link className="rs-btn" data-kind="primary" href={`/?term=${encodeURIComponent(termId)}${market ? `&m=${market}` : ""}`}>{tx(locale, "xp_make")}</Link>
          </div>
        ) : null}
      </section>

      <div className="rs-sheet">
        <div className="rs-sheet-main">
          {text ? (
            <section className="rs-block" aria-labelledby="rs-b-meaning">
              <h2 id="rs-b-meaning">{tx(locale, "tm_meaning")}</h2>
              {noJa ? <p className="rs-quiet" data-untranslated="ja">{tx(locale, "tm_untranslated")}</p> : null}
              <p className="rs-block-lead" lang={txLang}>{text.definition}</p>
              {text.expansion ? <p className="rs-block-note" lang={txLang}>{text.expansion}</p> : null}
              {text.origin ? <><h3>{tx(locale, "tm_origin")}</h3><p lang={txLang}>{text.origin}</p></> : null}
              {text.nuance ? <><h3>{tx(locale, "tm_nuance")}</h3><p lang={txLang}>{text.nuance}</p></> : null}
            </section>
          ) : null}
          <section className="rs-block" aria-labelledby="rs-b-linked">
            <h2 id="rs-b-linked">{tx(locale, "tm_linked")}</h2>
            {related && hasGraph(related)
              ? <RelGraph word={term.canonical} lang={term.lang} graph={related} href={(id) => `/dictionary/${encodeURIComponent(id)}${market ? `?m=${market}` : ""}`} locale={locale} />
              : <p className="rs-quiet">{tx(locale, "tm_linked_none")}</p>}
            <p className="rs-block-foot"><ActorTag who="ai" locale={locale}>{tx(locale, "tm_linked_note")}</ActorTag></p>
          </section>
          <section className="rs-block" aria-labelledby="rs-b-versions">
            <h2 id="rs-b-versions">{tx(locale, "tm_versions")}</h2>
            <ol className="rs-versions">
              {versions.map((v) => {
                const st = versionStatus(v, locale);
                const open = !v.valid_to;
                const shown = v.verification === "verified_human" || v.verification === "verified_auto";
                return (
                  <li key={v.meaning_id} data-open={open}>
                    <p className="rs-v-when rs-num">
                      {open ? <b>{tx(locale, "tm_v_now")}</b> : null}
                      <span>{open ? tx(locale, "tm_v_from", { date: fmtDay(v.valid_from, locale, true) }) : `${fmtDay(v.valid_from, locale, true)} – ${fmtDay(v.valid_to, locale, true)}`}</span>
                    </p>
                    <p className="rs-v-who">
                      <ActorTag who={HUMAN(v.created_by) ? "human" : "ai"} locale={locale}>{tx(locale, HUMAN(v.created_by) ? "tm_v_by_human" : "tm_v_by_ai")}</ActorTag>
                      <ActorTag who={st.who} locale={locale}>{st.text}</ActorTag>
                    </p>
                    {shown ? <p className="rs-v-text" lang="ko">{v.definition}</p> : null}
                  </li>
                );
              })}
            </ol>
            <p className="rs-block-foot rs-quiet">{tx(locale, "tm_versions_note")}</p>
          </section>
        </div>
        <aside className="rs-sheet-side">
          <section className="rs-block" aria-labelledby="rs-b-trend">
            <h2 id="rs-b-trend">{tx(locale, "tm_trend")}</h2>
            {hasTrend ? <TrendChart weekly={weekly} locale={locale} partial={partial} height={132} /> : <p className="rs-quiet">{tx(locale, "tm_no_trend")}</p>}
            <p className="rs-quiet">
              {tx(locale, market ? "tm_trend_scope_in" : "tm_trend_scope_all", { where: market ? marketName(locale, market) : "" })}
              {hasTrend ? <>{gap(locale)}{tx(locale, "tm_m4", { n: fmtN(m4) })}</> : null}
              {hasTrend && partial ? <>{gap(locale)}{tx(locale, "tm_partial")}</> : null}
            </p>
          </section>
          <section id="refs" className="rs-block" aria-labelledby="rs-b-refs">
            <h2 id="rs-b-refs">{tx(locale, "tm_refs")}</h2>
            {refs.length ? (
              <ul className="rs-refs">
                {refs.slice(0, 6).map((e) => {
                  const r = cleanSource(e, term.canonical, locale);
                  return (
                    <li key={r.id}>
                      <a href={r.url} target="_blank" rel="noopener noreferrer" className="rs-ref">
                        <span className="rs-ref-src">{r.source}<ArrowUpRight aria-hidden="true" size={13} /></span>
                        <span className="rs-ref-title">{r.title}</span>
                        <span className="rs-ref-date rs-num">{fmtDay(r.date, locale, true)}</span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            ) : <p className="rs-quiet">–</p>}
            {refs.length > 6 ? (
              <details className="rs-more">
                <summary>{tx(locale, "tm_refs_more", { n: refs.length - 6 })}</summary>
                <ul className="rs-refs">
                  {refs.slice(6, 30).map((e) => {
                    const r = cleanSource(e, term.canonical, locale);
                    return <li key={r.id}><a href={r.url} target="_blank" rel="noopener noreferrer" className="rs-ref"><span className="rs-ref-src">{r.source}</span><span className="rs-ref-title">{r.title}</span><span className="rs-ref-date rs-num">{fmtDay(r.date, locale, true)}</span></a></li>;
                  })}
                </ul>
              </details>
            ) : null}
            <p className="rs-block-foot rs-quiet">{tx(locale, "tm_refs_note")}</p>
          </section>
          {viewer?.reviewer ? <LiveRiskPanel termId={termId} locale={locale} /> : null}
          <section className="rs-block" aria-labelledby="rs-b-how">
            <h2 id="rs-b-how">{tx(locale, "tm_how")}</h2>
            <ol className="rs-how">
              {how.map((h, i) => {
                const Icon = h.who === "rule" ? ListChecks : h.who === "ai" ? Sparkles : Stamp;
                return <li key={i} data-who={h.who}><span className="rs-how-dot" aria-hidden="true"><Icon size={13} strokeWidth={2.2} /></span><span>{h.text}</span></li>;
              })}
            </ol>
          </section>
        </aside>
      </div>
    </main>
  );
}
