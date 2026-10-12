import type { Metadata } from "next";
import Link from "next/link";
import { RiskMark } from "@/components/lab/o-report/bits";
import { matchScore, normQuery } from "@/lib/lab/o-report";
import { stageWord, tr } from "@/lib/lab/o-report/copy";
import { loadSearchIndex } from "@/lib/lab/o-report/data";
import { getLabLocale as getLocale } from "@/lib/locale";

/* 초안 1의 사전 — 위 막대의 '사전' 과 찾기 칸의 '결과 모두 보기' 가 여기로 온다(09-29 검토: 앱의 예전 사전 화면으로 넘어갔다).
   찾는 말이 없으면 확인된 밈 전부를 이름순으로. 맞추는 규칙은 찾기 칸과 같다. 스크립트 없이도 폼으로 찾는다. */

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata(): Promise<Metadata> {
  return { title: tr(await getLocale(), "dict_title") };
}

export default async function OReportDictionary({ searchParams }: { searchParams: Promise<Search> }) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const q = ([sp.q].flat()[0] ?? "").trim().slice(0, 60);
  const items = await loadSearchIndex(locale);
  const n = normQuery(q);
  const list = !items ? [] : n
    ? items.map((it) => ({ it, s: matchScore(it, n) })).filter((x) => x.s < 99).sort((a, b) => a.s - b.s || a.it.name.length - b.it.name.length).map((x) => x.it)
    : [...items].sort((a, b) => a.name.localeCompare(b.name, locale));
  const lead = !items ? tr(locale, "dict_failed")
    : !q ? tr(locale, "dict_count", { n: items.length })
      : list.length ? tr(locale, "dict_results", { q, n: list.length }) : tr(locale, "dict_none", { q });

  return (
    <div className="mx-auto max-w-[1320px] px-5 pb-20 sm:px-8">
      <section className="grid grid-cols-1 gap-6 pt-8 pb-8 sm:pt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:items-end">
        <div className="min-w-0">
          <h1 className="or-headline">{tr(locale, "dict_title")}</h1>
          <p className="mt-4 max-w-[640px] text-[16px] leading-[1.6] text-[var(--or-slate)] sm:text-[18px]" role={q ? "status" : undefined}>{lead}</p>
        </div>
        <form action="/lab/o-report/search" method="get" role="search" className="flex gap-2">
          <label htmlFor="or-dict-q" className="sr-only">{tr(locale, "search_label")}</label>
          <input id="or-dict-q" name="q" type="search" defaultValue={q} placeholder={tr(locale, "search_placeholder")}
            className="h-12 min-w-0 flex-1 appearance-none rounded-[6px] border border-[var(--or-edge)] bg-white px-3 text-[16px] text-[var(--or-ink)] placeholder:text-[var(--or-slate)] hover:border-[var(--or-slate)] focus:border-[var(--or-petrol)] focus-visible:outline-offset-0 [&::-webkit-search-cancel-button]:hidden" />
          <button type="submit" className="h-12 shrink-0 rounded-[6px] bg-[var(--or-ink)] px-5 text-[16px] font-semibold text-white hover:bg-[var(--or-petrol-deep)]">{tr(locale, "dict_submit")}</button>
        </form>
      </section>

      {list.length > 0 && (
        <ul className="border-t border-[var(--or-ink)]">
          {list.map((it) => (
            <li key={it.id} className="or-row">
              <Link href={`/lab/o-report/m/${encodeURIComponent(it.id)}`} className="or-row-link grid gap-x-6 gap-y-1 py-3.5 pr-1 pl-3 sm:grid-cols-[minmax(0,1fr)_132px] sm:items-center">
                <span className="min-w-0">
                  <span className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span lang={it.lang} className="or-row-name text-[16px] leading-[1.35] font-bold">{it.name}</span>
                    <RiskMark risk={it.risk === "caution" || it.risk === "avoid" ? it.risk : null} locale={locale} />
                  </span>
                  {it.gloss && <span lang={it.glossLang} className="or-clamp-1 mt-1 text-[14px] leading-[1.45] text-[var(--or-slate)]">{it.gloss}</span>}
                </span>
                <span className="text-[13px] text-[var(--or-slate)]">{stageWord(locale, it.lifecycle)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {q && items && list.length === 0 && (
        <p className="pt-2"><Link href="/lab/o-report" className="inline-flex h-11 items-center rounded-[6px] border border-[var(--or-ink)] px-4 text-[14px] font-semibold hover:bg-[var(--or-ink)] hover:text-white">{tr(locale, "dict_to_report")}</Link></p>
      )}
    </div>
  );
}
