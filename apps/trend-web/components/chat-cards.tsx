"use client";

import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import type { Diffusion, Lifecycle, RiskLevel } from "@/lib/contract/types";
import { t, type Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";

/* 질문 답에 붙는 화면 조각. 백엔드 도구가 찾은 것을 그대로 그린다 (pipeline/tools.py 의 ctx.card).
   글로만 답하면 목록과 비중이 눈에 안 들어와서, 표제어·목록·세대 비중을 각각 다르게 그린다.
   단계·쓸 때 조심은 코드(lifecycle_code·diffusion·risk_level)가 오면 해석 결과·대시보드와 같은 말로 그린다 —
   백엔드의 한국어 이름('꾸준함')을 그대로 내면 같은 단계에 이름이 넷이 되고 영어 화면에 한국어가 나왔다(2026-09-29 검토).
   그림은 위키미디어 공용의 자유 라이선스만 오고(출처를 함께 적는다), 영상은 유튜브 공식 플레이어로 끼운다. */

export type MediaItem = { kind: string; url: string; page_url: string; title: string; license: string; attribution: string };
type Status = { lifecycle_code?: Lifecycle; diffusion?: Diffusion | null; risk_level?: RiskLevel | null; risk_checked_at?: string | null; lang?: string };
export type ChatCard =
  | ({ type: "term"; term_id: string; canonical: string; definition: string; origin: string; status: string;
      lifecycle: string; category: string; evidence_count: number; media: MediaItem[] } & Status)
  | { type: "list"; title: string; items: Array<{ term_id: string; canonical: string; definition: string; origin?: string; lifecycle: string; status: string } & Status> }
  | { type: "usage"; term: string; term_id: string; bars: Array<{ label: string; ratio: number }>;
      regions: string[]; weekly: Array<{ week: string; count: number }> }
  | { type: "live"; term: string; summary: string; seconds: number;
      sources: Array<{ domain: string; url: string; title: string }> };

function youtubeId(url: string): string | null {
  const m = /(?:v=|shorts\/|youtu\.be\/)([A-Za-z0-9_-]{6,20})/.exec(url);
  return m ? m[1] : null;
}

const headLang = (c: { canonical: string; lang?: string }) => (c.lang ? langTag(c.lang) : scriptLang(c.canonical));
const hasRisk = (c: Status) => c.risk_level !== undefined || c.risk_checked_at !== undefined;

function Stage({ c, locale }: { c: Status & { lifecycle: string }; locale: Locale }) {
  // 코드가 없는 예전 응답은 화면 언어가 한국어일 때만 백엔드 이름을 그대로 보인다
  if (c.lifecycle_code) return <StageCell diffusion={c.diffusion} lifecycle={c.lifecycle_code} locale={locale} />;
  return <span className="text-[13px] text-charcoal">{locale === "ko" ? c.lifecycle : "—"}</span>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-x-4 py-1 sm:grid-cols-[112px_minmax(0,1fr)]">
      <dt className="text-[13px] leading-[1.55] font-medium text-steel">{label}</dt>
      <dd className="min-w-0 text-[14px] leading-[1.55] text-charcoal">{children}</dd>
    </div>
  );
}

