import Link from "next/link";
import { RiskCell, StageCell } from "@/components/term-status";
import { glossFor } from "@/lib/gloss";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import type { KeywordCard } from "@/lib/types";

/* 포스터 격자 (시안 o-editorial): 밈 이름이 곧 그림. 칸마다 위에 가는 먹 선, 이름은 칸 폭에 맞춘 세 단계 크기, 뜻 두 줄, 아래에 단계·조심.
   카드·그림자·색 면은 쓰지 않는다. 적고 중요한 것(지금 쓰이는 밈 앞 여덟)에만 쓰고, 나머지는 표로 본다. */
function size(name: string) {
  const w = [...name].reduce((n, ch) => n + (/[ᄀ-ᇿ぀-ヿ㐀-鿿가-힯]/.test(ch) ? 1 : ch === " " ? 0.3 : 0.56), 0);
  return w <= 5 ? "text-[40px]" : w <= 9 ? "text-[30px]" : "text-[24px]";
}

export function PosterGrid({ cards, locale, regions }: { cards: KeywordCard[]; locale: Locale; regions: string[] }) {
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  return (
    <ul className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <li key={c.term_id} className="flex min-w-0 flex-col border-t border-ink pt-4">
          <Link href={`/dictionary/${encodeURIComponent(c.term_id)}${q}`} className="group">
            <span lang={langTag(c.lang)} className={`poster-word block group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4 ${size(c.canonical)}`}>{c.canonical}</span>
          </Link>
          <p className="mt-3 line-clamp-2 text-[14px] leading-[1.6] text-charcoal">{glossFor(c, locale)}</p>
          <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 pt-4">
            <StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} />
            {c.risk_level && c.risk_level !== "none" && <RiskCell item={c} locale={locale} />}
          </div>
        </li>
      ))}
    </ul>
  );
}
