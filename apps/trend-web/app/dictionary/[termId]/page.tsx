import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EntryHistory, historyRows } from "@/components/entry-history";
import { GenerationCurves } from "@/components/generation-curves";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { SourceTable } from "@/components/source-table";
import { StatusBadge } from "@/components/status-badge";
import { TermMediaBlock } from "@/components/term-media";
import { StageCell } from "@/components/term-status";
import { RiskSentences } from "@/components/risk-sentences";
import { TermProvenance } from "@/components/term-provenance";
import { TermSummary } from "@/components/term-summary";
import { TrendChart, isPartialWeek } from "@/components/trend-chart";
import { VariantTable } from "@/components/variant-table";
import { Button } from "@/components/ui/button";
import { getGenerationCurves, getTermRecord, getTermSignals, getTermTopic, getUpdatedAt } from "@/lib/data";
import { currentMeaning, headlineFor, textFor } from "@/lib/explain";
import { t, type Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { langTag, scriptLang } from "@/lib/lang";
import { L, fmtDate, fmtDateTime, fmtInt, joinGens, joinRegions, listJoin, regionLabel, sourceName, nuanceChecked } from "@/lib/labels";
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

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  // 휴대폰 위 막대(56px, sticky)에 가리지 않게 여백을 둔다
  return <h2 id={id} className="scroll-mt-[72px] text-[18px] leading-[1.3] font-semibold text-ink lg:scroll-mt-8">{children}</h2>;
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
  const [record, curves, signals, updatedAt] = await Promise.all([
    getTermRecord(termId), getGenerationCurves(termId), getTermSignals(termId, regions), getUpdatedAt(),
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
    { id: "trend", title: t(locale, "term_sec_trend"), show: showTrend },
    { id: "made", title: t(locale, "prov_title"), show: !!record.provenance },
    { id: "sources", title: t(locale, "term_sources_title").replace("{n}", fmtInt(sources.length)), show: sources.length > 0 },
    { id: "history", title: t(locale, "term_sec_history"), show: history.length > 0 },
    { id: "related", title: t(locale, "term_related"), show: related.length > 0 },
  ].filter((s) => s.show);
  const title = (id: string) => sections.find((s) => s.id === id)?.title ?? "";

  const makeHref = `/recommend?term=${encodeURIComponent(term.term_id)}`;
  const makeButton = (className: string) => (
    <Button asChild className={`h-10 rounded-md px-4 text-[14px] ${className}`}><Link href={makeHref}>{t(locale, "term_make")}</Link></Button>
  );

  return (
    <PageShell>
      <article>
        <PageHeader
          crumbs={<><Link href="/dictionary" className="hover:text-ink hover:underline">{t(locale, "dict_title")}</Link> › <span lang={langTag(term.lang)}>{term.canonical}</span></>}
          title={<span lang={langTag(term.lang)}>{term.canonical}</span>}
          description={tx ? <span lang={txLang}>{headlineFor(tx, locale)}</span> : `${t(locale, "term_no_meaning")} ${t(locale, "term_no_meaning_next")}`}
          meta={<>
            {!verified && <StatusBadge tone="muted">{t(locale, "term_badge_review")}</StatusBadge>}
            {verified && m && <span>{t(locale, "term_meta_reviewed")} <span className="tabular-nums text-charcoal">{fmtDate(m.valid_from)}</span></span>}
            {updatedAt && <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(updatedAt, locale)}</span></span>}
          </>}
          actions={canMake ? makeButton("hidden sm:inline-flex") : undefined}>
          {!verified && <p className="text-[14px] leading-[1.55] text-charcoal">{t(locale, "term_draft_notice")}</p>}
          {/* 영어판이 없으면 뜻·유래·뉘앙스가 한국어 원문으로 나온다 — 영어 독자에게 알린다(본문은 숨기지 않는다) */}
          {tx && txLang && <p className="text-[14px] leading-[1.55] text-charcoal">{t(locale, "term_untranslated_notice")}</p>}
        </PageHeader>

        <div className="mt-8 grid gap-10 xl:grid-cols-[minmax(0,720px)_280px] xl:gap-12">
          {/* 요약과 목차 — DOM 은 먼저, 1280px 이상에서 오른쪽 칸(따라 내려온다) */}
          <div className="min-w-0 space-y-4 xl:sticky xl:top-8 xl:col-start-2 xl:row-start-1 xl:self-start">
            <TermSummary locale={locale} term={term} verified={verified}
              regions={m?.regions.length ? (locale === "ko" ? m.regions.map((r) => regionLabel(locale, r)).join(", ") : joinRegions(locale, m.regions)) : null}
              gens={m?.generations.length ? (locale === "ko" ? m.generations.map((g) => labels.generation[g]).join(", ") : joinGens(locale, m.generations)) : null}
              mentions={hasTrend || signals ? last4 : null} scope={scope} lastUsed={lastUsed}
              plain={tx?.plain || null} plainLang={txLang} sources={sources.length}
              popularYear={record.popular_year} popularDecade={record.popular_decade} />
            {canMake && makeButton("w-full sm:hidden")}
            {sections.length > 1 && (
              <nav aria-label={t(locale, "term_toc")} className="hidden px-1 text-[14px] xl:block">
                <p className="text-[13px] font-semibold text-ink">{t(locale, "term_toc")}</p>
                <ul className="mt-2 space-y-1.5">
                  {sections.map((s) => <li key={s.id}><a href={`#${s.id}`} className="text-charcoal hover:text-ink hover:underline">{s.title}</a></li>)}
                </ul>
              </nav>
            )}
          </div>

          <div className="min-w-0 max-w-[720px] space-y-10 xl:col-start-1 xl:row-start-1">
            {tx?.nuance && (
              <section className="space-y-3">
                <SectionHeading id="usage">{title("usage")}</SectionHeading>
                <p lang={txLang} className="text-[16px] leading-[1.55] text-ink">{tx.nuance}</p>
                {!nuanceChecked(m) && (
                  <p className="flex flex-wrap items-center gap-2 text-[13px] text-steel">
                    <StatusBadge tone="muted">{t(locale, "nuance_unchecked")}</StatusBadge>
                    {t(locale, "nuance_unchecked_note")}
                  </p>
                )}
              </section>
            )}

            {origin && (
              <section className="space-y-3">
                <SectionHeading id="origin">{title("origin")}</SectionHeading>
                <p lang={txLang} className="text-[16px] leading-[1.55] text-ink">{origin}</p>
                {/* 각주 번호 대신 근거 한 줄 — 누르면 그 출처가 새 창으로 열린다 */}
                {originRefs.length > 0 && (
                  <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
                    <span className="text-steel">{t(locale, "term_evidence_line")}</span>
                    {originRefs.map((e) => (
                      <a key={e.evidence_id} href={e.url} target="_blank" rel="noreferrer noopener" className="inline-flex min-h-6 items-center text-link-blue hover:underline">
                        {sourceName(locale, e.source_domain)} <span className="ml-1 tabular-nums">{fmtDate(e.observed_at)}</span>
                        <span className="sr-only"> ({t(locale, "term_new_tab")})</span>
                      </a>
                    ))}
                  </p>
                )}
                {media.length > 0 && <TermMediaBlock media={media} name={term.canonical} locale={locale} />}
              </section>
            )}

            {!origin && media.length > 0 && (
              <section className="space-y-3">
                <SectionHeading id="media">{title("media")}</SectionHeading>
                <TermMediaBlock media={media} name={term.canonical} locale={locale} />
              </section>
            )}

            {topic && topic.variants.length > 1 && (
              <section className="space-y-3">
                <SectionHeading id="variants">{title("variants")}</SectionHeading>
                {showSummary && <p className="text-[16px] leading-[1.55] text-charcoal">{summaryText}</p>}
                <VariantTable variants={topic.variants} locale={locale} />
                <Link href={`/map?topic=${encodeURIComponent(topic.id)}`} className="inline-flex min-h-6 items-center text-[14px] text-link-blue hover:underline">{t(locale, "term_see_on_map")}</Link>
              </section>
            )}

            {showTrend && (
              <section className="space-y-5">
                <SectionHeading id="trend">{title("trend")}</SectionHeading>
                {hasTrend && (
                  <div className="space-y-3">
                    <dl className="flex flex-wrap items-end gap-x-10 gap-y-2">
                      <div><dt className="text-[13px] text-steel">{t(locale, "term_last4")}</dt><dd className="text-[24px] leading-[1.3] font-semibold tabular-nums text-ink">{fmtInt(last4)}</dd></div>
                      <div><dt className="text-[13px] text-steel">{t(locale, "term_prev4")}</dt><dd className="text-[24px] leading-[1.3] font-semibold tabular-nums text-ink">{fmtInt(prev4)}</dd></div>
                      <div className="pb-1 text-[13px] text-steel">{scope}</div>
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
                        {/* 비중 칸은 뺐다. 네이버 '검색' 비중이라 '쓰는 사람' 과 다르고, 대부분 한 줄 100% 라 읽을 것이 없었다 */}
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
              </section>
            )}

            {record.provenance && (
              <section className="space-y-3">
                <SectionHeading id="made">{title("made")}</SectionHeading>
                <TermProvenance p={record.provenance} locale={locale} />
                {record.risk_labels && <RiskSentences b={record.risk_labels} locale={locale} />}
                <Link href="/about" className="inline-flex min-h-6 items-center text-[14px] text-link-blue hover:underline">{t(locale, "prov_more")} →</Link>
              </section>
            )}

            {sources.length > 0 && (
              <section className="space-y-3">
                <SectionHeading id="sources">{title("sources")}</SectionHeading>
                <p className="text-[13px] text-steel">{kindCounts(record.evidences, locale)}</p>
                <SourceTable rows={sources} locale={locale} />
              </section>
            )}

            {history.length > 0 && (
              <section className="space-y-3">
                <SectionHeading id="history">{title("history")}</SectionHeading>
                <EntryHistory rows={history} locale={locale} />
              </section>
            )}

            {related.length > 0 && (
              <section className="space-y-2">
                <SectionHeading id="related">{title("related")}</SectionHeading>
                <ul className="divide-y divide-hairline border-y border-hairline">
                  {related.map((r) => (
                    <li key={r.term.term_id} className="flex min-h-11 flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2">
                      <Link href={`/dictionary/${encodeURIComponent(r.term.term_id)}`} lang={langTag(r.term.lang)} className="text-[15px] font-medium text-link-blue hover:underline">{r.term.canonical}</Link>
                      <StageCell diffusion={r.term.diffusion} lifecycle={r.term.lifecycle ?? "unknown"} locale={locale} />
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
      </article>
    </PageShell>
  );
}
