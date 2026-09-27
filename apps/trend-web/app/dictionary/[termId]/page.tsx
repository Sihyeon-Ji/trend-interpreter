import Link from "next/link";
import { TermMediaBlock } from "@/components/term-media";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/page-shell";
import { ChangeHistory } from "@/components/history";
import { Sparkline } from "@/components/sparkline";
import { TermTimeline } from "@/components/term-timeline";
import { GenerationCurves } from "@/components/generation-curves";
import { currentMeaning, textFor } from "@/lib/explain";
import { getGenerationCurves, getTermRecord, getTermRecords, getTrendBoard } from "@/lib/data";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, joinGens, joinRegions, regionLabel, termLangLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { Evidence, TermRecord } from "@/lib/types";

function trendSentence(locale: Locale, lifecycle: string, last4: number, prev4: number) {
  const pct = prev4 === 0 ? null : Math.abs(Math.round(((last4 - prev4) / prev4) * 100));
  if (locale === "ko") {
    const cmp = pct === null ? "" : last4 === prev4 ? " 이전 4주와 같습니다." : ` 이전 4주보다 ${pct}% ${last4 > prev4 ? "많습니다" : "적습니다"}.`;
    return cmp ? `${lifecycle}. 최근 4주 동안 ${last4}번 언급됐고,${cmp}` : `${lifecycle}. 최근 4주 동안 ${last4}번 언급됐습니다.`;
  }
  const cmp = pct === null ? "" : last4 === prev4 ? ", the same as the previous four weeks." : `, ${pct}% ${last4 > prev4 ? "more" : "fewer"} than the previous four weeks.`;
  return `${lifecycle[0].toUpperCase()}${lifecycle.slice(1)}. Mentioned ${last4} times in the last four weeks${cmp || "."}`;
}

function SectionHeading({ id, num, title }: { id: string; num: number; title: string }) {
  return (
    <h2 id={id} className="scroll-mt-4 border-b border-hairline pb-1 text-[18px] font-semibold text-ink">
      <span className="mr-2 text-steel">{num}.</span>{title}
    </h2>
  );
}

function RefLink({ n }: { n: number }) {
  return <a href={`#ref-${n}`} className="ml-0.5 align-super text-[11px] text-link-blue hover:underline">[{n}]</a>;
}

/* 위키 문서: 왼쪽 본문(목차 + 번호 절 + 각주), 오른쪽 정보상자. */
/** 근거 한 줄. 제목과 같은 말을 두 번 찍지 않고, 표제어가 보이는 자리를 잘라 낸다.
 *  커뮤니티 발췌는 "@handle · 1♥ — " 가 앞에 붙어 제목과 다르게 보이지만 내용은 같고,
 *  앞에서부터 자르면 정작 그 표현이 잘려 나간다(2026-09-16 검토). 그래서 표제어를 가운데 두고 자른다. */
function snippet(e: Evidence, term: string, width = 60): string {
  const raw = (e.excerpt ?? "").trim();
  if (!raw) return "";
  const head = (e.title ?? "").trim().slice(0, 30);
  if (head && raw.includes(head)) {
    const rest = raw.replace(head, "").replace(/^[\s·—@♥0-9]+/, "").trim();
    if (rest.length < 15) return "";      // 제목을 되풀이할 뿐이면 내지 않는다
  }
  const at = raw.toLowerCase().indexOf(term.toLowerCase());
  if (at < 0 || raw.length <= width * 2) return raw.slice(0, width * 2);
  const from = Math.max(0, at - width);
  const to = Math.min(raw.length, at + term.length + width);
  return `${from > 0 ? "…" : ""}${raw.slice(from, to)}${to < raw.length ? "…" : ""}`;
}

