import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import type { KeywordCard } from "@/lib/types";
import { cn } from "@/lib/utils";

/* 시장 하나의 워드 클라우드 (Plan 20). 시장마다 수집량이 달라(미국 280 · 일본 55) 한 판에 모으면 큰 시장 말만 커지므로
   크기는 이 판 안의 순위로만 네 단계: 최근 4주 언급 상위 → 중간 → 그 밖 → 언급 없이 살아 있는 말(회색). 원문은 번역하지 않는다.
   다른 나라에서도 쓰이는 말은 나라 수를 작게 붙이고, 쓰지 말 말은 빨강. 색은 그 둘에만 쓴다. */
const TIERS = ["text-[44px] font-extrabold", "text-[28px] font-bold", "text-[19px] font-semibold", "text-[15px] font-medium text-steel"];

function tier(rank: number, mentioned: number, card: KeywordCard) {
  if (!card.mentions_4w) return 3;
  return rank < Math.max(2, Math.round(mentioned * 0.12)) ? 0 : rank < Math.max(5, Math.round(mentioned * 0.4)) ? 1 : 2;
}

/** 큰 말이 가운데로 모이게 — 순위대로 좌우에 번갈아 놓는다(같은 입력이면 같은 배치). */
function centerOut<T>(xs: T[]): T[] {
  const out: T[] = [];
  xs.forEach((x, i) => (i % 2 ? out.push(x) : out.unshift(x)));
  return out;
}

export function WordCloud({ cards, locale, regions, title }: { cards: KeywordCard[]; locale: Locale; regions: string[]; title: string }) {
  const ranked = [...new Map(cards.map((c) => [c.term_id, c])).values()]
    .sort((a, b) => b.mentions_4w - a.mentions_4w || a.canonical.localeCompare(b.canonical)).slice(0, 40);
  const mentioned = ranked.filter((c) => c.mentions_4w > 0).length;
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  const own = new Set(regions);
  const words = centerOut(ranked.map((c, i) => ({ c, tier: tier(i, mentioned, c), elsewhere: c.regions.filter((r) => !own.has(r)).length })));
  if (!words.length) return null;
  return (
    <section aria-labelledby="cloud-title" className="rubric">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-1">
        <h2 id="cloud-title" className="text-[24px] font-extrabold tracking-[-0.02em] text-ink">{title}</h2>
        <p className="max-w-[560px] text-[14px] text-charcoal">{t(locale, "cloud_note")}</p>
      </div>
      <ul className="mt-6 flex flex-wrap items-baseline justify-center gap-x-6 gap-y-3 py-4 text-center">
        {words.map(({ c, tier: k, elsewhere }) => (
          <li key={c.term_id}>
            <Link href={`/dictionary/${encodeURIComponent(c.term_id)}${q}`}
              className={cn("leading-[1.15] tracking-[-0.03em] hover:underline hover:decoration-2 hover:underline-offset-4", TIERS[k],
                c.risk_level === "avoid" ? "text-avoid" : k < 3 && "text-ink")}>
              <span lang={langTag(c.lang)}>{c.canonical}</span>
              {elsewhere > 0 && <sup className="ml-0.5 text-[11px] font-medium tracking-normal text-link-blue tabular-nums">+{elsewhere}</sup>}
              {c.risk_level === "avoid" && <span className="sr-only"> {t(locale, "risk_avoid")}</span>}
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-2 border-t border-hairline pt-3 text-[13px] text-steel">{t(locale, "cloud_legend")}</p>
    </section>
  );
}