export function ChatCards({ cards, locale }: { cards: ChatCard[]; locale: Locale }) {
  if (!cards?.length) return null;
  return (
    <div className="space-y-5">
      {cards.map((card, i) => {
        if (card.type === "term") {
          const image = card.media.find((m) => m.kind === "image");
          const video = card.media.find((m) => m.kind === "video");
          const vid = video ? youtubeId(video.url) : null;
          return (
            <div key={i} className="border-t border-hairline pt-4">
              <div className="flex items-start gap-4">
                <div className="min-w-0 flex-1">
                  <h3 className="text-[16px] font-semibold text-ink">
                    <Link href={`/dictionary/${card.term_id}`} lang={headLang(card)} className="hover:underline">{card.canonical}</Link>
                  </h3>
                  {card.definition && <p className="mt-1.5 text-[15px] leading-[1.6] text-ink">{card.definition}</p>}
                </div>
                {image && (
                  /* 자유 라이선스 그림만 온다. next/image 로 감싸지 않는 것은 위키미디어 도메인을 설정에 열지 않기 위해서다. */
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={image.url} alt={card.canonical} className="h-20 w-20 shrink-0 rounded border border-hairline object-cover" />
                )}
              </div>
              <dl className="mt-2">
                <Row label={t(locale, "dash_col_stage")}><Stage c={card} locale={locale} /></Row>
                {hasRisk(card) && <Row label={t(locale, "dash_col_risk")}><RiskCell item={card} locale={locale} /></Row>}
                {card.origin && <Row label={t(locale, "term_origin")}>{card.origin}</Row>}
                {card.evidence_count > 0 && (
                  <Row label={t(locale, "pg_ex_sources")}>
                    <Link href={`/dictionary/${card.term_id}#refs`} className="text-link-blue hover:underline">
                      {t(locale, "pg_ex_all_sources").replace("{n}", String(card.evidence_count))}
                    </Link>
                  </Row>
                )}
                {image && (
                  <Row label={t(locale, "card_media_src")}>
                    <a href={image.page_url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">{image.license}</a>
                  </Row>
                )}
              </dl>
              {vid && (
                <div className="mt-3">
                  <p className="mb-1 text-[13px] text-steel">{t(locale, "card_video")}</p>
                  <div className="aspect-video w-full max-w-[320px] overflow-hidden rounded border border-hairline">
                    <iframe
                      src={`https://www.youtube-nocookie.com/embed/${vid}`}
                      title={video?.title || card.canonical}
                      allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
                      allowFullScreen
                      className="h-full w-full"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        }
        if (card.type === "live") {
          /* 사전에 없어서 그 자리에서 찾아본 것. 확인된 항목과 섞이면 안 되므로 테두리를 점선으로 두고
             '확인 전' 을 먼저 적는다. 읽은 곳을 그대로 보여 준다. */
          return (
            <div key={i} className="rounded-lg border border-dashed border-hairline-strong p-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge tone="muted">{t(locale, "risk_not_checked")}</StatusBadge>
                <span className="text-[13px] text-steel">{t(locale, "live_label")}</span>
              </div>
              <p className="mt-2 text-[15px] leading-[1.6] text-ink">{card.summary}</p>
              <p className="mt-3 text-[13px] text-steel">{t(locale, "live_read")}</p>
              <ul className="mt-1 space-y-1">
                {card.sources.map((s2, k) => (
                  <li key={k} className="text-[13px] leading-[1.5]">
                    <a href={s2.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">{s2.domain}</a>
                    <span className="block text-charcoal">{s2.title}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[13px] text-steel">{t(locale, "live_queued")}</p>
            </div>
          );
        }
        if (card.type === "list") {
          const withRisk = card.items.some(hasRisk);
          return (
            <div key={i}>
              <p className="border-b border-hairline pb-2 text-[14px] font-medium text-ink">{card.title}</p>
              <table className="hidden w-full border-collapse text-left md:table">
                <caption className="sr-only">{card.title}</caption>
                <thead>
                  <tr className="border-b border-hairline text-[13px] text-steel">
                    <th scope="col" className="py-2 pr-4 font-medium">{t(locale, "dash_col_keyword")}</th>
                    <th scope="col" className="py-2 pr-4 font-medium">{t(locale, "card_meaning")}</th>
                    <th scope="col" className="w-[170px] py-2 pr-4 font-medium">{t(locale, "dash_col_stage")}</th>
                    {withRisk && <th scope="col" className="w-[120px] py-2 font-medium">{t(locale, "dash_col_risk")}</th>}
                  </tr>
                </thead>
                <tbody>
                  {card.items.map((it) => (
                    <tr key={it.term_id} className="border-b border-hairline align-top">
                      <th scope="row" className="py-2.5 pr-4 text-left text-[14px] font-semibold">
                        <Link href={`/dictionary/${it.term_id}`} lang={headLang(it)} className="text-ink hover:underline">{it.canonical}</Link>
                      </th>
                      <td className="py-2.5 pr-4 text-[14px] leading-[1.5] text-charcoal">{it.definition}</td>
                      <td className="py-2.5 pr-4"><Stage c={it} locale={locale} /></td>
                      {withRisk && <td className="py-2.5"><RiskCell item={it} locale={locale} /></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
              <ul className="divide-y divide-hairline md:hidden">
                {card.items.map((it) => (
                  <li key={it.term_id} className="py-3">
                    <div className="flex items-start justify-between gap-3">
                      <Link href={`/dictionary/${it.term_id}`} lang={headLang(it)} className="min-w-0 text-[15px] font-semibold text-ink hover:underline">{it.canonical}</Link>
                      {hasRisk(it) && <RiskCell item={it} locale={locale} />}
                    </div>
                    {it.definition && <p className="mt-1 text-[14px] leading-[1.5] text-charcoal">{it.definition}</p>}
                    <div className="mt-1.5"><Stage c={it} locale={locale} /></div>
                  </li>
                ))}
              </ul>
            </div>
          );
        }
        const peak = Math.max(1, ...card.weekly.map((w) => w.count));
        return (
          <div key={i} className="border-t border-hairline pt-4">
            <h3 className="text-[16px] font-semibold text-ink">
              <Link href={`/dictionary/${card.term_id}`} lang={scriptLang(card.term)} className="hover:underline">{card.term}</Link>
            </h3>
            <p className="mt-2 text-[13px] font-medium text-steel">{t(locale, "card_who")}</p>
            <div className="mt-1 max-w-[480px] space-y-1">
              {card.bars.map((b) => (
                <div key={b.label} className="flex items-center gap-2">
                  <span className="w-16 shrink-0 text-[13px] text-charcoal">{b.label}</span>
                  <span className="h-2 flex-1 rounded-sm bg-surface">
                    <span className="block h-2 rounded-sm bg-ink" style={{ width: `${Math.round(b.ratio * 100)}%` }} />
                  </span>
                  <span className="w-10 shrink-0 text-right text-[13px] tabular-nums text-steel">{Math.round(b.ratio * 100)}%</span>
                </div>
              ))}
            </div>
            {card.regions.length > 0 && (
              <dl className="mt-2"><Row label={t(locale, "card_where")}>{card.regions.join(", ")}</Row></dl>
            )}
            {card.weekly.length > 1 && (
              <div role="img" className="mt-2 flex h-8 items-end gap-1"
                aria-label={t(locale, "spark_label").replace("{n}", String(card.weekly.length)).replace("{last}", String(card.weekly.at(-1)?.count ?? 0)).replace("{max}", String(peak))}>
                {card.weekly.map((w) => (
                  <span key={w.week} className="w-3 rounded-sm bg-ink" style={{ height: `${Math.max(6, (w.count / peak) * 100)}%` }} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
