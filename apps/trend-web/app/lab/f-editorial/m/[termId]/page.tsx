import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AgeCurves } from "@/components/lab/f-editorial/age-curves";
import { posterSize } from "@/components/lab/f-editorial/cover";
import { FactRail, MeaningHistory, SourceList, Variants, variantRows } from "@/components/lab/f-editorial/entry-parts";
import { Masthead } from "@/components/lab/f-editorial/masthead";
import { SearchBox } from "@/components/lab/f-editorial/search-box";
import { diffusionWord, lifecycleWord, riskClass, riskKeyOf, riskReasonText, riskWord } from "@/components/lab/f-editorial/stickers";
import { StarButton, WatchDiff, type WatchState } from "@/components/lab/f-editorial/watchlist";
import { getGenerationCurves, getTermRecord, getTermSignals, getTermTopic, getUpdatedAt } from "@/lib/data";
import { currentMeaning, textFor } from "@/lib/explain";
import { fe } from "@/lib/lab/f-editorial-copy";
import { editionName, editionRegions, issueHref, originRefs, parseEdition, sourceItems } from "@/lib/lab/f-editorial";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import { getLocale } from "@/lib/locale";

/* 밈 항목 — 한 편의 기사. 큰 제목, 뜻(리드), 단계·조심·갱신을 적은 한 줄, 유래(참고 문서와 함께), 쓰임, 조심(있을 때만),
   나라별 차이, 나이대별 검색 관심(없으면 그렇다고), 출처(위키·기사·영상만, 같은 기사는 한 번), 뜻의 이력. 예문은 지어내지 않는다. */

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);   // 영어 단계 말은 소문자라 줄 첫머리에서만 대문자로
const SOURCES_SHOWN = 12;

