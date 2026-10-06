import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EntryHistory, historyRows } from "@/components/entry-history";
import { RiskText, Spark, StageMark, riskKey } from "@/components/ledger-bits";
import { Who } from "@/components/who";
import { GenerationCurves } from "@/components/generation-curves";
import { SourceTable } from "@/components/source-table";
import { StatusBadge } from "@/components/status-badge";
import { TermMediaBlock } from "@/components/term-media";
import { RiskSentences } from "@/components/risk-sentences";
import { TermProvenance } from "@/components/term-provenance";
import { TrendChart, isPartialWeek } from "@/components/trend-chart";
import { VariantTable } from "@/components/variant-table";
import { getGenerationCurves, getTermRecord, getTermRelated, getTermSignals, getTermTopic, getUpdatedAt } from "@/lib/data";
import { currentMeaning, headlineFor, textFor } from "@/lib/explain";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { langTag, scriptLang } from "@/lib/lang";
import { L, fmtDate, fmtDateTime, fmtInt, joinRegions, listJoin, regionLabel, sourceName, nuanceChecked } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { cleanSource, kindCounts } from "@/lib/sources";
import type { KeywordCard, SearchHit, TermRecord } from "@/lib/types";

/* 사전 항목 — "이 밈을, 이 나라에서, 지금 써도 되나" 를 머리와 요약에서 답하고, 본문은 그 근거(쓰임·유래·나라별 차이·언급·출처·기록).
   요약은 DOM 에서도 머리 바로 다음이라 휴대폰·화면 읽기 순서가 보이는 순서와 같다. 1280px 이상에서만 오른쪽 칸으로 옮긴다.
   절에는 번호를 붙이지 않는다(docs/트렌드/디자인-개편.md 원칙 5). */

