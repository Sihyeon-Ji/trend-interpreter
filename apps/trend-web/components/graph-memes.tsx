import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import type { GraphMeme, GraphVariant } from "@/lib/types";

/* 콘텐츠에서 나온 밈 — 나라를 건너간 밈은 나라별 이름을 나란히(관계표), 한 나라에서만 보인 밈은 나라 칸에 한 줄씩.
   근거는 그 밈을 적은 위키 문서로만 잇는다(본문은 옮기지 않는다). */

export const regionName = (locale: Locale, r: string) => (r === "GLOBAL" ? t(locale, "graph_global") : regionLabel(locale, r));

const REGION_LANG: Record<string, string> = { KR: "ko", JP: "ja", TW: "zh-Hant", HK: "zh-Hant", CN: "zh", TH: "th", ID: "id", VN: "vi", PH: "tl", US: "en", GLOBAL: "en" };

function site(url: string): string {
  const h = (() => { try { return new URL(url).hostname; } catch { return ""; } })();
  if (h === "namu.wiki") return "나무위키";
  if (h.endsWith("knowyourmeme.com")) return "Know Your Meme";
  if (h.endsWith("wikipedia.org")) return `Wikipedia (${h.split(".")[0]})`;
  return h;
}

function Source({ v, locale }: { v: GraphVariant; locale: Locale }) {
  if (!v.evidence_url) return null;
  return (
    <a href={v.evidence_url} target="_blank" rel="noopener noreferrer" className="text-[12px] text-link-blue hover:underline">
      {site(v.evidence_url)} <span aria-hidden>↗</span><span className="sr-only"> ({t(locale, "graph_external")})</span>
    </a>
  );
}

function Name({ v, className }: { v: GraphVariant; className: string }) {
  const lang = REGION_LANG[v.region];
  return v.term_id
    ? <Link href={`/dictionary/${encodeURIComponent(v.term_id)}`} lang={lang} className={`${className} hover:underline`}>{v.name}</Link>
    : <span lang={lang} className={className}>{v.name}</span>;
}

/** 관계표 — 줄은 밈(같은 장면·대사), 칸은 나라. 그 나라 이름이 없으면 빈 칸. */
export function CrossTable({ memes, regions, locale }: { memes: GraphMeme[]; regions: string[]; locale: Locale }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ink text-[12px] text-steel">
            <th scope="col" className="py-2 pr-4 font-normal">{t(locale, "graph_meme_col")}</th>
            {regions.map((r) => <th key={r} scope="col" className="py-2 pr-4 font-normal">{regionName(locale, r)}</th>)}
          </tr>
        </thead>
        <tbody>
          {memes.map((m, i) => (
            <tr key={i} className="border-b border-hairline align-top">
              <td className="max-w-[260px] py-3 pr-4 text-[13px] leading-[1.55] text-charcoal">{m.same_scene || m.variants[0].description}</td>
              {regions.map((r) => {
                const vs = m.variants.filter((v) => v.region === r);
                return (
                  <td key={r} className="py-3 pr-4">
                    {vs.map((v) => (
                      <div key={v.name} className="space-y-0.5">
                        <Name v={v} className="block text-[15px] font-medium text-ink" />
                        <Source v={v} locale={locale} />
                      </div>
                    ))}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 한 나라 칸 — 밈 이름, 한 줄 뜻, 근거 문서. */
export function RegionList({ region, memes, locale, mine }: { region: string; memes: GraphVariant[]; locale: Locale; mine: boolean }) {
  const id = `region-${region}`;
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-6 space-y-2">
      <h2 id={`${id}-h`} className="flex flex-wrap items-baseline gap-x-3 border-b border-ink pb-2 text-[18px] font-semibold text-ink">
        {t(locale, "graph_in_region").replace("{region}", regionName(locale, region))}
        <span className="text-[13px] font-normal tabular-nums text-steel">{memes.length}</span>
        {mine && <span className="rounded-md border border-hairline-strong px-1.5 text-[12px] font-normal text-charcoal">{t(locale, "graph_my_country")}</span>}
      </h2>
      <ul>
        {memes.map((v) => (
          <li key={v.name} className="grid gap-x-6 gap-y-0.5 border-b border-hairline py-2.5 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto]">
            <Name v={v} className="text-[15px] font-medium text-ink" />
            <p className="text-[14px] leading-[1.55] text-charcoal">{v.description}</p>
            <div className="sm:text-right"><Source v={v} locale={locale} /></div>
          </li>
        ))}
      </ul>
    </section>
  );
}
