"use client";

import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";

/* 챗봇 답에 붙는 화면 조각. 백엔드 도구가 찾은 것을 그대로 그린다 (pipeline/tools.py 의 ctx.card).
   글로만 답하면 목록과 비중이 눈에 안 들어와서, 표제어·목록·세대 비중을 각각 다르게 그린다.
   그림은 위키미디어 공용의 자유 라이선스만 오고(출처를 함께 적는다), 영상은 유튜브 공식 플레이어로 끼운다. */

export type MediaItem = { kind: string; url: string; page_url: string; title: string; license: string; attribution: string };
export type ChatCard =
  | { type: "term"; term_id: string; canonical: string; definition: string; origin: string; status: string;
      lifecycle: string; category: string; evidence_count: number; media: MediaItem[] }
  | { type: "list"; title: string; items: Array<{ term_id: string; canonical: string; definition: string; origin?: string; lifecycle: string; status: string }> }
  | { type: "usage"; term: string; term_id: string; bars: Array<{ label: string; ratio: number }>;
      regions: string[]; weekly: Array<{ week: string; count: number }> }
  | { type: "live"; term: string; summary: string; seconds: number;
      sources: Array<{ domain: string; url: string; title: string }> };

function youtubeId(url: string): string | null {
  const m = /(?:v=|shorts\/|youtu\.be\/)([A-Za-z0-9_-]{6,20})/.exec(url);
  return m ? m[1] : null;
}

export function ChatCards({ cards, locale }: { cards: ChatCard[]; locale: Locale }) {
  if (!cards?.length) return null;
  return (
    <div className="space-y-3">
      {cards.map((card, i) => {
        if (card.type === "term") {
          const image = card.media.find((m) => m.kind === "image");
          const video = card.media.find((m) => m.kind === "video");
          const vid = video ? youtubeId(video.url) : null;
          return (
            <div key={i} className="rounded-lg border border-hairline bg-white p-3">
              <div className="flex items-start gap-3">
                {image && (
                  /* 자유 라이선스 그림만 온다. next/image 로 감싸지 않는 것은 위키미디어 도메인을 설정에 열지 않기 위해서다. */
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={image.url} alt={card.canonical} className="h-20 w-20 shrink-0 rounded border border-hairline object-cover" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <Link href={`/dictionary/${card.term_id}`} className="text-[16px] font-medium text-ink hover:underline">{card.canonical}</Link>
                    {/* 상태·생애주기 칩은 뺐다 — 화면에 닿는 표제어는 전부 확인된 것이라 구별력이 없었다. */}
                  </div>
                  {card.definition && <p className="mt-1 text-[15px] leading-[1.6] text-ink">{card.definition}</p>}
                  {card.origin && <p className="mt-1 text-[13px] leading-[1.6] text-charcoal">{card.origin}</p>}
                  <p className="mt-1 text-[12px] text-steel">
                    {t(locale, "card_evidence")} {card.evidence_count}
                    {image && (
                      <>
                        {" · "}
                        <a href={image.page_url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
                          {t(locale, "card_media_src")} ({image.license})
                        </a>
                      </>
                    )}
                  </p>
                </div>
              </div>
              {vid && (
                <div className="mt-3">
                  <p className="mb-1 text-[12px] text-steel">{t(locale, "card_video")}</p>
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
          /* 사전에 없어서 그 자리에서 찾아본 것. 검증된 항목과 섞이면 안 되므로 테두리를 점선으로 두고
             '아직 확인 전'을 먼저 적는다. 읽은 곳을 그대로 보여 준다. */
          return (
            <div key={i} className="rounded-lg border border-dashed border-hairline-strong bg-white p-3">
              <p className="text-[12px] text-steel">
                {t(locale, "live_label")} · {card.seconds}s
              </p>
              <p className="mt-1 text-[15px] leading-[1.6] text-ink">{card.summary}</p>
              <p className="mt-2 text-[12px] text-steel">{t(locale, "live_read")}</p>
              <ul className="mt-1 space-y-0.5">
                {card.sources.map((s2, k) => (
                  <li key={k} className="text-[12px] leading-[1.5]">
                    <a href={s2.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
                      {s2.domain}
                    </a>
                    <span className="text-charcoal"> — {s2.title}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[12px] text-steel">{t(locale, "live_queued")}</p>
            </div>
          );
        }
        if (card.type === "list") {
          return (
            <div key={i} className="overflow-x-auto rounded-lg border border-hairline bg-white">
              <p className="border-b border-hairline px-3 py-2 text-[13px] text-charcoal">{card.title}</p>
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="text-[12px] text-steel">
                    <th className="px-3 py-1.5 font-normal">{t(locale, "card_term")}</th>
                    <th className="px-3 py-1.5 font-normal">{t(locale, "card_meaning")}</th>
                    {card.items.some((i) => i.origin) && (
                      <th className="px-3 py-1.5 font-normal">{t(locale, "card_why")}</th>
                    )}
                    {/* 열두 줄이 모두 '잠잠함' 이면 칸을 두는 의미가 없다 */}
                    {new Set(card.items.map((i) => i.lifecycle)).size >= 3 && (
                      <th className="px-3 py-1.5 font-normal">{t(locale, "card_stage")}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {card.items.map((it) => (
                    <tr key={it.term_id} className="border-t border-hairline align-top">
                      <td className="whitespace-nowrap px-3 py-1.5 text-[14px]">
                        <Link href={`/dictionary/${it.term_id}`} className="text-ink hover:underline">{it.canonical}</Link>
                      </td>
                      <td className="px-3 py-1.5 text-[14px] leading-[1.5] text-charcoal">{it.definition}</td>
                      {card.items.some((i) => i.origin) && (
                        <td className="px-3 py-1.5 text-[13px] leading-[1.5] text-charcoal">
                          {it.origin ? `${it.origin}${it.origin.length >= 118 ? "…" : ""}` : "—"}
                        </td>
                      )}
                      {new Set(card.items.map((i) => i.lifecycle)).size >= 3 && (
                        <td className="whitespace-nowrap px-3 py-1.5 text-[12px] text-steel">{it.lifecycle}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        const peak = Math.max(1, ...card.weekly.map((w) => w.count));
        return (
          <div key={i} className="rounded-lg border border-hairline bg-white p-3">
            <p className="text-[14px] text-ink">{card.term}</p>
            <p className="mt-2 text-[12px] text-steel">{t(locale, "card_who")}</p>
            <div className="mt-1 space-y-1">
              {card.bars.map((b) => (
                <div key={b.label} className="flex items-center gap-2">
                  <span className="w-12 shrink-0 text-[13px] text-charcoal">{b.label}</span>
                  <span className="h-2 flex-1 rounded-sm bg-surface">
                    <span className="block h-2 rounded-sm bg-ink" style={{ width: `${Math.round(b.ratio * 100)}%` }} />
                  </span>
                  <span className="w-10 shrink-0 text-right text-[12px] text-steel">{Math.round(b.ratio * 100)}%</span>
                </div>
              ))}
            </div>
            {card.regions.length > 0 && (
              <p className="mt-2 text-[12px] text-steel">{t(locale, "card_where")} · {card.regions.join(", ")}</p>
            )}
            {card.weekly.length > 1 && (
              <div className="mt-2 flex h-8 items-end gap-1" aria-hidden>
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