type Params = { params: Promise<{ termId: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const record = await getTermRecord(termId).catch(() => null);
  return { title: `${record?.term.canonical ?? fe(locale, "not_found_title")}, ${fe(locale, "site")}` };
}

export default async function EntryPage({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const edition = parseEdition(sp);
  const [record, curves, signals, updatedAt] = await Promise.all([
    getTermRecord(termId), getGenerationCurves(termId), getTermSignals(termId, editionRegions(edition)), getUpdatedAt(),
  ]);
  if (!record) notFound();
  const topic = await getTermTopic(termId, record.term.canonical);

  const term = record.term;
  const meaning = currentMeaning(record);
  const tx = textFor(record, locale);
  const txLang = locale === "en" && !record.en ? "ko" : undefined;   // 번역이 없으면 한국어 원문이 나간다
  const verified = term.status === "verified";
  const risk = riskWord(term, locale);
  const canMake = verified && term.risk_level !== "avoid";
  const origin = tx?.origin && tx.origin !== "unknown" ? tx.origin : null;
  const names = [term.canonical, ...(term.aliases ?? [])];
  const sources = sourceItems(record.evidences, names, locale);
  const refs = originRefs(sources);
  const variants = variantRows(topic, names, locale);
  const lastUsed = signals?.last_used ?? signals?.last_seen ?? term.last_seen ?? null;
  const reason = riskReasonText(term, locale);
  const riskAt = term.risk_human ? term.risk_decided_at : term.risk_checked_at;
  const state: WatchState = { stage: term.lifecycle ?? "unknown", risk: riskKeyOf(term) };
  const edName = editionName(locale, edition);

  return (
    <>
      <Masthead locale={locale} edition={edition} />
      <main id="fe-main">
        <div className="fe-wrap">
          <div className="fe-issue" style={{ paddingBottom: 0 }}>
            <Link href={issueHref(edition)} className="fe-entry__back">{fe(locale, "back_issue", { edition: edName })}</Link>
            <SearchBox locale={locale} edition={edition} />
          </div>

          <article className="fe-entry">
            <header className="fe-entry__head">
              <div className="fe-entry__title">
                <h1 className={posterSize(term.canonical) === "fe-poster--longer" ? "fe-title fe-title--long" : "fe-title"} lang={langTag(term.lang)}>{term.canonical}</h1>
                <StarButton item={{ id: term.term_id, name: term.canonical, lang: term.lang }} state={state} locale={locale} />
              </div>
              {tx?.expansion && <p className="fe-entry__expansion" lang={txLang}>{tx.expansion}</p>}
              <p className="fe-lede" lang={txLang}>{tx ? tx.definition : fe(locale, "e_no_meaning")}</p>
              <div className="fe-byline">
                {verified ? (
                  <>
                    <span><strong>{cap(lifecycleWord(locale, term.lifecycle))}</strong>{term.diffusion && <>, {diffusionWord(locale, term.diffusion)}</>}</span>
                    {risk && <span className={riskClass(risk.key)}>{risk.label}</span>}
                    {meaning && <span>{fe(locale, "e_verified", { date: fmtDate(meaning.valid_from) })}</span>}
                  </>
                ) : <span>{fe(locale, "e_reviewing")}</span>}
                {updatedAt && <span>{fe(locale, "updated", { time: fmtDateTime(updatedAt, locale) })}</span>}
              </div>
              <WatchDiff id={term.term_id} state={state} locale={locale} />
              {canMake && (
                <div className="fe-entry__actions">
                  <Link href={`/recommend?term=${encodeURIComponent(term.term_id)}`} className="fe-btn fe-btn--primary">{fe(locale, "make")}</Link>
                </div>
              )}
            </header>

            <div className="fe-entry__grid">
              <div className="fe-article">
                {reason && risk && (risk.key === "caution" || risk.key === "avoid") && (
                  <section className={risk.key === "avoid" ? "fe-caution fe-caution--avoid" : "fe-caution"} aria-labelledby="fe-caution-title">
                    <h2 id="fe-caution-title" className="fe-h3">{fe(locale, "e_caution")}: {risk.label}</h2>
                    <p className="fe-body" lang={reason.lang}>{reason.text}</p>
                  </section>
                )}
                {origin && (
                  <section aria-labelledby="fe-origin-title">
                    <h2 id="fe-origin-title" className="fe-h2">{fe(locale, "e_origin")}</h2>
                    <p className="fe-body" lang={txLang}>{origin}</p>
                    {refs.length > 0 && (
                      <p className="fe-refs">
                        <span>{fe(locale, "e_sources")}</span>
                        {refs.map((s) => (
                          <a key={s.id} href={s.url} target="_blank" rel="noreferrer noopener" className="fe-link">{s.source} {fmtDate(s.date)}<span className="sr-only"> ({fe(locale, "new_tab")})</span></a>
                        ))}
                      </p>
                    )}
                  </section>
                )}
                {(tx?.nuance || tx?.plain) && (
                  <section aria-labelledby="fe-usage-title">
                    <h2 id="fe-usage-title" className="fe-h2">{fe(locale, "e_usage")}</h2>
                    {tx?.nuance && <p className="fe-body" lang={txLang}>{tx.nuance}</p>}
                    {tx?.plain && <dl className="fe-plain"><dt>{fe(locale, "e_plain")}</dt><dd lang={txLang}>{tx.plain}</dd></dl>}
                  </section>
                )}
                {variants.length > 1 && (
                  <section aria-labelledby="fe-variants-title">
                    <h2 id="fe-variants-title" className="fe-h2">{fe(locale, "e_variants")}</h2>
                    <p className="fe-note" style={{ marginTop: 0, marginBottom: 12 }}>{fe(locale, "e_variants_note")}</p>
                    <Variants rows={variants} termId={termId} edition={edition} locale={locale} />
                  </section>
                )}
                <section aria-labelledby="fe-ages-title">
                  <h2 id="fe-ages-title" className="fe-h2">{fe(locale, "e_ages")}</h2>
                  <AgeCurves curves={curves} locale={locale} />
                </section>
                {sources.length > 0 && (
                  <section id="fe-sources" aria-labelledby="fe-sources-title">
                    <h2 id="fe-sources-title" className="fe-h2">{fe(locale, "e_sources")}<span className="fe-rubric__count">{sources.length}</span></h2>
                    <p className="fe-note" style={{ marginTop: 0, marginBottom: 12 }}>{fe(locale, "e_sources_note")}</p>
                    <SourceList items={sources.slice(0, SOURCES_SHOWN)} locale={locale} />
                    {sources.length > SOURCES_SHOWN && (
                      <details className="fe-rest">
                        <summary>{fe(locale, "e_sources_more", { n: sources.length - SOURCES_SHOWN })}</summary>
                        <SourceList items={sources.slice(SOURCES_SHOWN)} locale={locale} />
                      </details>
                    )}
                  </section>
                )}
                {record.meanings.length > 0 && (
                  <section aria-labelledby="fe-history-title">
                    <h2 id="fe-history-title" className="fe-h2">{fe(locale, "e_history")}</h2>
                    <p className="fe-note" style={{ marginTop: 0, marginBottom: 12 }}>{fe(locale, "e_history_note")}</p>
                    <MeaningHistory meanings={record.meanings} firstSeen={term.first_seen} riskAt={riskAt} locale={locale} />
                  </section>
                )}
              </div>
              <FactRail term={term} verified={verified} meaning={meaning} usage={record.usage} lastUsed={lastUsed} sources={sources.length} locale={locale} />
            </div>
          </article>
        </div>
      </main>
    </>
  );
}
