import type { Metadata } from "next";
import Link from "next/link";
import { ViewTransition } from "react";
import { isMarket, marketName, num, tr, type Market } from "@/components/lab/r-flow/copy";
import { ExploreTable } from "@/components/lab/r-flow/explore-table";
import { getMarketCounts } from "@/components/lab/r-flow/server";
import { getKeywordBoard } from "@/lib/data";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { KeywordBoard, KeywordList } from "@/lib/types";

/* 둘러보기 — 시장 하나씩, 목록 셋(뜨는 중·식는 중·조심, 대시보드 규칙 그대로). 시장·목록·쪽은 주소에만 둔다(?m=&l=&p=).
   시장을 바꾸면 표가 그 방향으로 짧게 미끄러지며 바뀌고(같은 자리, 다른 내용), 고른 표시는 새 자리로 옮겨 간다(View Transitions). */
export const metadata: Metadata = { title: "Explore" };

const BASE = "/lab/r-flow";
const LISTS: KeywordList[] = ["rising", "fading", "caution"];
const LIST_KEY = { rising: ["ex_rising", "ex_rising_note"], fading: ["ex_fading_list", "ex_fading_note"], caution: ["ex_caution", "ex_caution_note"] } as const;

type SP = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => [v].flat()[0];

export default async function Explore({ searchParams }: { searchParams: SP }) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const m: Market = isMarket(one(sp.m)) ? (one(sp.m) as Market) : "KR";
  const l: KeywordList = LISTS.includes(one(sp.l) as KeywordList) ? (one(sp.l) as KeywordList) : "rising";
  const p = Math.max(1, Number.parseInt(one(sp.p) ?? "", 10) || 1);
  const href = (mm: Market, ll: KeywordList = "rising", pp = 1) => `${BASE}/explore?m=${mm}${ll !== "rising" ? `&l=${ll}` : ""}${pp > 1 ? `&p=${pp}` : ""}`;

  let board: KeywordBoard | null = null;
  try {
    board = await getKeywordBoard([m], p);
  } catch {
    board = null;
  }
  const counts = (await getMarketCounts()) ?? board?.counts ?? {};
  const name = marketName(locale, m);
  const rows = board ? board[l] : [];
  const total = board?.totals[l] ?? 0;
  const pages = Math.max(1, Math.ceil(total / (board?.page_size ?? 30)));
  const verified = counts[m] ?? board?.counts[m] ?? 0;

  return (
    <>
      <ViewTransition key={`${m}-${l}-${p}`} name="rf-list" share={{ "rf-right": "rf-swap-r", "rf-left": "rf-swap-l", default: "rf-swap-f" }} default="none">
        <div>
          <nav className="rf-lists" aria-label={tr(locale, "ex_lists")}>
            {LISTS.map((ll) => (
              <Link key={ll} href={href(m, ll)} aria-current={ll === l ? "page" : undefined} scroll={false} transitionTypes={["rf-same"]}>
                {tr(locale, LIST_KEY[ll][0])}<small>{board ? num(board.totals[ll]) : ""}</small>
                {ll === l && <span className="rf-lists-thumb" aria-hidden="true" />}
              </Link>
            ))}
          </nav>
          <p className="rf-list-note">
            <span>{tr(locale, LIST_KEY[l][1])}</span>
            <span>{name}, {tr(locale, "ex_verified", { n: num(verified) })}{board ? `. ${tr(locale, "ex_updated", { at: fmtDateTime(board.collected_at ?? board.generated_at, locale) })}` : ""}</span>
          </p>
          {verified > 0 && verified < 50 && <p className="rf-notice">{tr(locale, "ex_thin", { market: name })}</p>}
          {!board ? (
            <div className="rf-banner" data-tone="error" role="alert">
              {tr(locale, "ex_error")} <Link className="rf-link" href={href(m, l, p)}>{tr(locale, "ex_retry")}</Link>
            </div>
          ) : rows.length ? (
            <ExploreTable rows={rows} market={m} locale={locale} caption={`${name}, ${tr(locale, LIST_KEY[l][0])}`} />
          ) : (
            <p className="rf-empty">{tr(locale, "ex_empty")}</p>
          )}
          {board && pages > 1 && (
            <div className="rf-pager">
              {p > 1 && <Link className="rf-btn" data-kind="line" data-size="s" href={href(m, l, p - 1)} transitionTypes={["rf-left"]}>{tr(locale, "ex_prev")}</Link>}
              <span className="rf-num">{tr(locale, "ex_page", { p, n: pages })}</span>
              {p < pages && <Link className="rf-btn" data-kind="line" data-size="s" href={href(m, l, p + 1)} transitionTypes={["rf-right"]}>{tr(locale, "ex_next")}</Link>}
            </div>
          )}
        </div>
      </ViewTransition>
    </>
  );
}
