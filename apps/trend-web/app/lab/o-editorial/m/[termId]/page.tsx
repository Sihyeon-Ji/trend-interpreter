/* eslint-disable @next/next/no-img-element -- 위키미디어 그림·유튜브 미리보기는 주소만 쓰는 평범한 <img>(파일을 받지 않는다) */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AgeCurves } from "@/components/lab/o-editorial/age-curves";
import { ScrapButton } from "@/components/lab/o-editorial/client";
import { FitName, Tape } from "@/components/lab/o-editorial/type";
import { getGenerationCurves, getTermRecord, getTermSignals, getTermTopic } from "@/lib/data";
import { termRegions, lastUsedOf } from "@/lib/dictionary/regions";
import type { Locale } from "@/lib/i18n";
import { currentMeaning, textFor } from "@/lib/explain";
import { langTag, scriptLang } from "@/lib/lang";
import {
  ageName, copy, editionHref, editionName, editionRegions, entryHref, fmtDay, hottestAge, parseEdition, regionName, riskKind,
  riskNotes, riskTone, riskWhy, riskWord, searchSummary, stageSentence, stageTapes, youtubeId,
} from "@/lib/lab/o-editorial";
import { ledeFor, originSources, sourceList, type SourceItem } from "@/lib/lab/o-editorial/server";
import { getLocale } from "@/lib/locale";

/* 기사 — 한 밈의 특집. 제목(원문, lang) → 뜻 한 줄 → 단계·쓸 때 조심·확인한 날 → 본문(유래·쓰는 법·조심할 점·나라마다·누가 찾나·출처·기록).
   '브랜드가 써도 될까' 상자는 DOM 에서 본문보다 앞이라 휴대폰·화면 읽기 순서가 보이는 순서와 같다. 예문은 지어내지 않는다. */

