import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FitName, Growth, RiskMark, RiskNotes } from "@/components/lab/o-report/bits";
import { SilhouetteShape } from "@/components/lab/o-report/charts";
import { GenGrid, IndexChart } from "@/components/lab/o-report/entry-charts";
import { EntryWatch } from "@/components/lab/o-report/entry-watch";
import type { Locale } from "@/lib/i18n";
import { fmtDay, readingOf, type RiskKey, type Silhouette } from "@/lib/lab/o-report";
import { spreadWord, stageWord, tr, type CopyKey } from "@/lib/lab/o-report-copy";
import { loadEntry, parseRegions, type Entry } from "@/lib/lab/o-report-data";
import { getTermRecord } from "@/lib/data";
import { scriptLang } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";

/* 초안 1 밈 항목 — 머리(원문 이름·다른 표기·뜻 한 줄·단계·쓸 때 조심·만들기·지켜보기) → 대표 자료 → 유래 → 이렇게 써요 →
   쓰임 추이 → 나라별 차이 → 출처 → 뜻이 바뀐 기록. 절 제목은 왼쪽 칸, 내용은 오른쪽 칸(리포트의 '숫자는 이렇게 셌어요' 와 같은 틀).
   예문은 만들지 않는다 — 사전에 실린 쓰임·쉬운 말만. 출처는 위키·기사·영상만(같은 기사는 원래 언론사 하나), 커뮤니티 글은 건수만. */

