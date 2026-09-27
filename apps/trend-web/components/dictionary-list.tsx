"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { currentMeaning, textFor } from "@/lib/explain";
import { groupByInitial } from "@/lib/dictionary/index";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, joinGens, regionLabel, termLangLabel } from "@/lib/labels";
import type { Generation, TermRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

const GENS: Generation[] = ["10s", "20s", "30s", "40s", "50s+"];
const control = "h-9 w-full rounded-[4px] border border-hairline bg-white px-2.5 text-[13px] text-ink focus:border-ink focus:outline-none";

/* 위키식 사전 색인: 큰 검색창, 왼쪽에 분류·필터·최근 바뀐 문서, 오른쪽에 첫 글자 색인. */
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

  return (
    <div className="space-y-6">
      {/* 검색 */}
      <div className="flex flex-wrap items-center gap-3">
        <input id="dict-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(locale, "dict_search")}
          className="h-12 w-full max-w-[640px] rounded-[6px] border border-hairline-strong bg-white px-4 text-[16px] text-ink focus:border-ink focus:outline-none" />
        <span className="text-[13px] text-steel tabular-nums">
          {locale === "ko" ? `표현 ${shown.length}개` : `${shown.length} entries`}{updatedAt && <> · {t(locale, "updates_last_run")} {fmtDate(updatedAt)}</>}
        </span>
      </div>

      <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* 왼쪽: 분류·필터·최근 — 좁은 화면에서는 접어 둔다 */}
        <details className="text-[13px] lg:hidden">
          <summary className="cursor-pointer font-semibold text-ink">{t(locale, "dict_categories")} · {t(locale, "dict_language")} · {t(locale, "dict_generation")} · {t(locale, "dict_region")}</summary>
          <div className="mt-3 space-y-6">
          <section>
            <h2 className="mb-1.5 font-semibold text-ink">{t(locale, "dict_categories")}</h2>
            <ul className="space-y-0.5">
              <li><button type="button" onClick={() => setCategory("")} className={cn("flex w-full justify-between hover:text-ink", category === "" ? "font-medium text-ink" : "text-charcoal")}><span>{t(locale, "dict_all")}</span><span className="tabular-nums text-steel">{records.length}</span></button></li>
              {categories.map(([c, n]) => (
                <li key={c}><button type="button" onClick={() => setCategory(category === c ? "" : c)} className={cn("flex w-full justify-between hover:text-ink", category === c ? "font-medium text-ink" : "text-charcoal")}><span>{labels.category[c as keyof typeof labels.category] ?? c}</span><span className="tabular-nums text-steel">{n}</span></button></li>
              ))}
              {pendingCount > 0 && <li className="pt-1 text-steel">{t(locale, "dict_pending_count")} {pendingCount}</li>}
            </ul>
          </section>
          <section className="space-y-2">
            <label className="block text-steel">{t(locale, "dict_language")}
              <select value={lang} onChange={(e) => setLang(e.target.value)} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {langs.map((l) => <option key={l} value={l}>{termLangLabel(locale, l)}</option>)}
              </select>
            </label>
            <label className="block text-steel">{t(locale, "dict_generation")}
              <select value={gen} onChange={(e) => setGen(e.target.value as Generation | "")} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {GENS.map((g) => <option key={g} value={g}>{labels.generation[g]}</option>)}
              </select>
            </label>
            <label className="block text-steel">{t(locale, "dict_region")}
              <select value={region} onChange={(e) => setRegion(e.target.value)} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {regions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
              </select>
            </label>
            {readerGen && (
              <label className="flex items-center gap-1.5 text-charcoal"><input type="checkbox" checked={myGenFirst} onChange={(e) => setMyGenFirst(e.target.checked)} />{t(locale, "dict_my_gen_first")}</label>
            )}
          </section>
          {recent.length > 0 && (
            <section>
              <h2 className="mb-1.5 font-semibold text-ink">{t(locale, "dict_recent")}</h2>
              <ul className="space-y-1">
                {recent.map(({ r, at }) => (
                  <li key={r.term.term_id} className="flex justify-between gap-2"><Link href={`/dictionary/${r.term.term_id}`} className="truncate text-charcoal hover:text-ink hover:underline">{r.term.canonical}</Link><span className="shrink-0 tabular-nums text-steel">{fmtDate(at).slice(5)}</span></li>
                ))}
              </ul>
            </section>
          )}
          </div>
        </details>
        <aside className="hidden space-y-6 text-[13px] lg:block">
          <section>
            <h2 className="mb-1.5 font-semibold text-ink">{t(locale, "dict_categories")}</h2>
            <ul className="space-y-0.5">
              <li><button type="button" onClick={() => setCategory("")} className={cn("flex w-full justify-between hover:text-ink", category === "" ? "font-medium text-ink" : "text-charcoal")}><span>{t(locale, "dict_all")}</span><span className="tabular-nums text-steel">{records.length}</span></button></li>
              {categories.map(([c, n]) => (
                <li key={c}><button type="button" onClick={() => setCategory(category === c ? "" : c)} className={cn("flex w-full justify-between hover:text-ink", category === c ? "font-medium text-ink" : "text-charcoal")}><span>{labels.category[c as keyof typeof labels.category] ?? c}</span><span className="tabular-nums text-steel">{n}</span></button></li>
              ))}
              {pendingCount > 0 && <li className="pt-1 text-steel">{t(locale, "dict_pending_count")} {pendingCount}</li>}
            </ul>
          </section>
          <section className="space-y-2">
            <label className="block text-steel">{t(locale, "dict_language")}
              <select value={lang} onChange={(e) => setLang(e.target.value)} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {langs.map((l) => <option key={l} value={l}>{termLangLabel(locale, l)}</option>)}
              </select>
            </label>
            <label className="block text-steel">{t(locale, "dict_generation")}
              <select value={gen} onChange={(e) => setGen(e.target.value as Generation | "")} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {GENS.map((g) => <option key={g} value={g}>{labels.generation[g]}</option>)}
              </select>
            </label>
            <label className="block text-steel">{t(locale, "dict_region")}
              <select value={region} onChange={(e) => setRegion(e.target.value)} className={cn(control, "mt-1")}>
                <option value="">{t(locale, "dict_all")}</option>
                {regions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
              </select>
            </label>
            {readerGen && (
              <label className="flex items-center gap-1.5 text-charcoal"><input type="checkbox" checked={myGenFirst} onChange={(e) => setMyGenFirst(e.target.checked)} />{t(locale, "dict_my_gen_first")}</label>
            )}
          </section>
          {recent.length > 0 && (
            <section>
              <h2 className="mb-1.5 font-semibold text-ink">{t(locale, "dict_recent")}</h2>
              <ul className="space-y-1">
                {recent.map(({ r, at }) => (
                  <li key={r.term.term_id} className="flex justify-between gap-2"><Link href={`/dictionary/${r.term.term_id}`} className="truncate text-charcoal hover:text-ink hover:underline">{r.term.canonical}</Link><span className="shrink-0 tabular-nums text-steel">{fmtDate(at).slice(5)}</span></li>
                ))}
              </ul>
            </section>
          )}
        </aside>

        {/* 오른쪽: 첫 글자 색인 */}
        <div className="min-w-0">
          <nav aria-label={t(locale, "dict_index")} className="flex flex-wrap gap-x-2.5 gap-y-1 border-b border-hairline pb-3 text-[13px]">
            {groups.map((g) => <a key={g.key} href={`#idx-${encodeURIComponent(g.key)}`} className="text-charcoal hover:text-ink hover:underline">{g.key === "#" ? t(locale, "dict_other_scripts") : g.key}</a>)}
          </nav>
          {groups.length === 0 && <p className="py-6 text-[14px] text-steel">{t(locale, "ex_no_result")}</p>}
          {groups.map((g) => (
            <section key={g.key} id={`idx-${encodeURIComponent(g.key)}`} className="scroll-mt-4 py-4">
              <h2 className="text-[18px] font-semibold text-ink">{g.key === "#" ? t(locale, "dict_other_scripts") : g.key}</h2>
              <ul className="mt-2 divide-y divide-hairline-soft">
                {g.items.map((r) => {
                  const m = currentMeaning(r);
                  const tx = textFor(r, locale);
                  return (
                    <li key={r.term.term_id} className="py-2.5">
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <Link href={`/dictionary/${r.term.term_id}`} className="text-[16px] font-semibold text-ink hover:underline">{r.term.canonical}</Link>
                        {r.term.aliases && r.term.aliases.length > 0 && <span className="text-[13px] text-steel">{r.term.aliases.slice(0, 3).join(", ")}</span>}
                        <span className="ml-auto text-[12px] text-steel">
                          {labels.category[r.category]}{m && <> · {joinGens(locale, m.generations)}</>}
                          {r.term.status === "needs_review" && <> · {t(locale, "dict_pending_short")}</>}
                          {unfamiliar(r) && <> · {t(locale, "dict_unfamiliar")}</>}
                        </span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[14px] text-charcoal">
                        {tx?.expansion && <span className="font-medium text-ink">{tx.expansion}. </span>}
                        {tx?.definition ?? m?.definition ?? t(locale, "dict_pending")}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
