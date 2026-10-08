import type { Metadata } from "next";
import { MARKETS, isMarket, type Market } from "@/components/lab/r-flow/copy";
import { Make, type Pinned } from "@/components/lab/r-flow/make";
import { getMarketCounts, getSignerName } from "@/components/lab/r-flow/server";
import { getTermRecord, isSampleMode } from "@/lib/data";
import { getLocale } from "@/lib/locale";

/* 시작(만들기) — 입력 상자와, 실행될 진행표를 빈 채로 미리 보인다. 만들기를 누르면 같은 화면에서 시장별 초안으로 펼쳐진다.
   ?regions=KR 는 둘러보기의 '이 시장으로 초안 만들기', ?term= 는 밈 항목의 '이 밈으로 초안 만들기'. */
export const metadata: Metadata = { title: "New draft" };

type SP = Promise<Record<string, string | string[] | undefined>>;

export default async function MakePage({ searchParams }: { searchParams: SP }) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const asked = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase());
  const initial: Market[] = MARKETS.filter((m) => asked.includes(m));
  const termId = [sp.term].flat()[0] ?? "";
  const [counts, signer, record] = await Promise.all([
    getMarketCounts(),
    getSignerName(),
    /^[\w.:-]{1,64}$/.test(termId) ? getTermRecord(termId).catch(() => null) : Promise.resolve(null),
  ]);
  // 고정할 수 있는 밈은 확인된 말 중 쓰지 않을 말이 아닌 것만
  const pinned: Pinned | null = record && record.term.status === "verified" && record.term.risk_level !== "avoid"
    ? { id: record.term.term_id, name: record.term.canonical, lang: record.term.lang ?? "" } : null;
  return (
    <Make key={pinned?.id ?? "none"} locale={locale} counts={counts} initialMarkets={initial.length ? initial : [...MARKETS].filter(isMarket)}
      pinned={pinned} signer={signer} sample={isSampleMode} />
  );
}
