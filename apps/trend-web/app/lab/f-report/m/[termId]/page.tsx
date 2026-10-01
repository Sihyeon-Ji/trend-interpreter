import Link from "next/link";
import type { Metadata } from "next";
import { GenCurves, Ground, growthText } from "@/components/lab/f-report/charts";
import { RiskNotes, SourceList } from "@/components/lab/f-report/report-board";
import { WatchButton } from "@/components/lab/f-report/watch-button";
import { getGenerationCurves, getMeta, getTermRecord, getTermSignals, getTermTopic } from "@/lib/data";
import { langTag, scriptLang } from "@/lib/lang";
import { c, categoryLabel, diffusionLabel, regionName, riskLabel, stageLabel } from "@/lib/lab/f-report/copy";
import { combineCurves, fitClass, fmtDay, riskNotes } from "@/lib/lab/f-report";
import { toDetail } from "@/lib/lab/f-report/detail";
import { getLocale } from "@/lib/locale";
import type { Meaning } from "@/lib/types";

type Params = { params: Promise<{ termId: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const rec = await getTermRecord(termId).catch(() => null);
  return { title: rec ? `${rec.term.canonical} · ${c(locale, "brand")}` : c(locale, "entry_missing") };
}

const VERIF: Record<string, "entry_reviewed" | "entry_auto"> = { verified_human: "entry_reviewed", verified_auto: "entry_auto" };

/** 밈 항목 — 머리(낱말이 제 곡선 위에) → 대표 장면 → 유래 → 이렇게 써요 → 쓰임 추이 → 나라별 차이 → 출처 → 뜻이 바뀐 기록 */
export default async function MemeEntry({ params }: Params) {
  const [{ termId }, locale] = await Promise.all([params, getLocale()]);
  const record = await getTermRecord(termId);
  if (!record) {
    return (
      <div className="fr-state">
        <h1>{c(locale, "entry_missing")}</h1>
        <p>{c(locale, "entry_missing_hint")}</p>
        <Link href="/lab/f-report" className="fr-btn">{c(locale, "entry_back")}</Link>
      </div>
    );
  }
  const [signals, curves, topic, meta] = await Promise.all([getTermSignals(termId), getGenerationCurves(termId), getTermTopic(termId, record.term.canonical), getMeta().catch(() => null)]);
  const d = toDetail(record, locale);
  const text = locale === "en" ? d.en ?? d.ko : d.ko ?? d.en;
  const trend = combineCurves(curves, meta?.board_generated_at ?? null);
  const g = growthText(trend?.pct ?? null, locale);
  const stage = signals?.lifecycle ?? d.stage;
  const diffusion = signals?.diffusion ?? d.diffusion;
  const risk = record.term.risk_level ?? signals?.risk_level ?? null;
  const notes = riskNotes(record.term.risk_reasons ?? signals?.risk_reasons, locale);
  const regions = signals?.regions?.length ? signals.regions : [...new Set(record.meanings.flatMap((m) => m.regions ?? []))];
  const verified = d.status === "verified";
  const canMake = verified && risk !== "avoid";
  const lede = text?.definition ?? "";
  const plain = text?.plain && text.plain !== text.definition ? text.plain : null;
  const sources = d.sources;
  const originSources = sources.filter((s) => s.kind !== "short").slice(0, 2);
  const history = [...record.meanings].sort((a, b) => b.version - a.version);
  // 근거가 모자란 나라(what_changed 가 '근거 부족')는 빼고, 그 나라에서 생긴 말은 짧은 이름꼴만(문장·해시태그는 커뮤니티 글일 수 있다)
  const variants = (topic?.variants ?? []).filter((v) => v.region && !/^근거 부족/.test(v.what_changed.ko) && !/^Insufficient/i.test(v.what_changed.en));
  const shortMemes = (labels: { label: string }[]) => labels.map((m) => m.label.trim()).filter((l) => l.length <= 24 && l.split(/\s+/).length <= 3 && !/[#\n]/.test(l));
  const sections = [
    text?.origin || originSources.length ? ["origin", c(locale, "entry_origin")] : null,
    plain || text?.nuance || text?.expansion ? ["usage", c(locale, "entry_usage")] : null,
    ["trend", c(locale, "entry_trend")],
    variants.length ? ["variants", c(locale, "entry_variants")] : null,
    ["sources", c(locale, "entry_sources")],
    history.length ? ["history", c(locale, "entry_history")] : null,
  ].filter((s): s is [string, string] => !!s);
  const hasGround = !!trend && trend.smooth.length > 1 && trend.pct !== null;

  return (
    <>
      <p className="fr-crumb m-0"><Link href="/lab/f-report">{c(locale, "entry_back")}</Link></p>
      <header className="fr-hero">
        <p className="fr-hero-kind m-0">{categoryLabel(locale, d.category)}{!verified && <span className="fr-steel"> — {c(locale, "entry_under_review")}</span>}</p>
        <h1 className={`fr-hero-name ${fitClass(d.name)}`} lang={langTag(d.lang)}>{d.name}</h1>
        {d.aliases.length > 0 && <p className="fr-hero-alias"><span lang={langTag(d.lang)}>{d.aliases.join(", ")}</span></p>}
        {lede && <p className="fr-hero-lede">{lede}</p>}
        <div className="fr-hero-marks">
          <span>{stageLabel(locale, stage)}</span>
          {diffusionLabel(locale, diffusion) && <span className="fr-steel">{diffusionLabel(locale, diffusion)}</span>}
          {risk === "caution" && <span className="fr-mark is-caution">{c(locale, "risk_caution")}</span>}
          {risk === "avoid" && <span className="fr-mark is-avoid">{c(locale, "risk_avoid")}</span>}
          {risk === "none" && <span className="fr-steel">{c(locale, "risk_none")}</span>}
        </div>
        <div className="fr-hero-actions">
          {canMake && <Link href={`/recommend?term=${encodeURIComponent(d.id)}`} className="fr-btn is-primary">{c(locale, "make")}</Link>}
          <WatchButton item={{ id: d.id, name: d.name, lang: d.lang, stage, risk }} locale={locale} />
        </div>
        {hasGround ? (
          <div className="fr-hero-ground">
            {g.dir !== "none" && <p className="fr-hero-growth m-0"><b className={`fr-num is-${g.dir}`}>{g.text}</b><span>{c(locale, "interest")}, {c(locale, "growth_vs")}</span></p>}
            <Ground values={trend!.smooth} recent={trend!.recentDays} base={trend!.baseDays} className="fr-hero-chart" label={`${c(locale, "interest")} ${g.text}`} />
          </div>
        ) : (
          <div className="fr-hero-floor" />
        )}
      </header>

      <div className="fr-entry">
        <article className="fr-article">
          {(d.media || d.video) && (
            <section aria-labelledby="fr-media-h">
              <h2 id="fr-media-h">{c(locale, "entry_media")}</h2>
              {d.media?.kind === "image" ? (
                <figure className="m-0">
                  <a href={d.media.page_url} target="_blank" rel="noopener noreferrer" className="fr-media">
                    {/* eslint-disable-next-line @next/next/no-img-element -- 자유 라이선스 그림의 원래 주소만 쓴다 */}
                    <img src={d.media.url} alt={d.media.title} loading="lazy" />
                  </a>
                  <figcaption className="fr-media-cap">{d.media.title}. {d.media.attribution}, {d.media.license}</figcaption>
                </figure>
              ) : d.video ? (
                <figure className="m-0">
                  <a href={d.video.url} target="_blank" rel="noopener noreferrer" className="fr-media">
                    {/* eslint-disable-next-line @next/next/no-img-element -- 유튜브 썸네일은 밖의 주소만 쓰고 저장하지 않는다 */}
                    <img src={d.video.thumb} alt={d.video.title} loading="lazy" />
                  </a>
                  <figcaption className="fr-media-cap">{d.video.title} <a href={d.video.url} className="fr-link" target="_blank" rel="noopener noreferrer">{c(locale, "video_open")}</a></figcaption>
                </figure>
              ) : d.media ? (
                <p><a href={d.media.page_url} className="fr-link" target="_blank" rel="noopener noreferrer">{d.media.title}</a> <span className="fr-muted">{d.media.attribution}, {d.media.license}</span></p>
              ) : null}
            </section>
          )}

          {sections.some(([k]) => k === "origin") && (
            <section aria-labelledby="fr-origin-h" id="origin">
              <h2 id="fr-origin-h">{c(locale, "entry_origin")}</h2>
              {text?.origin ? <p>{text.origin}</p> : <p className="fr-muted">{c(locale, "entry_no_origin")}</p>}
              {originSources.length > 0 && <SourceList sources={originSources} locale={locale} />}
            </section>
          )}

          {sections.some(([k]) => k === "usage") && (
            <section aria-labelledby="fr-usage-h" id="usage">
              <h2 id="fr-usage-h">{c(locale, "entry_usage")}</h2>
              {plain && <blockquote className="fr-quote mb-3"><span className="fr-muted block text-[13px]">{c(locale, "usage_plain")}</span>{plain}</blockquote>}
              {text?.nuance && <p>{text.nuance}</p>}
              {text?.expansion && <p className="fr-muted">{c(locale, "entry_expansion")}: <span lang={langTag(d.lang)}>{text.expansion}</span></p>}
            </section>
          )}

          <section aria-labelledby="fr-trend-h" id="trend">
            <h2 id="fr-trend-h">{c(locale, "entry_trend")}</h2>
            {trend ? (
              <>
                {trend.pct !== null ? (
                  <p className="fr-num"><b className={`fr-change is-${g.dir}`}>{g.text}</b> <span className="fr-muted">{c(locale, "growth_vs")}. {c(locale, "interest_counted")} {trend.counted}/{trend.byGen.length}</span></p>
                ) : (
                  <p className="fr-muted">{trend.stale ? c(locale, "stale_note") : c(locale, "interest_thin")}</p>
                )}
                <GenCurves byGen={trend.byGen} locale={locale} large />
                <p className="fr-muted mt-3"><span className="fr-num">{fmtDay(trend.from)} – {fmtDay(trend.to)}</span>. {c(locale, "interest_note")} {c(locale, "interest_method")}</p>
              </>
            ) : (
              <p className="fr-muted">{c(locale, "interest_none")}</p>
            )}
          </section>

          {variants.length > 0 && (
            <section aria-labelledby="fr-var-h" id="variants">
              <h2 id="fr-var-h">{c(locale, "entry_variants")}</h2>
              <table className="fr-table">
                <thead><tr><th>{c(locale, "entry_variant_region")}</th><th>{c(locale, "entry_variant_name")}</th><th>{c(locale, "entry_variant_changed")}</th><th>{c(locale, "entry_variant_memes")}</th></tr></thead>
                <tbody>
                  {variants.map((v) => (
                    <tr key={v.region}>
                      <td className="whitespace-nowrap">{regionName(locale, v.region)}</td>
                      <td><span lang={scriptLang(v.local_name, v.region)}>{v.local_name}</span></td>
                      <td>{locale === "en" ? v.what_changed.en : v.what_changed.ko}</td>
                      <td>{shortMemes(v.local_memes).length ? shortMemes(v.local_memes).map((l) => <span key={l} lang={scriptLang(l, v.region)} className="mr-2 inline-block">{l}</span>) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section aria-labelledby="fr-src-h" id="sources">
            <h2 id="fr-src-h">{c(locale, "entry_sources")}</h2>
            {sources.length ? <SourceList sources={sources} locale={locale} /> : <p className="fr-muted">{c(locale, "entry_no_sources")}</p>}
          </section>

          {history.length > 0 && (
            <section aria-labelledby="fr-hist-h" id="history">
              <h2 id="fr-hist-h">{c(locale, "entry_history")}</h2>
              <ol className="fr-history">
                {history.map((m: Meaning) => (
                  <li key={m.meaning_id} className={m.valid_to ? "" : "is-current"}>
                    <span className="fr-when fr-num">
                      {m.valid_to ? `${fmtDay(m.valid_from)} – ${fmtDay(m.valid_to)}` : `${fmtDay(m.valid_from)} ${c(locale, "entry_since")}`}
                      {m.verification && VERIF[m.verification] ? <span className="block text-[12.5px]">{c(locale, VERIF[m.verification])}</span> : null}
                    </span>
                    <span>{m.definition}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </article>

        <aside className="fr-rail">
          <dl className="fr-facts">
            <dt>{c(locale, "stage")}</dt>
            <dd>{stageLabel(locale, stage)}</dd>
            {diffusionLabel(locale, diffusion) && <><dt>{c(locale, "spread")}</dt><dd>{diffusionLabel(locale, diffusion)}</dd></>}
            <dt>{c(locale, "risk")}</dt>
            <dd>{riskLabel(locale, risk)}<RiskNotes notes={notes} /></dd>
            <dt>{c(locale, "regions")}</dt>
            <dd>{regions.length ? regions.map((r) => regionName(locale, r)).join(", ") : "—"}</dd>
            <dt>{c(locale, "entry_first_seen")}</dt>
            <dd className="fr-num">{d.firstSeen ? fmtDay(d.firstSeen) : "—"}</dd>
            <dt>{c(locale, "last_seen")}</dt>
            <dd className="fr-num">{fmtDay(signals?.last_seen ?? d.lastSeen) || "—"}</dd>
          </dl>
          <ul className="fr-toc">
            {sections.map(([id, label]) => <li key={id}><a href={`#${id}`}>{label}</a></li>)}
          </ul>
        </aside>
      </div>
    </>
  );
}
