/* 밈 하나 — 옆 패널과 전체 화면이 같은 내용을 쓴다. 순서는 '써도 되나'(규칙의 판정)가 먼저, 그다음 뜻·유래·이어진 밈·추이·근거·기록.
   판정과 단계는 백엔드 규칙이 정한 값을 글로 옮길 뿐이다. 커뮤니티 글은 근거 목록에 싣지 않는다. */
import Link from "next/link";
import { ArrowLeft, Ban, Check, CircleDashed, ExternalLink, TriangleAlert } from "lucide-react";
import { isPartialWeek } from "@/components/trend-chart";
import { getTermRecord, getTermRelated, getTermSignals, getTermTopic } from "@/lib/data";
import { currentMeaning, textFor } from "@/lib/explain";
import type { LabLocale as Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { L, fmtDate, regionLabel, termLangLabel } from "@/lib/labels";
import { cleanSource } from "@/lib/sources";
import type { Meaning, Term, TermRelated } from "@/lib/types";
import { Spark, WeekBars } from "./charts";
import { isMarket, marketName, num, tr, type CopyKey } from "./copy";
import { Mark } from "./glyph";
import { Constellation } from "./constellation";

const BASE = "/lab/r-flow";
const SHOWN = new Set(["wiki", "web", "news", "short"]);
const AUTO = new Set(["research_agent", "tracking_agent"]);

type Tone = "avoid" | "caution" | "ok" | "muted";

/** 써도 되나 — 저장된 위험·단계를 그대로 읽는다(새로 판정하지 않는다) */
function verdictOf(term: Term): { tone: Tone; title: CopyKey; desc: CopyKey } {
  if (term.risk_level === "avoid") return { tone: "avoid", title: "tm_v_avoid", desc: "tm_v_avoid_d" };
  if (term.risk_level === "caution") return { tone: "caution", title: "tm_v_caution", desc: "tm_v_caution_d" };
  if (term.risk_level === "none") {
    return term.lifecycle === "declining" || term.lifecycle === "dormant"
      ? { tone: "ok", title: "tm_v_ok_fading", desc: "tm_v_ok_fading_d" }
      : { tone: "ok", title: "tm_v_ok", desc: "tm_v_ok_d" };
  }
  return term.risk_checked_at ? { tone: "muted", title: "tm_v_undecided", desc: "tm_v_undecided_d" } : { tone: "muted", title: "tm_v_unchecked", desc: "tm_v_unchecked_d" };
}

const where = (locale: Locale, r: string) => (isMarket(r) ? marketName(locale, r) : regionLabel(locale, r));
const sum = (xs: { count: number }[]) => xs.reduce((a, p) => a + p.count, 0);

function VerdictIcon({ tone }: { tone: Tone }) {
  const p = { size: 16, strokeWidth: 2, "aria-hidden": true } as const;
  return <span className="rf-verdict-icon">{tone === "avoid" ? <Ban {...p} /> : tone === "caution" ? <TriangleAlert {...p} /> : tone === "ok" ? <Check {...p} /> : <CircleDashed {...p} />}</span>;
}

function verLabel(locale: Locale, m: Meaning): string {
  return m.verification === "verified_human" ? tr(locale, "tm_ver_person")
    : m.verification === "verified_auto" ? tr(locale, "tm_ver_rule")
      : m.verification === "rejected" ? tr(locale, "tm_ver_rejected") : tr(locale, "tm_ver_wait");
}

export async function TermView({ termId, locale, mode, regions }: { termId: string; locale: Locale; mode: "page" | "panel"; regions: string[] }) {
  const [record, signals, graph] = await Promise.all([getTermRecord(termId), getTermSignals(termId, regions), getTermRelated(termId)]);
  if (!record) {
    return (
      <div className="rf-term" data-mode={mode}>
        <h1 className="rf-title">{tr(locale, "tm_not_found")}</h1>
        <p className="rf-lead">{tr(locale, "tm_not_found_d")}</p>
        <p style={{ marginTop: 16 }}><Link className="rf-btn" data-kind="line" href={`${BASE}/explore`}>{tr(locale, "nav_explore")}</Link></p>
      </div>
    );
  }
  const topic = await getTermTopic(termId, record.term.canonical);
  const labels = L(locale);
  const term = record.term;
  const lang = langTag(term.lang);
  const m = currentMeaning(record);
  const tx = textFor(record, locale);
  const txLang = locale === "en" && !record.en ? "ko" : undefined;
  const verified = term.status === "verified";
  const v = verdictOf(term);
  const decidedByPerson = !!term.risk_decided_by && !!term.risk_decided_at;

  const weekly = signals?.weekly?.length ? signals.weekly : record.weekly.slice(-12);
  const m4 = signals?.mentions_4w ?? sum(weekly.slice(-4));
  const last = signals?.last_used ?? signals?.last_seen ?? term.last_seen ?? null;
  const markets = (signals?.regions?.length ? signals.regions : m?.regions ?? []).filter((r) => r !== "");
  const partial = isPartialWeek(weekly.at(-1));
  const hasTrend = weekly.some((p) => p.count > 0);

  const sources = record.evidences
    .filter((e) => SHOWN.has(e.kind))
    .sort((a, b) => b.observed_at.localeCompare(a.observed_at))
    .map((e) => cleanSource(e, term.canonical, locale));
  const first = sources.slice(0, 6);
  const rest = sources.slice(6);

  const versions = [...record.meanings].sort((a, b) => b.version - a.version);
  const origin = tx?.origin && tx.origin !== "unknown" ? tx.origin : null;
  const canMake = verified && term.risk_level !== "avoid";
  const linkProps = mode === "panel" ? { replace: true, scroll: false } : { scroll: false };

  const meaningWho = m?.verification === "verified_human" ? "person" : m?.verification === "verified_auto" ? "rule" : null;
  const draftedByAI = !!m?.created_by && AUTO.has(m.created_by);
  const hasGraph = !!graph && (graph.related.length > 0 || graph.same_source.length > 0 || graph.candidates.length > 0 || !!graph.source?.name);

  return (
    <article className="rf-term" data-mode={mode} aria-labelledby="rf-term-h">
      {mode === "page" && (
        <p className="rf-crumb">
          <Link className="rf-link" href={`${BASE}/explore${regions[0] ? `?m=${regions[0]}` : ""}`}><ArrowLeft size={13} strokeWidth={2} aria-hidden="true" style={{ verticalAlign: "-2px", marginRight: 4 }} />{tr(locale, "nav_explore")}</Link>
        </p>
      )}
      <header className="rf-term-head">
      <h1 id="rf-term-h" className="rf-term-word" lang={lang}>{term.canonical}</h1>
      <div className="rf-term-sub">
        {term.lang && <span>{tr(locale, "tm_lang", { lang: termLangLabel(locale, term.lang) })}</span>}
        {!!term.aliases?.length && <span>{tr(locale, "tm_aliases")} <span lang={lang}>{term.aliases.slice(0, 4).join(", ")}</span></span>}
        {graph?.card && <span className="rf-chip">{locale === "ko" ? graph.card.kind_ko : graph.card.kind}</span>}
      </div>
      {tx?.plain && <p className="rf-headline" lang={txLang}>{tx.plain}</p>}
      {!verified && <p className="rf-notice">{tr(locale, "tm_review_notice")}</p>}
      </header>

      <div className="rf-term-side">
      <section className="rf-verdict" data-tone={v.tone} aria-labelledby="rf-verdict-h">
        <VerdictIcon tone={v.tone} />
        <div>
          <p className="rf-verdict-k" id="rf-verdict-h">{tr(locale, "tm_verdict")}</p>
          <p className="rf-verdict-t">{tr(locale, v.title)}</p>
          <p className="rf-verdict-d">{tr(locale, v.desc)}</p>
          <div className="rf-verdict-by">
            {decidedByPerson
              ? <span className="rf-who" data-actor="person"><Mark actor="person" />{tr(locale, "tm_by_person", { date: fmtDate(term.risk_decided_at) })}</span>
              : term.risk_checked_at ? <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "tm_by_rule", { date: fmtDate(term.risk_checked_at) })}</span> : null}
          </div>
          {!!term.risk_reasons?.length && (term.risk_level === "caution" || term.risk_level === "avoid" || term.risk_level == null) && (
            <ul className="rf-reasons" aria-label={tr(locale, "tm_reasons")}>
              {term.risk_reasons.slice(0, 3).map((r) => <li key={r} lang="ko">{r}</li>)}
            </ul>
          )}
        </div>
      </section>

      <dl className="rf-facts">
        <div><dt>{tr(locale, "tm_stage")}</dt><dd>{labels.lifecycle[term.lifecycle ?? "unknown"]}</dd></div>
        <div><dt>{tr(locale, "tm_spread")}</dt><dd>{term.diffusion ? tr(locale, `dif_${term.diffusion}`) : "–"}</dd></div>
        <div>
          <dt>{tr(locale, "tm_m4")}</dt>
          <dd><span className="rf-num">{num(m4)}</span>{hasTrend && <Spark values={weekly.map((p) => p.count)} w={64} h={18} label={tr(locale, "ex_spark", { a: weekly[0]?.count ?? 0, b: weekly.at(-1)?.count ?? 0 })} />}</dd>
        </div>
        <div><dt>{tr(locale, "tm_last")}</dt><dd className="rf-num">{last ? fmtDate(last) : "–"}</dd></div>
        <div><dt>{tr(locale, "tm_where")}</dt><dd style={{ fontWeight: 550, fontSize: 14 }}>{markets.length ? markets.slice(0, 4).map((r) => where(locale, r)).join(", ") : "–"}</dd></div>
      </dl>
      {canMake && <div className="rf-term-actions rf-term-cta"><Link className="rf-btn" href={`${BASE}?term=${encodeURIComponent(term.term_id)}`}>{tr(locale, "tm_make")}</Link></div>}
      </div>

      <div className="rf-term-main">

      {tx && (
        <section className="rf-sec" aria-labelledby="rf-s-meaning">
          <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-meaning">{tr(locale, "tm_meaning")}</h2></div>
          {txLang && <p className="rf-note" style={{ margin: "0 0 8px" }}>{tr(locale, "tm_untranslated")}</p>}
          <p className="rf-prose" lang={txLang}>{tx.definition}</p>
          {tx.expansion && <><span className="rf-prose-k">{tr(locale, "tm_expansion")}</span><p className="rf-prose" lang={txLang ?? lang}>{tx.expansion}</p></>}
          {origin && <><span className="rf-prose-k">{tr(locale, "tm_origin")}</span><p className="rf-prose" lang={txLang}>{origin}</p></>}
          {tx.nuance && (
            <>
              <span className="rf-prose-k">{tr(locale, "tm_nuance")}</span>
              <p className="rf-prose" lang={txLang}>{tx.nuance}</p>
              {m?.verification !== "verified_human" && <p className="rf-note" style={{ margin: "-4px 0 8px" }}>{tr(locale, "tm_nuance_unchecked")}</p>}
            </>
          )}
          <ul className="rf-whos" aria-label={tr(locale, "tm_who")}>
            {draftedByAI && <li><Mark actor="ai" />{tr(locale, "tm_who_meaning_draft")}</li>}
            <li>{meaningWho ? <Mark actor={meaningWho} /> : <Mark actor="person" filled={false} />}{tr(locale, meaningWho === "person" ? "tm_who_meaning_person" : meaningWho === "rule" ? "tm_who_meaning_rule" : "tm_who_meaning_wait")}</li>
            <li><Mark actor="rule" />{tr(locale, "tm_who_risk")}</li>
          </ul>
        </section>
      )}

      <section className="rf-sec" aria-labelledby="rf-s-graph">
        <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-graph">{tr(locale, "tm_graph")}</h2><span className="rf-note">{tr(locale, "tm_graph_note")}</span></div>
        {graph?.card && (
          <dl className="rf-dl" style={{ marginBottom: 12 }}>
            {graph.card.domains_ko.length > 0 && <><dt>{tr(locale, "tm_graph_domains")}</dt><dd>{(locale === "ko" ? graph.card.domains_ko : graph.card.domains.map((d) => d.replace(/_/g, " "))).join(", ")}</dd></>}
            {graph.source?.name && <><dt>{tr(locale, "tm_graph_source")}</dt><dd>{graph.source.name} <span className="rf-muted">({sourceType(locale, graph.source.type)})</span></dd></>}
          </dl>
        )}
        {hasGraph ? <Graph graph={graph!} self={term} locale={locale} linkProps={linkProps} /> : <p className="rf-note">{tr(locale, "tm_graph_empty")}</p>}
      </section>

      <section className="rf-sec" aria-labelledby="rf-s-trend">
        <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-trend">{tr(locale, "tm_trend")}</h2>{partial && hasTrend && <span className="rf-note">{tr(locale, "tm_trend_partial")}</span>}</div>
        {hasTrend ? <WeekBars points={weekly} partial={partial} label={`${tr(locale, "tm_trend_sr")}: ${weekly.map((p) => `${p.week_start.slice(5)} ${p.count}`).join(", ")}`} /> : <p className="rf-note">{tr(locale, "tm_trend_none")}</p>}
      </section>

      {sources.length > 0 && (
        <section className="rf-sec" aria-labelledby="rf-s-src">
          <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-src">{tr(locale, "tm_sources", { n: sources.length })}</h2><span className="rf-note">{tr(locale, "tm_sources_note")}</span></div>
          <ul className="rf-sources">{first.map((s) => <SourceRow key={s.id} s={s} locale={locale} />)}</ul>
          {rest.length > 0 && (
            <details className="rf-more">
              <summary>{tr(locale, "tm_sources_more", { n: rest.length })}</summary>
              <ul className="rf-sources">{rest.map((s) => <SourceRow key={s.id} s={s} locale={locale} />)}</ul>
            </details>
          )}
        </section>
      )}

      {topic && topic.variants.length > 1 && (
        <section className="rf-sec" aria-labelledby="rf-s-var">
          <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-var">{tr(locale, "tm_variants")}</h2></div>
          <table className="rf-variants">
            <thead><tr><th scope="col">{tr(locale, "tm_where")}</th><th scope="col">{tr(locale, "ex_col_meme")}</th><th scope="col">{tr(locale, "ex_col_gloss")}</th></tr></thead>
            <tbody>
              {topic.variants.slice(0, 8).map((x) => (
                <tr key={`${x.region}-${x.local_name}`}>
                  <td>{x.region ? where(locale, x.region) : "–"}</td>
                  <td lang={scriptLang(x.local_name, x.region)}>{x.local_name}</td>
                  <td>{x.what_changed[locale] || x.what_changed.ko || "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {versions.length > 0 && (
        <section className="rf-sec" aria-labelledby="rf-s-ver">
          <div className="rf-sec-h"><h2 className="rf-h2" id="rf-s-ver">{tr(locale, "tm_versions")}</h2></div>
          <ol className="rf-versions">
            {versions.map((x) => {
              const open = !x.valid_to;
              return (
                <li key={x.meaning_id} data-current={open}>
                  <span className="rf-ver-dot" aria-hidden="true" />
                  <div className="rf-ver-h">
                    {open ? <span style={{ color: "var(--rf-ink)", fontWeight: 600, fontSize: 13 }}>{tr(locale, "tm_ver_current")}</span> : <span style={{ fontSize: 13 }}>{tr(locale, "tm_ver_old")}</span>}
                    <span>{tr(locale, "tm_ver_from", { from: fmtDate(x.valid_from) })}{x.valid_to ? `, ${tr(locale, "tm_ver_closed", { to: fmtDate(x.valid_to) })}` : ""}</span>
                    <span>{verLabel(locale, x)}</span>
                  </div>
                  <p className="rf-ver-d" lang="ko">{x.definition}</p>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      </div>
    </article>
  );
}

function sourceType(locale: Locale, t: string): string {
  const k = `src_${t}` as CopyKey;
  return ["work", "person", "platform", "event", "ad", "community"].includes(t) ? tr(locale, k) : tr(locale, "src_other");
}

function SourceRow({ s, locale }: { s: ReturnType<typeof cleanSource>; locale: Locale }) {
  return (
    <li>
      <a className="rf-src-t rf-link" href={s.url} target="_blank" rel="noreferrer noopener" lang={scriptLang(s.title)}>
        {s.title}<ExternalLink size={12} strokeWidth={2} aria-hidden="true" style={{ marginLeft: 4, verticalAlign: "-1px", color: "var(--rf-ink-3)" }} />
        <span className="rf-sr"> ({tr(locale, "tm_new_tab")})</span>
      </a>
      <span className="rf-src-m">{s.source}, {fmtDate(s.date)}</span>
      {s.excerpt && <span className="rf-src-x" lang={scriptLang(s.excerpt)}>{s.excerpt}</span>}
    </li>
  );
}

function Graph({ graph, self, locale, linkProps }: { graph: TermRelated; self: Term; locale: Locale; linkProps: { replace?: boolean; scroll: boolean } }) {
  const rel = (r: string) => {
    const k = `rel_${r.toLowerCase()}` as CopyKey;
    return ["rel_derived_from", "rel_derived_into", "rel_variant", "rel_opposite", "rel_similar", "rel_parody_of", "rel_linked"].includes(k) ? tr(locale, k) : r.toLowerCase();
  };
  return (
    <>
      <Constellation
        self={{ name: self.canonical, lang: self.lang ?? "" }}
        related={graph.related.map((r) => ({ id: r.term_id, name: r.canonical, lang: r.lang, rel: rel(r.rel) }))}
        candidates={graph.candidates.map((c) => ({ name: c.name, rel: rel(c.rel) }))}
        source={graph.source?.name ? { name: graph.source.name, type: sourceType(locale, graph.source.type) } : null}
        same={graph.same_source.map((r) => ({ id: r.term_id, name: r.canonical, lang: r.lang }))}
        base={BASE}
      />
      <ul className="rf-rel-list">
        {graph.related.map((r) => (
          <li key={r.term_id}><Link {...linkProps} className="rf-link" href={`${BASE}/term/${encodeURIComponent(r.term_id)}`} lang={langTag(r.lang)}>{r.canonical}</Link><span>{rel(r.rel)}</span></li>
        ))}
        {graph.candidates.map((c) => (
          <li key={c.name}><span style={{ color: "var(--rf-ink)", marginLeft: 0, fontSize: 13, fontWeight: 600 }} lang={scriptLang(c.name)}>{c.name}</span><span>{rel(c.rel)}, {tr(locale, "tm_graph_cand")}</span></li>
        ))}
        {graph.source?.name && graph.same_source.map((r) => (
          <li key={`s-${r.term_id}`}><Link {...linkProps} className="rf-link" href={`${BASE}/term/${encodeURIComponent(r.term_id)}`} lang={langTag(r.lang)}>{r.canonical}</Link><span>{tr(locale, "tm_graph_same", { source: graph.source?.name ?? "" })}</span></li>
        ))}
      </ul>
    </>
  );
}