export default async function TermPage({ params }: { params: Promise<{ termId: string }> }) {
  const { termId } = await params;
  const [record, locale, curves, board, all] = await Promise.all([getTermRecord(termId), getLocale(), getGenerationCurves(termId), getTrendBoard(), getTermRecords()]);
  if (!record) notFound();
  const labels = L(locale);
  const m = currentMeaning(record);
  const tx = textFor(record, locale);
  const usage = [...record.usage].sort((a, b) => a.first_seen.localeCompare(b.first_seen));
  const hasTrend = record.weekly.some((p) => p.count > 0);   // 0 만 이어진 주간 자료는 없는 것과 같다
  const last4 = record.weekly.slice(-4).reduce((a, p) => a + p.count, 0);
  const prev4 = record.weekly.slice(-8, -4).reduce((a, p) => a + p.count, 0);
  const refs = [...record.evidences].sort((a, b) => a.observed_at.localeCompare(b.observed_at));
  const refNo = (id: string) => refs.findIndex((e) => e.evidence_id === id) + 1;
  const originRefs = refs.filter((e) => e.kind === "news" || e.kind === "short" || e.kind === "web").slice(0, 2);
  const topic = board.topics.find((x) => x.variants.some((v) => v.term_id === record.term.term_id) || x.name.ko === record.term.canonical || x.name.en === record.term.canonical);
  const related: TermRecord[] = all.filter((r) => r.term.term_id !== record.term.term_id && r.category === record.category && r.term.status === "verified").slice(0, 8);
  const lastEvent = [record.term.last_seen, ...record.meanings.map((x) => x.valid_from)].filter(Boolean).sort().at(-1) ?? null;
  const nextCheck = lastEvent ? new Date(new Date(lastEvent).getTime() + record.recheck_days * 86400000).toISOString() : null;

  const sections: { id: string; title: string; show: boolean }[] = [
    { id: "meaning", title: t(locale, "term_meaning"), show: !!m },
    { id: "media", title: t(locale, "term_media"), show: (record.media?.length ?? 0) > 0 },
    { id: "origin", title: t(locale, "term_origin"), show: !!tx?.origin && tx.origin !== "unknown" },
    { id: "usage", title: t(locale, "term_sec_usage"), show: !!m },
    { id: "variants", title: t(locale, "term_sec_variants"), show: !!topic && topic.variants.length > 1 },
    { id: "trend", title: t(locale, "term_trend"), show: hasTrend || usage.length > 0 },
    { id: "generations", title: t(locale, "term_gen_curves"), show: curves.length > 0 },
    { id: "timeline", title: t(locale, "term_timeline"), show: true },
    { id: "related", title: t(locale, "term_related"), show: related.length > 0 || (record.term.aliases?.length ?? 0) > 0 },
    { id: "refs", title: t(locale, "term_refs"), show: refs.length > 0 },
    { id: "history", title: t(locale, "term_history"), show: record.meanings.length > 0 },
  ].filter((s) => s.show);
  const heading = (id: string) => <SectionHeading id={id} num={sections.findIndex((s) => s.id === id) + 1} title={sections.find((s) => s.id === id)?.title ?? ""} />;

  return (
    <PageShell>
      <article>
        <nav className="text-[13px] text-steel"><Link href="/dictionary" className="hover:text-ink">{t(locale, "dict_title")}</Link> › {record.term.canonical}</nav>
        <h1 className="mt-2 text-[30px] font-semibold text-ink">{record.term.canonical}</h1>
        <p className="mt-1 text-[14px] text-steel">
          {labels.category[record.category]} · {labels.verification[m?.verification ?? "unverified"]}
          {record.term.aliases && record.term.aliases.length > 0 && <> · {t(locale, "term_other_spellings")}: {record.term.aliases.join(", ")}</>}
        </p>
        {record.term.status === "needs_review" && (
          <p className="mt-4 border border-hairline p-3 text-[14px] text-charcoal"><span className="font-medium text-ink">{t(locale, "term_pending")}</span> {t(locale, "term_pending_more")}</p>
        )}

        <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="min-w-0 space-y-10">
            {/* 목차 */}
            <nav aria-label={t(locale, "term_toc")} className="inline-block border border-hairline px-5 py-3 text-[14px]">
              <p className="font-semibold text-ink">{t(locale, "term_toc")}</p>
              <ol className="mt-1.5 space-y-0.5">
                {sections.map((s, i) => <li key={s.id}><a href={`#${s.id}`} className="text-link-blue hover:underline"><span className="mr-1.5 text-steel">{i + 1}.</span>{s.title}</a></li>)}
              </ol>
            </nav>

            {m && tx && (
              <section className="space-y-3">
                {heading("meaning")}
                <p className="text-[17px] leading-[1.7] text-ink">
                  {tx.expansion && <span className="font-semibold">{tx.expansion}. </span>}
                  {tx.definition}
                </p>
                {tx.plain && <p className="text-[14px] text-charcoal"><span className="text-steel">{t(locale, "term_plain")}:</span> {tx.plain}</p>}
              </section>
            )}

            {(record.media?.length ?? 0) > 0 && (
              <section className="space-y-3">
                {heading("media")}
                <TermMediaBlock media={record.media ?? []} name={record.term.canonical} locale={locale} />
              </section>
            )}

            {tx?.origin && tx.origin !== "unknown" && (
              <section className="space-y-3">
                {heading("origin")}
                <p className="text-[15px] leading-[1.7] text-charcoal">{tx.origin}{originRefs.map((e) => <RefLink key={e.evidence_id} n={refNo(e.evidence_id)} />)}</p>
              </section>
            )}

            {m && (
              <section className="space-y-3">
                {heading("usage")}
                {tx?.nuance && <p className="text-[15px] leading-[1.7] text-charcoal">{tx.nuance}</p>}
                <p className="text-[14px] text-charcoal">
                  {locale === "ko" ? `주로 ${joinGens(locale, m.generations)}가 ${joinRegions(locale, m.regions)}에서 씁니다.` : `Mostly used by people in their ${joinGens(locale, m.generations)} in ${joinRegions(locale, m.regions)}.`}
                </p>
              </section>
            )}

            {topic && topic.variants.length > 1 && (
              <section className="space-y-3">
                {heading("variants")}
                <p className="text-[14px] text-charcoal">{topic.summary[locale]}</p>
                <ul className="divide-y divide-hairline border-y border-hairline text-[14px]">
                  {topic.variants.map((v) => (
                    <li key={v.region} className="grid gap-1 py-2.5 sm:grid-cols-[160px_1fr]">
                      <span className="font-medium text-ink">{regionLabel(locale, v.region)} <span className="text-steel">· {v.local_name}</span></span>
                      <div className="text-charcoal">
                        {v.what_changed[locale]}
                        {v.local_memes.length > 0 && <span className="text-steel"> — {v.local_memes.map((x) => x.label).join(", ")}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
                <Link href={`/map?topic=${topic.id}`} className="inline-block text-[13px] text-link-blue hover:underline">{t(locale, "term_see_on_globe")}</Link>
              </section>
            )}

            {(hasTrend || usage.length > 0) && (
              <section className="space-y-3">
                {heading("trend")}
                {/* 언급이 한 건도 없으면 추세 문장도 선도 내지 않는다. 0 이 열두 칸 이어진 선은 정보가 아니다. */}
                {hasTrend && (
                  <>
                    <p className="text-[14px] text-charcoal">{trendSentence(locale, labels.lifecycle[record.term.lifecycle ?? "unknown"], last4, prev4)}</p>
                    <Sparkline points={record.weekly} width={480} height={64} className="w-full max-w-[480px]" />
                  </>
                )}
                {usage.length > 0 && (
                  <table className="w-full max-w-[560px] text-left text-[14px]">
                    <thead className="border-b border-hairline text-[13px] font-medium text-steel whitespace-nowrap">
                      <tr><th className="py-2 pr-4">{t(locale, "term_col_where")}</th><th className="py-2">{t(locale, "term_col_first")}</th></tr>
                    </thead>
                    <tbody className="divide-y divide-hairline-soft">
                      {/* 비중 칸은 뺐다. 네이버 '검색' 비중이라 '쓰는 사람' 과 다르고(모르는 사람이 검색한다),
                          272개 중 242개가 한 줄 100% 거나 전부 같은 값이라 읽을 것이 없었다. */}
                      {usage.map((u) => (
                        <tr key={u.segment.segment_id}>
                          <td className="py-2 pr-4 text-ink">{regionLabel(locale, u.segment.region)}, {labels.generation[u.segment.generation]}</td>
                          <td className="py-2 tabular-nums text-charcoal">{fmtDate(u.first_seen)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            )}

            {curves.length > 0 && (
              <section className="space-y-3">
                {heading("generations")}
                <GenerationCurves curves={curves} locale={locale} />
              </section>
            )}

            <section className="space-y-3">
              {heading("timeline")}
              <TermTimeline record={record} locale={locale} />
            </section>

            {(related.length > 0 || (record.term.aliases?.length ?? 0) > 0) && (
              <section className="space-y-2">
                {heading("related")}
                {record.term.aliases && record.term.aliases.length > 0 && <p className="text-[14px] text-charcoal"><span className="text-steel">{t(locale, "term_other_spellings")}:</span> {record.term.aliases.join(", ")}</p>}
                {related.length > 0 && (
                  <p className="text-[14px] text-charcoal">
                    <span className="text-steel">{t(locale, "term_same_category")}:</span>{" "}
                    {related.map((r, i) => <span key={r.term.term_id}>{i > 0 && ", "}<Link href={`/dictionary/${r.term.term_id}`} className="text-link-blue hover:underline">{r.term.canonical}</Link></span>)}
                  </p>
                )}
              </section>
            )}

            {refs.length > 0 && (
              <section className="space-y-2">
                {heading("refs")}
                <ol className="space-y-1.5 text-[13px]">
                  {refs.map((e, i) => (
                    <li key={e.evidence_id} id={`ref-${i + 1}`} className="grid grid-cols-[28px_1fr] gap-2 scroll-mt-4">
                      <span className="text-steel tabular-nums">[{i + 1}]</span>
                      <span className="text-charcoal">
                        <span className="text-steel">{labels.evidenceKind[e.kind]} · {e.source_domain} · {fmtDate(e.observed_at)}</span>{" "}
                        {e.url ? <Link href={e.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">{e.title || e.url}</Link> : e.title}
                        {snippet(e, record.term.canonical) && (
                          <span className="block text-steel">“{snippet(e, record.term.canonical)}”</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {record.meanings.length > 0 && (
              <section className="space-y-2">
                {heading("history")}
                <ChangeHistory meanings={record.meanings} locale={locale} />
                <p className="text-[13px] text-steel">
                  {t(locale, "term_first_seen")} {fmtDate(record.term.first_seen)} · {t(locale, "term_last_seen")} {fmtDate(record.term.last_seen)}
                  {locale === "en" && <> · {t(locale, "term_original_note")}</>}
                </p>
              </section>
            )}
          </div>

          {/* 정보상자 */}
          <aside className="lg:sticky lg:top-4 lg:self-start">
            <div className="border border-hairline">
              <p className="border-b border-hairline bg-[#f6f7f8] px-4 py-2 text-[14px] font-semibold text-ink">{record.term.canonical}</p>
              <dl className="grid grid-cols-[88px_1fr] gap-x-3 gap-y-2 px-4 py-3 text-[13px]">
                <dt className="text-steel">{t(locale, "dict_categories")}</dt><dd className="text-charcoal">{labels.category[record.category]}</dd>
                <dt className="text-steel">{t(locale, "term_info_lang")}</dt><dd className="text-charcoal">{termLangLabel(locale, record.term.lang ?? "ko")}</dd>
                <dt className="text-steel">{t(locale, "term_info_status")}</dt><dd className="text-charcoal">{labels.verification[m?.verification ?? "unverified"]}</dd>
                <dt className="text-steel">{t(locale, "term_info_lifecycle")}</dt><dd className="text-charcoal">{labels.lifecycle[record.term.lifecycle ?? "unknown"]}</dd>
                {m && <><dt className="text-steel">{t(locale, "term_used_by")}</dt><dd className="text-charcoal">{joinGens(locale, m.generations)}</dd></>}
                {m && <><dt className="text-steel">{t(locale, "term_where")}</dt><dd className="text-charcoal">{joinRegions(locale, m.regions)}</dd></>}
                <dt className="text-steel">{t(locale, "term_first_seen")}</dt><dd className="text-charcoal tabular-nums">{fmtDate(record.term.first_seen)}</dd>
                <dt className="text-steel">{t(locale, "term_last_seen")}</dt><dd className="text-charcoal tabular-nums">{fmtDate(record.term.last_seen)}</dd>
                {nextCheck && <><dt className="text-steel">{t(locale, "term_info_next")}</dt><dd className="text-charcoal tabular-nums">{fmtDate(nextCheck)}</dd></>}
                <dt className="text-steel">{t(locale, "term_info_evidence")}</dt><dd className="text-charcoal tabular-nums">{record.evidences.length}</dd>
              </dl>
            </div>
          </aside>
        </div>
      </article>
    </PageShell>
  );
}
