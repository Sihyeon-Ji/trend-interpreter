"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { currentMeaning, textFor } from "@/lib/explain";
import { groupByInitial } from "@/lib/dictionary/index";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, joinGens, regionLabel, termLangLabel } from "@/lib/labels";
import type { Generation, TermRecord } from "@/lib/types";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

const GENS: Generation[] = ["10s", "20s", "30s", "40s", "50s+"];
const control = "h-10 rounded-md border border-hairline-strong bg-white px-3 text-[14px] text-ink focus:border-ink focus:outline-none";

/* 사전 색인: 도구 줄(검색·필터·분류) → 최근 바뀐 표현 → 첫 글자 색인과 목록. 앱 틀에 왼쪽 메뉴가 있어 필터 칸을 따로 두지 않는다. */
export function DictionaryList({ records, locale, readerGen = null, updatedAt = null }: { records: TermRecord[]; locale: Locale; readerGen?: string | null; updatedAt?: string | null }) {
  const [myGenFirst, setMyGenFirst] = useState(!!readerGen);
  const [gen, setGen] = useState<Generation | "">("");
  const [region, setRegion] = useState("");
  const [q, setQ] = useState("");
  const [lang, setLang] = useState("");
  const [category, setCategory] = useState("");
  const labels = L(locale);
  const regions = useMemo(() => Array.from(new Set(records.flatMap((r) => currentMeaning(r)?.regions ?? []))).sort(), [records]);
  const langs = useMemo(() => Array.from(new Set(records.map((r) => r.term.lang ?? "ko"))), [records]);
  const categories = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of records) m.set(r.category, (m.get(r.category) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [records]);
  const recent = useMemo(
    () => [...records].map((r) => ({ r, at: r.meanings.at(-1)?.valid_from ?? "" })).filter((x) => x.at).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 8),
    [records],
  );
  const pendingCount = records.filter((r) => r.term.status === "needs_review").length;

  const shown = records.filter((r) => {
    const m = currentMeaning(r);
    const tx = textFor(r, locale);
    if (category && r.category !== category) return false;
    if (lang && (r.term.lang ?? "ko") !== lang) return false;
    if (gen && !(m?.generations.includes(gen) || m?.generations.includes("all"))) return false;
    if (region && !m?.regions.includes(region)) return false;
    if (q) {
      const hay = [r.term.canonical, ...(r.term.aliases ?? []), tx?.definition ?? "", tx?.expansion ?? "", m?.definition ?? ""].join(" ").toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  });
  const unfamiliar = (r: TermRecord) => {
    if (!myGenFirst || !readerGen) return false;
    const gens = currentMeaning(r)?.generations ?? [];
    return !!gens.length && !gens.includes("all") && !gens.includes(readerGen as never);
  };
  const groups = groupByInitial(shown, locale);
  const pill = chipClass;

  return (
    <div className="space-y-5">
      {/* 도구 줄: 검색 + 필터 한 줄. 좁은 화면에서는 줄을 바꿔 쌓는다(두 벌을 그리지 않는다) */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="dict-search" className="sr-only">{t(locale, "dict_search")}</label>
          <input id="dict-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(locale, "dict_search")}
            className="h-10 w-full rounded-md border border-hairline-strong bg-white px-3.5 text-[15px] text-ink placeholder:text-steel focus:border-ink focus:outline-none sm:max-w-[420px]" />
          <select aria-label={t(locale, "dict_language")} value={lang} onChange={(e) => setLang(e.target.value)} className={cn(control, "w-auto")}>
            <option value="">{t(locale, "dict_language")}: {t(locale, "dict_all")}</option>
            {langs.map((l) => <option key={l} value={l}>{termLangLabel(locale, l)}</option>)}
          </select>
          <select aria-label={t(locale, "dict_generation")} value={gen} onChange={(e) => setGen(e.target.value as Generation | "")} className={cn(control, "w-auto")}>
            <option value="">{t(locale, "dict_generation")}: {t(locale, "dict_all")}</option>
            {GENS.map((g) => <option key={g} value={g}>{labels.generation[g]}</option>)}
          </select>
          <select aria-label={t(locale, "dict_region")} value={region} onChange={(e) => setRegion(e.target.value)} className={cn(control, "w-auto")}>
            <option value="">{t(locale, "dict_region")}: {t(locale, "dict_all")}</option>
            {regions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
          </select>
          {readerGen && (
            <label className="flex items-center gap-1.5 text-[13px] text-charcoal"><input type="checkbox" checked={myGenFirst} onChange={(e) => setMyGenFirst(e.target.checked)} />{t(locale, "dict_my_gen_first")}</label>
          )}
        </div>
        <div role="group" aria-label={t(locale, "dict_categories")} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
          <button type="button" onClick={() => setCategory("")} aria-pressed={category === ""} className={pill(category === "")}>
            {t(locale, "dict_all")} <span className="tabular-nums opacity-75">{records.length}</span>
          </button>
          {categories.map(([c, n]) => (
            <button key={c} type="button" onClick={() => setCategory(category === c ? "" : c)} aria-pressed={category === c} className={pill(category === c)}>
              {labels.category[c as keyof typeof labels.category] ?? c} <span className="tabular-nums opacity-75">{n}</span>
            </button>
          ))}
        </div>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-steel">
          <span className="tabular-nums">{locale === "ko" ? `표현 ${shown.length}개` : `${shown.length} entries`}</span>
          {updatedAt && <span>{t(locale, "updates_last_run")} <span className="tabular-nums text-charcoal">{fmtDate(updatedAt)}</span></span>}
          {pendingCount > 0 && <span>{t(locale, "dict_pending_count")} <span className="tabular-nums text-charcoal">{pendingCount}</span></span>}
        </p>
      </div>

      {recent.length > 0 && (
        <section aria-labelledby="dict-recent" className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-y border-hairline py-3 text-[13px]">
          <h2 id="dict-recent" className="text-[13px] font-semibold text-ink">{t(locale, "dict_recent")}</h2>
          {recent.map(({ r }) => (
            <Link key={r.term.term_id} href={`/dictionary/${r.term.term_id}`} className="text-charcoal hover:text-ink hover:underline">{r.term.canonical}</Link>
          ))}
        </section>
      )}

      {/* 첫 글자 색인 */}
      <nav aria-label={t(locale, "dict_index")} className="flex flex-wrap gap-x-3 gap-y-1 text-[14px]">
        {groups.map((g) => <a key={g.key} href={`#idx-${encodeURIComponent(g.key)}`} className="text-charcoal hover:text-ink hover:underline">{g.key === "#" ? t(locale, "dict_other_scripts") : g.key}</a>)}
      </nav>
      {groups.length === 0 && <p className="rounded-lg border border-hairline px-4 py-8 text-center text-[14px] text-charcoal">{t(locale, "ex_no_result")}</p>}
      {groups.map((g) => (
        <section key={g.key} id={`idx-${encodeURIComponent(g.key)}`} aria-labelledby={`idx-h-${encodeURIComponent(g.key)}`} className="scroll-mt-16">
          <h2 id={`idx-h-${encodeURIComponent(g.key)}`} className="border-b border-hairline pb-2 text-[16px] font-semibold text-ink">{g.key === "#" ? t(locale, "dict_other_scripts") : g.key}</h2>
          <ul className="divide-y divide-hairline">
            {g.items.map((r) => {
              const m = currentMeaning(r);
              const tx = textFor(r, locale);
              return (
                <li key={r.term.term_id} className="grid gap-x-6 gap-y-1 py-3 md:grid-cols-[minmax(0,1fr)_200px]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <Link href={`/dictionary/${r.term.term_id}`} className="text-[16px] font-semibold text-ink hover:underline">{r.term.canonical}</Link>
                      {r.term.aliases && r.term.aliases.length > 0 && <span className="text-[13px] text-steel">{r.term.aliases.slice(0, 3).join(", ")}</span>}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[14px] leading-[1.55] text-charcoal">
                      {tx?.expansion && <span className="font-medium text-ink">{tx.expansion}. </span>}
                      {tx?.definition ?? m?.definition ?? t(locale, "dict_pending")}
                    </p>
                  </div>
                  <div className="flex flex-wrap content-start items-center gap-x-3 gap-y-1 text-[12px] text-steel md:justify-end">
                    <span>{labels.category[r.category]}</span>
                    {m && <span>{joinGens(locale, m.generations)}</span>}
                    {r.term.status === "needs_review" && <span className="text-charcoal">{t(locale, "dict_pending_short")}</span>}
                    {unfamiliar(r) && <span className="text-charcoal">{t(locale, "dict_unfamiliar")}</span>}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