type Params = { params: Promise<{ termId: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { termId } = await params;
  const r = await getTermRecord(termId).catch(() => null);
  return { title: r ? r.term.canonical : tr(await getLocale(), "page_title") };
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-h`} className="grid gap-4 border-t border-[var(--or-line)] py-8 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-12 lg:py-10">
      <h2 id={`${id}-h`} className="scroll-mt-24 text-[21px] leading-tight font-bold">{title}</h2>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function shapeOf(e: Entry): Silhouette | null {
  const t = e.trend;
  if (!t || t.growth4 == null) return null;
  const step = 2;
  const values: number[] = [];
  for (let i = t.daily.length - 1; i >= 0; i -= step) values.unshift(t.daily[i]);
  return { values, recent: 14, base: 14 };
}

/** 머리 오른쪽 — 다른 표기, 뜻 한 줄, 단계·퍼진 정도·쓸 때 조심·쓰이는 곳, 할 일. growth 는 표지가 없는 머리(대표 자료)에서만 여기 선다 */
function Facts({ e, locale, riskKey, makeHref, growth }: { e: Entry; locale: Locale; riskKey: RiskKey; makeHref: string; growth: number | null }) {
  const p = e.preview;
  return (
    <div className="flex min-w-0 flex-col">
      {p.aliases.length > 0 && (
        <p className="text-[14px] text-[var(--or-slate)]">{tr(locale, "aliases")} <span className="text-[var(--or-ink)]">{p.aliases.map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={scriptLang(a) ?? e.lang}>{a}</span></span>)}</span></p>
      )}
      <p lang={p.textLang} className="mt-3 text-[18px] leading-[1.55] font-medium sm:text-[21px]">{p.definition ?? tr(locale, "no_meaning")}</p>
      {!p.verified && <p className="mt-3 text-[14px] leading-[1.55] text-[var(--or-caution)]">{tr(locale, "draft_notice")}</p>}

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 border-y border-[var(--or-line)] py-5">
        {growth != null && (
          <div className="col-span-2">
            <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "search_trend")}</dt>
            <dd className="mt-1.5 flex items-baseline gap-2"><Growth locale={locale} g={growth} size="md" /><span className="text-[13px] text-[var(--or-slate)]">{tr(locale, "spot_caption_4")}</span></dd>
          </div>
        )}
        <div>
          <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "stage")}</dt>
          <dd className="mt-1.5 text-[16px] font-semibold">{stageWord(locale, e.lifecycle)}</dd>
        </div>
        <div>
          <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "spread")}</dt>
          <dd className={`mt-1.5 text-[16px] font-semibold ${e.diffusion ? "" : "text-[var(--or-slate)]"}`}>{e.diffusion ? spreadWord(locale, e.diffusion) : "–"}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "risk")}</dt>
          <dd className="mt-1.5 flex flex-wrap items-start gap-x-3 gap-y-1.5">
            <RiskMark risk={riskKey} locale={locale} withNone />
            <RiskNotes notes={e.riskNotes} fallback={tr(locale, `risk_${riskKey}_why` as CopyKey)} className="min-w-0 flex-1 basis-[240px] text-[14px] leading-[1.55] text-[var(--or-slate)]" />
          </dd>
        </div>
        {e.regions.length > 0 && (
          <div className="col-span-2">
            <dt className="text-[12px] text-[var(--or-slate)]">{tr(locale, "where")}</dt>
            <dd className="mt-1.5 text-[16px]">{e.regions.map((r) => regionLabel(locale, r)).join(", ")}</dd>
          </div>
        )}
      </dl>

      {/* 데스크톱: 머리 안의 할 일. 휴대폰: 아래에 붙는 막대 */}
      <div className="mt-6 hidden flex-wrap gap-2 lg:flex">
        {e.canMake && <Link href={makeHref} className="inline-flex h-12 items-center justify-center rounded-[6px] bg-[var(--or-ink)] px-6 text-[16px] font-semibold whitespace-nowrap text-white hover:bg-[var(--or-petrol-deep)]">{tr(locale, "make")}</Link>}
        <EntryWatch id={e.id} name={e.name} lang={e.lang} lifecycle={e.lifecycle} risk={riskKey} locale={locale} big />
      </div>
    </div>
  );
}

function HistoryList({ e, locale }: { e: Entry; locale: Locale }) {
  if (!e.history.length) return <p className="text-[16px] text-[var(--or-slate)]">{tr(locale, "no_meaning")}</p>;
  return (
    <ol className="space-y-5">
      {e.history.length === 1 && <li className="text-[16px] text-[var(--or-slate)]">{tr(locale, "history_one", { d: fmtDay(e.history[0].from, locale, e.updatedAt) })}</li>}
      {e.history.length > 1 && e.history.map((h, i) => (
        <li key={`${h.from}-${i}`} className="grid gap-1 sm:grid-cols-[180px_minmax(0,1fr)] sm:gap-6">
          <p className="text-[13px]">
            <span className={`font-semibold ${h.current ? "text-[var(--or-petrol)]" : "text-[var(--or-slate)]"}`}>{tr(locale, h.current ? "history_now" : "history_before")}</span>
            <span className="or-num mt-0.5 block text-[var(--or-slate)]">
              {h.to ? tr(locale, "history_range", { from: fmtDay(h.from, locale, e.updatedAt), to: fmtDay(h.to, locale, e.updatedAt) }) : tr(locale, "history_since", { d: fmtDay(h.from, locale, e.updatedAt) })}
            </span>
          </p>
          <p lang="ko" className={`text-[16px] leading-[1.6] ${h.current ? "" : "text-[var(--or-slate)]"}`}>{h.definition}</p>
        </li>
      ))}
    </ol>
  );
}

export default async function OReportEntry({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const raw = [sp.regions].flat().filter(Boolean)[0] ?? "";
  const regions = parseRegions(raw || undefined);
  const e = await loadEntry(termId, raw ? regions : [], locale);   // 서버가 답하지 않으면 error.tsx
  if (!e) notFound();

  const p = e.preview;
  const backName = !raw ? regionLabel(locale, "KR") : regions.length === 0 ? tr(locale, "region_all") : regions.length === 1 ? regionLabel(locale, regions[0]) : regions.map((r) => regionLabel(locale, r)).slice(0, 2).join(", ");
  const backHref = `/lab/o-report${raw ? `?regions=${encodeURIComponent(raw)}` : ""}`;
  const shape = shapeOf(e);
  const reading = readingOf(e.name, p.aliases, locale);
  const growth = e.trend?.growth4 ?? null;
  const riskKey: RiskKey = e.risk ?? "none";
  const makeHref = `/recommend?term=${encodeURIComponent(e.id)}`;
  const kinds: Record<string, CopyKey> = { wiki: "src_wiki", news: "src_news", video: "src_video" };
  // 표지 낱말 칸의 높이 — 곡선이 있으면 표지의 위 56%, 없으면 거의 전부(읽기 도움 한 줄이 있으면 그만큼 뺀다)
  const avail = `calc(${shape ? "56cqb - 80px" : "100cqb - 96px"}${reading ? " - 32px" : ""})`;

  return (
    <div className="mx-auto max-w-[1320px] px-5 pb-28 sm:px-8 lg:pb-16">
      <p className="pt-6">
        <Link href={backHref} className="inline-flex h-10 items-center gap-1.5 text-[14px] text-[var(--or-slate)] hover:text-[var(--or-ink)]">
          <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden><path d="M10 3.5L5.5 8l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          {tr(locale, "back", { r: backName })}
        </Link>
      </p>

      {/* 머리 — 대표 자료가 있으면 그 그림이 왼쪽에(제목은 오른쪽), 없으면 낱말이 그림인 표지. 오른쪽은 뜻과 판단과 할 일 */}
      {p.media ? (
        <header className="or-hero or-hero-media mt-2 pb-10">
          <div className="or-hero-title min-w-0">
            <h1 lang={e.lang} className="text-[36px] leading-[1.08] font-extrabold tracking-[-0.035em] [overflow-wrap:anywhere] sm:text-[48px]">{e.name}</h1>
            {reading && <p lang={locale === "ko" ? "ko" : undefined} className="mt-2 text-[18px] font-medium text-[var(--or-slate)]">{reading}</p>}
          </div>
          <figure className="or-hero-figure min-w-0">
            {/* 유튜브 썸네일(mqdefault 320×180)은 크게 늘리면 흐려진다 — 480px 까지만. 주소만 쓴다(파일을 받거나 보관하지 않는다) */}
            <a href={p.media.href} target="_blank" rel="noreferrer noopener"
              className={`group relative block overflow-hidden rounded-[4px] bg-[var(--or-mist)] ${p.media.kind === "video" ? "max-w-[480px]" : ""}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.media.src} alt={p.media.title || e.name} className={`w-full ${p.media.kind === "video" ? "aspect-video object-cover" : "max-h-[440px] object-contain"}`} />
              {p.media.kind === "video" && (
                <span className="absolute bottom-3 left-3 inline-flex h-9 items-center gap-2 rounded-[6px] bg-white px-3 text-[14px] font-semibold text-[var(--or-ink)]">
                  <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden><path d="M3 1.8v8.4L10 6z" fill="currentColor" /></svg>{tr(locale, "media_video")}
                </span>
              )}
              <span className="sr-only"> ({tr(locale, "new_tab")})</span>
            </a>
            <figcaption className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-[12px] text-[var(--or-slate)]">
              {p.media.title && <><span>{tr(locale, "media_source")}</span><span lang={scriptLang(p.media.title)} className="break-words text-[var(--or-ink)]">{p.media.title}</span></>}
              {p.media.license && <><span>{tr(locale, "media_license")}</span><span className="text-[var(--or-ink)]">{p.media.license}</span></>}
              {p.media.attribution && <><span>{tr(locale, "media_author")}</span><span className="break-words text-[var(--or-ink)]">{p.media.attribution}</span></>}
            </figcaption>
          </figure>
          <div className="or-hero-facts min-w-0">
            <Facts e={e} locale={locale} riskKey={riskKey} makeHref={makeHref} growth={growth} />
          </div>
        </header>
      ) : (
        <header className="or-hero mt-2 pb-10">
          <div className={`or-cover or-hero-figure ${shape ? "h-[260px] sm:h-[340px] lg:h-auto lg:min-h-[400px]" : "h-[220px] sm:h-[280px] lg:h-auto lg:min-h-[340px]"}`} style={{ "--max": "128px", "--avail": avail, "--pad": "68px" } as React.CSSProperties}>
            {growth != null ? (
              <p className="absolute top-0 right-0 z-[1] flex flex-col items-end gap-1 p-5 text-right">
                <Growth locale={locale} g={growth} size="lg" />
                <span className="text-[12px] text-[var(--or-slate)]">{tr(locale, "spot_caption_4")}</span>
              </p>
            ) : e.lastUsed ? (
              /* 검색 곡선이 없는 밈: 늘어난 정도 대신 실제로 마지막에 쓰인 날 (리포트 표지와 같은 자리·같은 말) */
              <p className="absolute top-0 right-0 z-[1] flex flex-col items-end gap-1 p-5 text-right">
                <span className="or-num text-[21px] leading-none font-bold">{fmtDay(e.lastUsed, locale, e.updatedAt)}</span>
                <span className="text-[12px] text-[var(--or-slate)]">{tr(locale, "last_used")}</span>
              </p>
            ) : null}
            <div className={`absolute inset-x-0 top-[64px] flex flex-col items-start justify-end px-5 pb-3 sm:px-7 ${shape ? "bottom-[44%]" : "bottom-5"}`}>
              <FitName as="h1" name={e.name} lang={e.lang} splitAbove={5} className="or-cover-word" />
              {reading && <p lang={locale === "ko" ? "ko" : undefined} className="mt-2 text-[18px] font-medium text-[var(--or-slate)]">{reading}</p>}
            </div>
            {shape && <div className="or-cover-shape !h-[44%]"><SilhouetteShape shape={shape} /></div>}
          </div>
          <div className="or-hero-facts min-w-0">
            <Facts e={e} locale={locale} riskKey={riskKey} makeHref={makeHref} growth={null} />
          </div>
        </header>
      )}

      {/* 휴대폰의 할 일 막대 — 두 단추가 한 줄에 들어가지 않으면 줄을 바꾼다(글자가 단추 안에서 접히지 않게) */}
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-wrap gap-2 border-t border-[var(--or-line)] bg-white px-5 py-3 lg:hidden">
        {e.canMake && <Link href={makeHref} className="inline-flex h-12 flex-1 items-center justify-center rounded-[6px] bg-[var(--or-ink)] px-4 text-[16px] font-semibold whitespace-nowrap text-white">{tr(locale, "make")}</Link>}
        <EntryWatch id={e.id} name={e.name} lang={e.lang} lifecycle={e.lifecycle} risk={riskKey} locale={locale} big />
      </div>

      <Section id="origin" title={tr(locale, "sec_origin")}>
        {p.origin ? (
          <div className="max-w-[760px]">
            <p lang={p.textLang} className="text-[18px] leading-[1.7]">{p.origin}</p>
            {p.refs.length > 0 && (
              <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
                <span className="text-[var(--or-slate)]">{tr(locale, "origin_from")}</span>
                {p.refs.map((r) => (
                  <a key={r.url} href={r.url} target="_blank" rel="noreferrer noopener" className="inline-flex min-h-8 items-center gap-1.5 text-[var(--or-petrol)] underline-offset-4 hover:underline">
                    <span lang={r.nameLang}>{r.name}</span> <span className="or-num">{fmtDay(r.date, locale, e.updatedAt)}</span><span className="sr-only"> ({tr(locale, "new_tab")})</span>
                  </a>
                ))}
              </p>
            )}
          </div>
        ) : <p className="text-[16px] text-[var(--or-slate)]">{tr(locale, "origin_none")}</p>}
      </Section>

      <Section id="usage" title={tr(locale, "sec_usage")}>
        {p.nuance || p.plain ? (
          <div className="max-w-[760px] space-y-4">
            {p.nuance && <p lang={p.textLang} className="text-[18px] leading-[1.7]">{p.nuance}</p>}
            {p.plain && (
              <p className="flex flex-wrap items-baseline gap-x-3 border-l-[3px] border-[var(--or-petrol)] pl-4">
                <span className="text-[13px] text-[var(--or-slate)]">{tr(locale, "plainly")}</span>
                <span lang={p.textLang} className="text-[21px] font-bold">{p.plain}</span>
              </p>
            )}
          </div>
        ) : <p className="text-[16px] text-[var(--or-slate)]">{tr(locale, "usage_none")}</p>}
      </Section>

      <Section id="trend" title={tr(locale, "sec_trend")}>
        {e.trend ? (
          <div>
            <div className="mb-4 flex flex-wrap items-baseline gap-x-8 gap-y-3">
              {e.trend.growth4 != null && <p className="flex items-baseline gap-2"><Growth locale={locale} g={e.trend.growth4} size="md" /><span className="text-[13px] text-[var(--or-slate)]">{tr(locale, "spot_caption_4")}</span></p>}
              {e.trend.growth12 != null && <p className="flex items-baseline gap-2"><Growth locale={locale} g={e.trend.growth12} size="md" /><span className="text-[13px] text-[var(--or-slate)]">{tr(locale, "spot_caption_12")}</span></p>}
              {e.trend.stale && <p className="text-[13px] text-[var(--or-slate)]">{tr(locale, "trend_stale", { d: fmtDay(e.trend.end, locale) })}</p>}
              {!e.trend.stale && e.trend.growth4 == null && <p className="text-[13px] text-[var(--or-slate)]">{tr(locale, "trend_not_enough")}</p>}
            </div>
            <IndexChart trend={e.trend} locale={locale} />
            <GenGrid trend={e.trend} locale={locale} />
          </div>
        ) : (
          <div className="max-w-[680px]">
            <p className="text-[16px] leading-[1.6] text-[var(--or-slate)]">{tr(locale, "trend_none")}</p>
            <p className="mt-1 text-[14px] text-[var(--or-slate)]">{tr(locale, "trend_none_more")}</p>
          </div>
        )}
      </Section>

      {e.variants.length > 0 && (
        <Section id="variants" title={tr(locale, "sec_variants")}>
          <ul className="divide-y divide-[var(--or-line)] border-y border-[var(--or-line)]">
            {e.variants.map((v) => (
              <li key={v.region} className="grid gap-2 py-4 sm:grid-cols-[120px_minmax(0,1fr)] sm:gap-6">
                <div>
                  <p className="text-[16px] font-bold">{v.regionLabel}</p>
                  <p lang={v.localLang} className="mt-0.5 text-[14px] text-[var(--or-slate)]">{v.local}</p>
                </div>
                <div className="min-w-0">
                  {v.diff && <p lang={v.diffLang} className="text-[16px] leading-[1.65]">{v.diff}</p>}
                  {v.memes.length > 0 && (
                    <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[13px]">
                      <span className="text-[var(--or-slate)]">{tr(locale, "variant_memes")}</span>
                      {v.memes.map((m) => <span key={m.label} lang={m.lang} className="rounded-[3px] bg-[var(--or-mist)] px-2 py-0.5 text-[var(--or-ink)]">{m.label}</span>)}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section id="sources" title={tr(locale, "sec_sources")}>
        {e.sources.length ? (
          <ul className="divide-y divide-[var(--or-line)] border-y border-[var(--or-line)]">
            {e.sources.map((s) => (
              <li key={s.url + s.title}>
                <a href={s.url} target="_blank" rel="noreferrer noopener" className="group grid gap-1 py-3.5 sm:grid-cols-[170px_minmax(0,1fr)_100px] sm:items-baseline sm:gap-6">
                  <span className="text-[13px] text-[var(--or-slate)]"><span lang={s.nameLang}>{s.name}</span> {tr(locale, kinds[s.kind])}</span>
                  <span lang={s.titleLang} className="min-w-0 text-[16px] leading-[1.5] group-hover:underline">{s.title}<span className="sr-only"> ({tr(locale, "new_tab")})</span></span>
                  <span className="or-num text-[13px] text-[var(--or-slate)] sm:text-right">{fmtDay(s.date, locale, e.updatedAt)}</span>
                </a>
              </li>
            ))}
          </ul>
        ) : <p className="text-[16px] text-[var(--or-slate)]">{tr(locale, "sources_none")}</p>}
        {e.communityCount > 0 && <p className="mt-3 text-[13px] text-[var(--or-slate)]">{tr(locale, "sources_community", { n: e.communityCount })}</p>}
      </Section>

      <Section id="history" title={tr(locale, "sec_history")}>
        <div className="max-w-[860px]"><HistoryList e={e} locale={locale} /></div>
      </Section>
    </div>
  );
}