type Params = { params: Promise<{ termId: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };

const KNOWN = [...TARGET_REGIONS, "GLOBAL"];

/** 대시보드에서 넘어온 ?regions=KR,JP — 같은 지역의 수를 보이려고. 모르는 값은 버린다. */
function askedRegions(sp: Record<string, string | string[] | undefined>): string[] {
  const raw = [sp.regions].flat().filter(Boolean).join(",");
  const asked = raw.split(",").map((s) => s.trim().toUpperCase());
  return KNOWN.filter((r) => asked.includes(r));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const record = await getTermRecord(termId).catch(() => null);   // 실패는 화면(error.tsx)이 알린다
  const tail = `${t(locale, "dict_title")} · ${t(locale, "site")}`;
  return { title: record ? `${record.term.canonical} · ${tail}` : tail };
}

/** 원장의 한 줄 — 왼쪽 이름표, 오른쪽 내용 */
function Row({ id, label, children }: { id: string; label: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="n-row" aria-labelledby={id}>
      <h2 id={id} className="n-row-label scroll-mt-[72px]">{label}</h2>
      <div className="min-w-0 space-y-3">{children}</div>
    </section>
  );
}

const sum = (xs: { count: number }[]) => xs.reduce((a, p) => a + p.count, 0);

function toneLine(locale: Locale, tone: KeywordCard["tone"]): string | null {
  const total = tone.positive + tone.neutral + tone.negative;
  if (total < 5) return null;
  const parts = (["positive", "neutral", "negative"] as const).filter((k) => tone[k] > 0);
  if (locale === "ko") return `문장 ${total}개 중 ${parts.map((k) => `${t(locale, `tone_${k}`)} ${tone[k]}개`).join(", ")}`;
  return `Of ${total} sentences, ${listJoin(locale, parts.map((k) => `${tone[k]} ${t(locale, `tone_${k}`)}`))}`;
}

function SearchRow({ h, locale }: { h: SearchHit; locale: Locale }) {
  const where = regionLabel(locale, h.region);
  const rank = h.rank ? (locale === "ko" ? `${where} ${h.rank}위` : `#${h.rank} in ${where}`) : where;
  return (
    <li className="flex flex-wrap gap-x-3">
      <span>{rank}</span>
      {h.query && <span lang={scriptLang(h.query, h.region)}>“{h.query}”</span>}
      {h.traffic && <span className="text-steel">{locale === "ko" ? `검색 ${h.traffic}` : `${h.traffic} searches`}</span>}
      <span className="tabular-nums text-steel">{fmtDate(h.date)}</span>
    </li>
  );
}

export default async function TermPage({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const regions = askedRegions(sp);
  const [record, curves, signals, updatedAt, graph] = await Promise.all([
    getTermRecord(termId), getGenerationCurves(termId), getTermSignals(termId, regions), getUpdatedAt(), getTermRelated(termId),
  ]);
  if (!record) notFound();
  const topic = await getTermTopic(termId, record.term.canonical);
  // 관련 표현: 같은 주제에 엮인 사전 항목만(같은 분류 전체 목록 2MB 를 받지 않는다). 못 받은 것은 뺀다
  const relatedIds = [...new Set(topic ? topic.variants.flatMap((v) => [v.term_id, ...v.linked.map((x) => x.term_id)]) : [])]
    .filter((id): id is string => !!id && id !== termId).slice(0, 6);
  const related = (await Promise.all(relatedIds.map((id) => getTermRecord(id).catch(() => null))))
    .filter((r): r is TermRecord => !!r && r.term.status === "verified");

  const labels = L(locale);
  const term = record.term;
  const m = currentMeaning(record);
  const tx = textFor(record, locale);
  // 번역이 없으면 원문(한국어)이 나온다 — 그때는 한국어 음성으로 읽게
  const txLang = locale === "en" && !record.en ? "ko" : undefined;
  const verified = term.status === "verified";
  const canMake = verified && term.risk_level !== "avoid" && sp.from !== "recommend";

  // 언급 수는 대시보드 행과 같은 카드(signals)에서. 카드가 없을 때(확인 전·서버 없음)만 사전 항목의 주간 수
  const weekly = signals?.weekly ?? record.weekly.slice(-12);
  const hasTrend = weekly.some((p) => p.count > 0);   // 0 만 이어진 주간 자료는 없는 것과 같다
  const partial = isPartialWeek(weekly.at(-1));
  const last4 = signals?.mentions_4w ?? sum(weekly.slice(-4));
  const prev4 = sum(weekly.slice(-8, -4));
  const scope = regions.length ? t(locale, "term_scope_in").replace("{r}", joinRegions(locale, regions)) : t(locale, "term_scope_all");
  const lastUsed = signals ? signals.last_used ?? signals.last_seen ?? null : term.last_seen ?? null;

  const search = signals?.search ?? [];
  // 커뮤니티 사이트 이름('주로 보인 곳')은 싣지 않는다 — 커뮤니티 글은 뉘앙스 수처럼 지표로만 센다(ADR 0003)
  const tone = signals ? toneLine(locale, signals.tone) : null;
  const signalRows = search.length > 0 || !!tone;
  const usage = [...record.usage].sort((a, b) => a.first_seen.localeCompare(b.first_seen));
  const showTrend = hasTrend || signalRows || !!signals || curves.length > 0 || usage.length > 0;

  const origin = tx?.origin && tx.origin !== "unknown" ? tx.origin : null;
  const media = record.media ?? [];
  const byDate = [...record.evidences].sort((a, b) => a.observed_at.localeCompare(b.observed_at));
  const originRefs = byDate.filter((e) => e.kind === "news" || e.kind === "short" || e.kind === "web").slice(0, 2);
  const sources = [...byDate].reverse().map((e) => cleanSource(e, term.canonical, locale));
  const summaryText = topic?.summary[locale];
  const showSummary = !!summaryText && !!tx && !summaryText.includes(tx.definition.slice(0, 20));   // 뜻과 같은 말이면 되풀이하지 않는다

  const risk = riskOf(term);
  const riskResult = risk ? t(locale, `risk_${risk}`) : term.risk_level === "none" ? t(locale, "risk_none_short") : null;
  const history = historyRows(record, locale, riskResult);

  const sections = [
    { id: "usage", title: t(locale, "term_sec_usage"), show: !!tx?.nuance },
    { id: "origin", title: t(locale, "term_origin"), show: !!origin },
    { id: "media", title: t(locale, "term_media"), show: !origin && media.length > 0 },
    { id: "variants", title: t(locale, "term_sec_variants"), show: !!topic && topic.variants.length > 1 },
    { id: "linked", title: t(locale, "tm_linked"), show: !!graph && (!!graph.card || graph.related.length > 0 || graph.same_source.length > 0) },
    { id: "trend", title: t(locale, "term_sec_trend"), show: showTrend },
    { id: "made", title: t(locale, "prov_title"), show: !!record.provenance },
    { id: "sources", title: t(locale, "term_sources_title").replace("{n}", fmtInt(sources.length)), show: sources.length > 0 },
    { id: "history", title: t(locale, "term_sec_history"), show: history.length > 0 },
    { id: "related", title: t(locale, "term_related"), show: related.length > 0 },
  ].filter((s) => s.show);
  const title = (id: string) => sections.find((s) => s.id === id)?.title ?? "";

  const makeHref = `/recommend?term=${encodeURIComponent(term.term_id)}`;

  const verification = m?.verification;
  const who4 = !verified ? t(locale, "tm_who4_wait") : verification === "verified_human" && m
    ? t(locale, "tm_who4_human").replace("{date}", fmtDate(m.valid_from)) : t(locale, "tm_who4_auto");

  /* 원장(Plan 20, 시안 n-redesign): 원문을 크게 → 지금 상태 다섯 칸 → 왼쪽 이름표 줄(뜻·쓰는 법·유래·나라마다·쓰임 추이·만든 과정·출처·뜻 이력)
     → 오른쪽 '누가 정했나'. 각 줄의 내용 부품(출처 표·이력·나라별 비교·추이 그래프)은 그대로 쓴다. */
  return (
    <main id="main" className="n-main">
      <article className="n-wrap">
        <div className="n-term-head">
          <p className="n-crumb">
            <Link href={regions.length ? `/trends?regions=${regions[0]}` : "/trends"}>{t(locale, "nav_browse")}</Link><span aria-hidden="true">/</span>
            <Link href="/dictionary">{t(locale, "dict_title")}</Link><span aria-hidden="true">/</span>
            <span lang={langTag(term.lang)}>{term.canonical}</span>
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: "16px 32px" }}>
            <div className="min-w-0">
              <h1 className="n-term-word" lang={langTag(term.lang)}>{term.canonical}</h1>
              {tx ? <p className="n-term-gloss" lang={txLang}>{headlineFor(tx, locale)}</p>
                : <p className="n-term-gloss">{t(locale, "term_no_meaning")} {t(locale, "term_no_meaning_next")}</p>}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
              {!verified && <StatusBadge tone="muted">{t(locale, "term_badge_review")}</StatusBadge>}
              {updatedAt && <span className="n-meta">{t(locale, "dash_updated")} <span className="n-num">{fmtDateTime(updatedAt, locale)}</span></span>}
              {/* 식어 가는 말이면 검정 주 버튼으로 권하지 않는다(검토 10-06) */}
              {canMake && <Link className="n-btn" data-size="s" data-kind={term.lifecycle === "declining" || term.lifecycle === "dormant" ? "line" : undefined} href={makeHref}>{t(locale, "term_make")}</Link>}
            </div>
          </div>
          {!verified && <p className="n-thin" style={{ marginTop: 16 }}>{t(locale, "term_draft_notice")}</p>}
          {tx && txLang && <p className="n-thin" style={{ marginTop: 16 }}>{t(locale, "term_untranslated_notice")}</p>}

          <dl className="n-vitals" aria-label={t(locale, "tm_vitals")}>
            <div><dt>{t(locale, "dr_why_stage")}</dt><dd><StageMark stage={term.lifecycle ?? "unknown"} locale={locale} /></dd></div>
            <div><dt>{t(locale, "dr_why_spread")}</dt><dd>{term.diffusion ? t(locale, `diffusion_${term.diffusion}`) : "–"}</dd></div>
            <div><dt>{t(locale, "dr_why_risk")}</dt><dd><RiskText risk={riskKey(term)} locale={locale} /></dd></div>
            <div><dt>{t(locale, "tb_mentions")}</dt><dd>{hasTrend || signals ? <><span className="n-big">{fmtInt(last4)}</span>
              <Spark values={weekly.map((p) => p.count)} w={120} h={26} label={t(locale, "tb_spark").replace("{a}", String(weekly[0]?.count ?? 0)).replace("{b}", String(weekly.at(-1)?.count ?? 0))} /></> : "–"}</dd></div>
            <div><dt>{t(locale, "tb_last")}</dt><dd className="n-num">{lastUsed ? fmtDate(lastUsed) : "–"}</dd></div>
          </dl>
        </div>

        <div className="n-ledger">
          <div className="min-w-0">
            {tx && (
              <Row id="meaning" label={t(locale, "tm_meaning")}>
                <p className="n-prose" lang={txLang}>{tx.definition}</p>
                {tx.plain && <p className="n-meta" lang={txLang}>{tx.plain}</p>}
                <ul className="n-facts">
                  {!!term.aliases?.length && <li><span>{t(locale, "tm_aliases")}</span><span lang={langTag(term.lang)}>{term.aliases.join(", ")}</span></li>}
                  {!!m?.regions.length && <li><span>{t(locale, "tm_regions")}</span><span>{joinRegions(locale, m.regions)}</span></li>}
                  {!!m?.generations.length && <li><span>{t(locale, "tm_gens")}</span><span>{m.generations.map((g) => labels.generation[g]).join(", ")}</span></li>}
                </ul>
              </Row>
            )}
            {tx?.nuance && (
              <Row id="usage" label={title("usage")}>
                <p className="n-prose" lang={txLang}>{tx.nuance}</p>
                {!nuanceChecked(m) && (
                  <p className="flex flex-wrap items-center gap-2 text-[13px] text-steel">
                    <StatusBadge tone="muted">{t(locale, "nuance_unchecked")}</StatusBadge>{t(locale, "nuance_unchecked_note")}
                  </p>
                )}
              </Row>
            )}
            {origin && (
              <Row id="origin" label={title("origin")}>
                <p className="n-prose" lang={txLang}>{origin}</p>
                {originRefs.length > 0 && (
                  <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
                    <span className="text-steel">{t(locale, "term_evidence_line")}</span>
                    {originRefs.map((e) => (
                      <a key={e.evidence_id} href={e.url} target="_blank" rel="noreferrer noopener" className="n-link inline-flex min-h-6 items-center">
                        {sourceName(locale, e.source_domain)} <span className="ml-1 tabular-nums">{fmtDate(e.observed_at)}</span>
                        <span className="sr-only"> ({t(locale, "term_new_tab")})</span>
                      </a>
                    ))}
                  </p>
                )}
                {media.length > 0 && <TermMediaBlock media={media} name={term.canonical} locale={locale} />}
              </Row>
            )}
            {!origin && media.length > 0 && (
              <Row id="media" label={title("media")}><TermMediaBlock media={media} name={term.canonical} locale={locale} /></Row>
            )}
            {topic && topic.variants.length > 1 && (
              <Row id="variants" label={title("variants")}>
                {showSummary && <p className="n-prose">{summaryText}</p>}
                <VariantTable variants={topic.variants} locale={locale} />
                <Link href={`/map?topic=${encodeURIComponent(topic.id)}`} className="n-link text-[14px]">{t(locale, "term_see_on_map")}</Link>
              </Row>
            )}
            {graph && (graph.card || graph.related.length > 0 || graph.same_source.length > 0) && (
              <Row id="linked" label={<>{title("linked")}<small>{t(locale, "tm_linked_note")}</small></>}>
                {graph.card && (
                  <ul className="n-facts">
                    <li><span>{t(locale, "tm_kind")}</span><span>{graph.card.kind_ko}</span></li>
                    {graph.card.domains_ko.length > 0 && <li><span>{t(locale, "tm_domains")}</span><span>{graph.card.domains_ko.join(", ")}</span></li>}
                    {graph.card.source_name && <li><span>{t(locale, "tm_source")}</span><span>{graph.card.source_name}</span></li>}
                  </ul>
                )}
                {graph.related.length > 0 && (
                  <p className="n-prose">
                    {graph.related.map((r, i) => (
                      <span key={r.term_id}>{i > 0 && ", "}<Link className="n-link" href={`/dictionary/${encodeURIComponent(r.term_id)}`} lang={langTag(r.lang)}>{r.canonical}</Link>
                        <span className="n-meta"> ({t(locale, `tm_rel_${r.rel.toLowerCase()}` as StringKey)})</span></span>
                    ))}
                  </p>
                )}
                {graph.same_source.length > 0 && graph.source && (
                  <p className="text-[14px] text-charcoal">
                    {t(locale, "tm_same_source").replace("{source}", graph.source.name)}{" "}
                    {graph.same_source.map((r, i) => (
                      <span key={r.term_id}>{i > 0 && ", "}<Link className="n-link" href={`/dictionary/${encodeURIComponent(r.term_id)}`} lang={langTag(r.lang)}>{r.canonical}</Link></span>
                    ))}
                  </p>
                )}
                <p className="flex items-center gap-2 text-[12px] text-steel"><Who kind="model" locale={locale} />{t(locale, "tm_linked_who")}</p>
              </Row>
            )}
            {showTrend && (
              <Row id="trend" label={<>{title("trend")}<small>{scope}</small></>}>
                {hasTrend && (
                  <div className="space-y-3">
                    <dl className="flex flex-wrap items-end gap-x-10 gap-y-2">
                      <div><dt className="text-[13px] text-steel">{t(locale, "term_last4")}</dt><dd className="text-[24px] leading-[1.3] font-semibold tabular-nums text-ink">{fmtInt(last4)}</dd></div>
                      <div><dt className="text-[13px] text-steel">{t(locale, "term_prev4")}</dt><dd className="text-[24px] leading-[1.3] font-semibold tabular-nums text-ink">{fmtInt(prev4)}</dd></div>
                    </dl>
                    <TrendChart points={weekly} locale={locale} partial={partial} />
                  </div>
                )}
                {signalRows ? (
                  <dl className="divide-y divide-hairline border-y border-hairline text-[14px]">
                    {search.length > 0 && (
                      <div className="grid gap-1 py-2.5 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-3">
                        <dt className="text-[13px] text-steel">{t(locale, "term_row_search")}</dt>
                        <dd className="text-ink"><ul className="space-y-1">{search.map((h, i) => <SearchRow key={`${h.region}-${h.date}-${i}`} h={h} locale={locale} />)}</ul></dd>
                      </div>
                    )}
                    {tone && (
                      <div className="grid gap-1 py-2.5 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-3">
                        <dt className="text-[13px] text-steel">{t(locale, "term_row_tone")}</dt>
                        <dd className="text-ink">{tone}</dd>
                      </div>
                    )}
                  </dl>
                ) : signals && <p className="text-[14px] text-charcoal">{t(locale, "term_signals_none")}</p>}
                {curves.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-[15px] font-semibold text-ink">{t(locale, "term_gen_title")}</h3>
                    <GenerationCurves curves={curves} locale={locale} />
                  </div>
                )}
                {usage.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-[15px] font-semibold text-ink">{t(locale, "term_first_used")}</h3>
                    <table className="w-full max-w-[560px] border-collapse text-left text-[14px]">
                      <thead>
                        <tr className="border-b border-hairline text-[13px] text-steel">
                          <th scope="col" className="py-2 pr-4 font-medium">{t(locale, "term_col_country")}</th>
                          <th scope="col" className="py-2 pr-4 font-medium">{t(locale, "term_col_age")}</th>
                          <th scope="col" className="py-2 font-medium">{t(locale, "term_col_first_date")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usage.map((u) => (
                          <tr key={u.segment.segment_id} className="border-b border-hairline">
                            <td className="py-2 pr-4 text-ink">{regionLabel(locale, u.segment.region)}</td>
                            <td className="py-2 pr-4 text-ink">{labels.generation[u.segment.generation]}</td>
                            <td className="py-2 tabular-nums text-charcoal">{fmtDate(u.first_seen)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Row>
            )}
            {record.provenance && (
              <Row id="made" label={title("made")}>
                <TermProvenance p={record.provenance} locale={locale} />
                {record.risk_labels && <RiskSentences b={record.risk_labels} locale={locale} />}
                <Link href="/about" className="n-link text-[14px]">{t(locale, "prov_more")}</Link>
              </Row>
            )}
            {sources.length > 0 && (
              <Row id="sources" label={<>{title("sources")}<small>{kindCounts(record.evidences, locale)}</small></>}>
                <SourceTable rows={sources} locale={locale} />
              </Row>
            )}
            {history.length > 0 && (
              <Row id="history" label={title("history")}><EntryHistory rows={history} locale={locale} /></Row>
            )}
            {related.length > 0 && (
              <Row id="related" label={title("related")}>
                <ul className="divide-y divide-hairline border-y border-hairline">
                  {related.map((r) => (
                    <li key={r.term.term_id} className="flex min-h-11 flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2">
                      <Link href={`/dictionary/${encodeURIComponent(r.term.term_id)}`} lang={langTag(r.term.lang)} className="text-[15px] font-medium text-ink hover:underline">{r.term.canonical}</Link>
                      <StageMark stage={r.term.lifecycle ?? "unknown"} locale={locale} />
                    </li>
                  ))}
                </ul>
              </Row>
            )}
          </div>

          <aside className="n-rail" aria-labelledby="tm-who">
            <h2 id="tm-who">{t(locale, "tm_who_title")}</h2>
            <ol className="n-steps">
              <li><div><Who kind="rule" locale={locale} /><span>{t(locale, "tm_who1")}</span></div></li>
              <li><div><Who kind="rule" locale={locale} /><span>{t(locale, "tm_who2")}</span></div></li>
              <li><div><Who kind="model" locale={locale} /><span>{t(locale, "tm_who3")}</span></div></li>
              <li><div><Who kind={verification === "verified_human" ? "human" : "wait"} locale={locale} /><span>{who4}</span></div></li>
            </ol>
            <p className="n-meta" style={{ marginTop: 16 }}>{t(locale, "tm_community")}</p>
            {sections.length > 1 && (
              <nav aria-label={t(locale, "term_toc")} style={{ marginTop: 24 }}>
                <h2>{t(locale, "term_toc")}</h2>
                <ul className="space-y-1.5 text-[14px]">
                  {sections.map((s) => <li key={s.id}><a href={`#${s.id}`} className="text-charcoal hover:text-ink hover:underline">{s.title}</a></li>)}
                </ul>
              </nav>
            )}
          </aside>
        </div>
      </article>
    </main>
  );
}