type Params = { params: Promise<{ termId: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };
const SOURCES_SHOWN = 8;   // 나머지는 '더 보기' 안에 — 기사 수십 건이 본문보다 길어지지 않게

function SourceRow({ s, locale }: { s: SourceItem; locale: Locale }) {
  return (
    <li>
      <span className="oe-meta oe-num oe-source-date">{fmtDay(locale, s.date)}</span>
      <span className="oe-meta oe-source-from">{s.source}</span>
      <a className="oe-source-link" href={s.url} target="_blank" rel="noreferrer noopener" lang={s.titleLang}>{s.title}<span className="oe-sr"> ({copy(locale).newTab})</span></a>
    </li>
  );
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const record = await getTermRecord(termId).catch(() => null);
  const c = copy(locale);
  return { title: record ? `${record.term.canonical} | ${c.site}` : c.site };
}

export default async function EntryPage({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const c = copy(locale);
  const edition = parseEdition(sp.regions);
  const [record, curves, signals] = await Promise.all([
    getTermRecord(termId), getGenerationCurves(termId), getTermSignals(termId, editionRegions(edition)),
  ]);
  if (!record) notFound();
  const topic = await getTermTopic(termId, record.term.canonical);

  const term = record.term;
  const lang = langTag(term.lang);
  const verified = term.status === "verified";
  const m = currentMeaning(record);
  const tx = textFor(record, locale);
  const txLang = locale === "en" && !record.en ? "ko" : undefined;
  const stage = { lifecycle: signals?.lifecycle ?? term.lifecycle ?? "unknown", diffusion: signals?.diffusion ?? term.diffusion ?? null };
  const risk = riskKind(signals ?? term);
  const notes = riskNotes(locale, (signals ?? term).risk_reasons);
  const tone = riskTone(risk);
  const canMake = verified && risk !== "avoid";
  const flagged = risk === "caution" || risk === "avoid";
  const regions = signals?.regions?.length ? signals.regions : termRegions(record);
  const lastUsed = signals ? signals.last_used ?? signals.last_seen ?? null : lastUsedOf(record);
  const search = searchSummary(curves);
  const hot = hottestAge(search);
  const origin = tx?.origin && tx.origin !== "unknown" ? tx.origin : null;

  const sources = sourceList(record.evidences, [term.canonical, ...(term.aliases ?? [])], locale);
  const originRefs = originSources(sources);

  const variants = (topic?.variants ?? []).filter((v) => v.region && v.local_name);
  const showVariants = variants.length > 1;
  const summaryRaw = topic?.summary?.[locale] ?? "";
  // 주제 요약이 뜻과 같은 말이면 되풀이하지 않는다
  const summary = summaryRaw && !summaryRaw.startsWith("근거 부족") && !(tx?.definition && summaryRaw.includes(tx.definition.slice(0, 16))) ? summaryRaw : null;

  const junk = (d: string) => !d || d.trim() === term.canonical.trim() || d.startsWith("근거 부족");
  const history = [...record.meanings].filter((x) => x.verification !== "rejected" && !junk(x.definition)).sort((a, b) => b.version - a.version);

  const image = record.media?.find((x) => x.kind === "image");
  const video = record.media?.find((x) => x.kind === "video" && youtubeId(x.url));
  const vid = video ? youtubeId(video.url) : null;
  const scrap = { id: term.term_id, name: term.canonical, lang, lifecycle: stage.lifecycle, diffusion: stage.diffusion, risk };
  const makeHref = `/recommend?term=${encodeURIComponent(term.term_id)}`;

  return (
    <article>
      <header className="oe-wrap oe-entry-head">
        <Link href={editionHref(edition)} className="oe-quiet-link" style={{ fontSize: 15, fontWeight: 600 }}>{c.backTo(editionName(locale, edition))}</Link>
        {!verified && (
          <p style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <Tape tone="unknown">{c.underReview}</Tape>
            <span className="oe-meta" style={{ fontSize: 15 }}>{c.underReviewNote}</span>
          </p>
        )}
        <h1 className="oe-fit oe-entry-name"><FitName name={term.canonical} lang={lang} maxLines={3} splitAbove={4.4} /></h1>
        <p className="oe-entry-lede" lang={txLang}>{tx ? ledeFor(tx, locale) : c.noMeaning}</p>
        <dl className="oe-byline">
          <div>
            <dt>{c.stageLabel}</dt>
            <dd className="oe-tapes">{stageTapes(locale, stage).map((s) => <Tape key={s.text} tone={s.tone}>{s.text}</Tape>)}</dd>
          </div>
          <div>
            <dt>{c.riskLabel}</dt>
            <dd>{tone ? <Tape tone={tone}>{riskWord(locale, risk)}</Tape> : <strong>{riskWord(locale, risk)}</strong>}</dd>
          </div>
          {verified && m?.valid_from && (
            <div><dt>{c.checkedLabel}</dt><dd className="oe-num">{fmtDay(locale, m.valid_from)}</dd></div>
          )}
          {lastUsed && <div><dt>{c.lastUsedLabel}</dt><dd className="oe-num">{fmtDay(locale, lastUsed)}</dd></div>}
        </dl>
        <div className="oe-entry-actions">
          {canMake && <Link href={makeHref} className="oe-btn oe-btn-primary">{c.make}</Link>}
          <ScrapButton locale={locale} scrap={scrap} labelled />
        </div>
      </header>

      <div className="oe-wrap oe-entry-body">
        <aside className="oe-fact" aria-labelledby="oe-fact-title">
          <h2 id="oe-fact-title">{c.factTitle}</h2>
          <dl>
            <div>
              <dt>{c.riskLabel}</dt>
              <dd>
                {tone ? <Tape tone={tone}>{riskWord(locale, risk)}</Tape> : <strong>{riskWord(locale, risk)}</strong>}
                <span style={{ display: "block", marginTop: 8 }}>{riskWhy(locale, risk)}</span>
                {/* 주의·사용 자제면 이유는 본문 '조심할 점' 한 곳에만 — 같은 문장이 한 화면에 두 번 나오지 않게 */}
                {flagged
                  ? <a href="#caution" className="oe-link" style={{ display: "inline-block", marginTop: 8, fontSize: 14, fontWeight: 600 }}>{c.factCautionMore}</a>
                  : notes.slice(0, 3).map((n) => <span key={n} className="oe-meta" style={{ display: "block", marginTop: 4, fontSize: 14 }}>{n}</span>)}
              </dd>
            </div>
            <div>
              <dt>{c.stageLabel}</dt>
              <dd>{stageSentence(locale, stage)}</dd>
            </div>
            {regions.length > 0 && <div><dt>{c.whereLabel}</dt><dd>{regions.map((r) => regionName(locale, r)).join(", ")}</dd></div>}
            <div>
              <dt>{c.whoLabel}</dt>
              <dd>{hot?.peak ? c.whoPeak(ageName(locale, hot.gen), fmtDay(locale, hot.peak)) : c.whoNone}</dd>
            </div>
            {tx?.plain && <div><dt>{c.plainLabel}</dt><dd lang={txLang}>{tx.plain}</dd></div>}
            {(term.aliases?.length ?? 0) > 0 && (
              <div>
                <dt>{c.aliasesLabel}</dt>
                <dd>{term.aliases!.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a)}>{a}</span></span>)}</dd>
              </div>
            )}
          </dl>
          {canMake ? (
            <div className="oe-fact-make">
              <Link href={makeHref} className="oe-btn oe-btn-primary">{c.make}</Link>
              <p className="oe-meta" style={{ marginTop: 10, fontSize: 14 }}>{c.makeNote}</p>
            </div>
          ) : risk === "avoid" ? <p className="oe-meta" style={{ marginTop: 16, fontSize: 14 }}>{c.avoidNoMake}</p> : null}
        </aside>

        <div className="oe-article">
          {(image || vid) && (
            <section aria-label={c.mediaFrom}>
              {image && (
                <figure className="oe-figure">
                  <img src={image.url} alt={term.canonical} loading="lazy" />
                  <figcaption className="oe-meta">
                    {c.mediaFrom} <a className="oe-link" href={image.page_url} target="_blank" rel="noreferrer noopener">Wikimedia Commons<span className="oe-sr"> ({c.newTab})</span></a>
                    {image.license && <>, {c.mediaLicense} {image.license}</>}
                  </figcaption>
                </figure>
              )}
              {!image && vid && (
                <figure className="oe-figure">
                  <a href={video!.page_url || video!.url} target="_blank" rel="noreferrer noopener" className="oe-thumb" style={{ maxWidth: 480 }}>
                    <img src={`https://i.ytimg.com/vi/${vid}/mqdefault.jpg`} alt={c.videoAlt(term.canonical)} loading="lazy" width={480} height={270} />
                  </a>
                  <figcaption className="oe-meta"><a className="oe-link" href={video!.page_url || video!.url} target="_blank" rel="noreferrer noopener">{c.watchVideo}<span className="oe-sr"> ({c.newTab})</span></a></figcaption>
                </figure>
              )}
            </section>
          )}

          <section>
            <h2 id="origin">{c.secOrigin}</h2>
            <p lang={txLang}>{origin ?? c.noOrigin}</p>
            {originRefs.length > 0 && (
              <p className="oe-meta" style={{ display: "flex", flexWrap: "wrap", gap: "4px 16px" }}>
                <span>{c.sourceLine}</span>
                {originRefs.map((s) => (
                  <a key={s.id} className="oe-link" href={s.url} target="_blank" rel="noreferrer noopener">
                    {s.source} <span className="oe-num">{fmtDay(locale, s.date)}</span><span className="oe-sr"> ({c.newTab})</span>
                  </a>
                ))}
              </p>
            )}
          </section>

          {/* '쉽게 말하면' 은 옆 상자(브랜드가 써도 될까)에만 — 본문에 인용처럼 다시 크게 세우던 것을 뺐다(같은 말이 한 화면에 두 번) */}
          {tx?.nuance && (
            <section>
              <h2 id="use">{c.secUse}</h2>
              <p lang={txLang}>{tx.nuance}</p>
            </section>
          )}

          {flagged && (
            <section>
              <h2 id="caution">{c.secCaution}</h2>
              <div className="oe-caution-box" data-level={risk}>
                <p style={{ marginTop: 0, fontWeight: 700 }}>{riskWord(locale, risk)}</p>
                <p style={{ marginTop: 4 }}>{riskWhy(locale, risk)}</p>
                {notes.length > 0 && <ul>{notes.map((n) => <li key={n}>{n}</li>)}</ul>}
              </div>
            </section>
          )}

          {showVariants && (
            <section>
              <h2 id="countries">{c.secCountries}</h2>
              {summary && <p>{summary}</p>}
              {/* 나라마다 한 줄 — 그 나라에서 부르는 이름이 머리, 무엇이 다른지가 본문. 휴대폰에서는 위아래로 쌓인다 */}
              <ul className="oe-variants">
                {variants.map((v) => {
                  const changed = v.what_changed?.[locale];
                  // 그 나라에서 생긴 말(local_memes)은 커뮤니티 글 문장이 섞여 들어와 싣지 않는다(데이터 방침 09-29) — 사전에 오른 밈만 잇는다
                  const linked = v.linked.filter((x) => x.term_id && x.term_id !== termId).slice(0, 3);
                  return (
                    <li key={`${v.region}-${v.local_name}`}>
                      <p className="oe-variant-head">
                        <span className="oe-variant-region">{regionName(locale, v.region)}</span>
                        <span className="oe-variant-name" lang={scriptLang(v.local_name, v.region)}>{v.local_name}</span>
                      </p>
                      <div>
                        <p>{changed && !changed.startsWith("근거 부족") ? changed : <span className="oe-meta" style={{ fontSize: 15 }}>{c.variantUnknown}</span>}</p>
                        {linked.length > 0 && (
                          <p className="oe-meta" style={{ fontSize: 14 }}>
                            {c.linkedCol}{" "}
                            {linked.map((x, i) => <span key={x.term_id}>{i > 0 && ", "}<Link className="oe-link" href={entryHref(x.term_id!, edition)} lang={scriptLang(x.label, v.region)}>{x.label}</Link></span>)}
                          </p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          <section>
            <h2 id="search">{c.secSearch}</h2>
            {search ? (
              <>
                <p className="oe-meta" style={{ fontSize: 15 }}>{c.searchIntro}</p>
                <AgeCurves locale={locale} ages={search.ages} />
              </>
            ) : <p className="oe-meta" style={{ fontSize: 15 }}>{c.searchNone}</p>}
          </section>

          {sources.length > 0 && (
            <section>
              <h2 id="sources">{c.secSources}</h2>
              <ul className="oe-sources">
                {sources.slice(0, SOURCES_SHOWN).map((s) => <SourceRow key={s.id} s={s} locale={locale} />)}
              </ul>
              {sources.length > SOURCES_SHOWN && (
                <details className="oe-details oe-sources-more">
                  <summary>{c.sourcesMore(sources.length - SOURCES_SHOWN)}</summary>
                  <ul className="oe-sources">
                    {sources.slice(SOURCES_SHOWN, 60).map((s) => <SourceRow key={s.id} s={s} locale={locale} />)}
                  </ul>
                </details>
              )}
            </section>
          )}

          <section>
            <h2 id="history">{c.secHistory}</h2>
            {history.length <= 1 ? (
              <p>{c.historyOnlyOne}{history[0] && <span className="oe-meta oe-num" style={{ display: "block" }}>{c.historyFrom(fmtDay(locale, history[0].valid_from))}</span>}</p>
            ) : (
              <ol className="oe-history" style={{ marginTop: 16 }}>
                {history.map((h) => (
                  <li key={h.meaning_id ?? h.version}>
                    <span className="oe-meta oe-num">
                      {h.valid_to ? c.historyRange(fmtDay(locale, h.valid_from), fmtDay(locale, h.valid_to)) : `${c.historyNow}, ${c.historyFrom(fmtDay(locale, h.valid_from))}`}
                    </span>
                    <span lang={scriptLang(h.definition)}>{h.definition}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </div>
    </article>
  );
}
