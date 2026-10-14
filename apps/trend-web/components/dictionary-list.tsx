"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChipMark } from "@/components/chip-mark";
import { RiskCell, StageCell } from "@/components/term-status";
import {
  PAGE_SIZE, aliasHit, inRegions, matchesExceptRegion, sortRows, unpackRows, type DictionaryRow, type Filters, type PackedRows, type RiskFilter,
  type SortKey,
} from "@/lib/dictionary/rows";
import { LOCALE_TAG, t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L, fmtDate, regionLabel, termLangLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

export interface DictionaryState extends Filters { sort: SortKey; page: number }

const control = "h-11 w-full rounded-md border border-hairline-strong bg-background px-3 text-[16px] text-ink sm:h-10 sm:text-[14px]";
const fieldLabel = "mb-1 block text-[13px] text-steel";
const textButton = "text-[13px] text-link-blue hover:underline";
const RISKS: Array<{ id: RiskFilter; key: StringKey }> = [
  { id: "none", key: "risk_none_short" }, { id: "caution", key: "risk_caution" }, { id: "avoid", key: "risk_avoid" },
  { id: "unknown", key: "risk_unknown" }, { id: "unchecked", key: "risk_not_checked" },
];
const REGION_CHIPS = [...TARGET_REGIONS, "GLOBAL"];

function toQuery(s: DictionaryState): string {
  const q = new URLSearchParams();
  if (s.q.trim()) q.set("q", s.q.trim());
  if (s.regions.length) q.set("regions", s.regions.join(","));
  if (s.kind) q.set("kind", s.kind);
  if (s.lang) q.set("lang", s.lang);
  if (s.risk) q.set("risk", s.risk);
  if (s.sort !== "name") q.set("sort", s.sort);
  if (s.page > 1) q.set("page", String(s.page));
  const out = q.toString();
  return out ? `?${out}` : "";
}

function Regions({ row, locale }: { row: DictionaryRow; locale: Locale }) {
  if (!row.regions.length) return <span className="text-steel">—</span>;
  const names = row.regions.slice(0, 3).map((r) => regionLabel(locale, r)).join(", ");
  const more = row.regions.length - 3;
  return <>{names}{more > 0 && ` ${t(locale, "pg_dict_more_regions").replace("{n}", String(more))}`}</>;
}

function Gloss({ row, locale, q }: { row: DictionaryRow; locale: Locale; q: string }) {
  const alias = aliasHit(row, q);
  const pending = (locale === "en" || locale === "ja") && !!row.meaning_lang;   // 영어·일본어판이 없는 뜻은 한국어 원문 대신 '번역 전' — 대시보드와 같다
  return (
    <>
      {alias && <p className="mt-0.5 text-[12px] text-steel">{t(locale, "pg_dict_also")}: <span lang={langTag(row.lang)}>{alias}</span></p>}
      <p lang={pending ? undefined : row.meaning_lang ?? undefined} className="mt-0.5 line-clamp-2 text-[14px] leading-[1.55] text-charcoal">
        {pending ? t(locale, locale === "ja" ? "gloss_ja_pending" : "gloss_en_pending") : <>
          {row.expansion && <span className="font-medium text-ink">{row.expansion}. </span>}
          {row.definition ?? t(locale, "dict_pending")}
        </>}
      </p>
    </>
  );
}

/* 사전 색인: 지역 칩 → 도구 줄(검색·분류·표제어 언어·쓸 때 조심·정렬) → 표(데스크톱)·한 줄 목록(휴대폰) → 쪽 나눔.
   행마다 '이 지역에서 지금 써도 되나'(단계·쓰이는 지역·쓸 때 조심)에 답한다. 자세한 것은 사전 항목에서 본다. */
export function DictionaryList({ packed, locale, readerGen = null, initial }: { packed: PackedRows; locale: Locale; readerGen?: string | null; initial: DictionaryState }) {
  const rows = useMemo(() => unpackRows(packed), [packed]);
  const [s, setS] = useState<DictionaryState>(initial);
  const [open, setOpen] = useState(false);           // 휴대폰에서 필터 펼침
  const labels = L(locale);
  const set = (patch: Partial<DictionaryState>) => setS((prev) => ({ ...prev, page: 1, ...patch }));

  // 주소에 둔다. 검색어는 치는 동안 매번 바꾸지 않게 조금 늦춘다. 화면은 다시 불러오지 않는다
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const id = window.setTimeout(() => window.history.replaceState(window.history.state, "", `/dictionary${toQuery(s)}`), 250);
    return () => window.clearTimeout(id);
  }, [s]);

  const categories = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of rows) m.set(r.category, (m.get(r.category) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);
  const langs = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of rows) m.set(r.lang, (m.get(r.lang) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const base = useMemo(() => rows.filter((r) => matchesExceptRegion(r, s)), [rows, s]);
  const shown = useMemo(() => sortRows(base.filter((r) => inRegions(r, s.regions)), s.sort, locale, readerGen), [base, s.regions, s.sort, locale, readerGen]);
  const regionCount = (code: string) => base.filter((r) => r.regions.includes(code)).length;
  const pages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const page = Math.min(s.page, pages);
  const slice = shown.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const filterCount = [s.kind, s.lang, s.risk].filter(Boolean).length;
  const anyFilter = !!(s.q.trim() || s.regions.length || filterCount);
  const clear = () => set({ q: "", regions: [], kind: "", lang: "", risk: "" });
  const toggleRegion = (r: string) => set({ regions: s.regions.includes(r) ? s.regions.filter((x) => x !== r) : [...s.regions, r] });
  const outside = s.regions.length ? base.length - shown.length : 0;
  const oneRegion = s.regions.length === 1;

  const count = anyFilter
    ? t(locale, "pg_dict_count_of").replace("{total}", String(rows.length)).replace("{n}", String(shown.length))
    : t(locale, "pg_dict_count").replace("{n}", String(shown.length));

  const filters = (
    <>
      <div className="min-w-0 sm:w-[160px]">
        <label htmlFor="dict-kind" className={fieldLabel}>{t(locale, "dict_categories")}</label>
        <select id="dict-kind" value={s.kind} onChange={(e) => set({ kind: e.target.value })} className={control}>
          <option value="">{t(locale, "dict_all")}</option>
          {categories.map(([c, n]) => <option key={c} value={c}>{labels.category[c as keyof typeof labels.category] ?? c} ({n})</option>)}
        </select>
      </div>
      <div className="min-w-0 sm:w-[160px]">
        <label htmlFor="dict-lang" className={fieldLabel}>{t(locale, "dict_language")}</label>
        <select id="dict-lang" value={s.lang} onChange={(e) => set({ lang: e.target.value })} className={control}>
          <option value="">{t(locale, "dict_all")}</option>
          {langs.map(([l, n]) => <option key={l} value={l}>{termLangLabel(locale, l)} ({n})</option>)}
        </select>
      </div>
      <div className="min-w-0 sm:w-[160px]">
        <label htmlFor="dict-risk" className={fieldLabel}>{t(locale, "dash_col_risk")}</label>
        <select id="dict-risk" value={s.risk} onChange={(e) => set({ risk: e.target.value })} className={control}>
          <option value="">{t(locale, "dict_all")}</option>
          {RISKS.map((r) => <option key={r.id} value={r.id}>{t(locale, r.key)}</option>)}
        </select>
      </div>
    </>
  );

  return (
    <div className="space-y-5">
      {/* 지역 칩 — 대시보드와 같은 지역 규칙, 여러 개를 고를 수 있다. 휴대폰에서는 한 줄로 옆으로 밀어 본다 */}
      <div role="group" aria-label={t(locale, "dash_regions")} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
        <button type="button" onClick={() => set({ regions: [] })} aria-pressed={!s.regions.length} className={chipClass(!s.regions.length)}>
          <ChipMark on={!s.regions.length} />{t(locale, "dict_all")} <span className="tabular-nums opacity-75">{base.length}</span>
        </button>
        {REGION_CHIPS.map((r) => {
          const on = s.regions.includes(r);
          return (
            <button key={r} type="button" onClick={() => toggleRegion(r)} aria-pressed={on} className={chipClass(on)}>
              <ChipMark on={on} />{regionLabel(locale, r)} <span className="tabular-nums opacity-75">{regionCount(r)}</span>
            </button>
          );
        })}
      </div>

      {/* 도구 줄. 라벨을 컨트롤 위에 보이게 둔다 — 옅은 테두리만으로는 무엇을 거르는 칸인지 드러나지 않았다 */}
      <div className="space-y-3 border-t border-hairline pt-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="min-w-0 sm:w-[320px]">
            <label htmlFor="dict-search" className={fieldLabel}>{t(locale, "pg_dict_search_label")}</label>
            <input id="dict-search" type="search" value={s.q} onChange={(e) => set({ q: e.target.value })} placeholder={t(locale, "dict_search")}
              className={cn(control, "placeholder:text-steel")} />
          </div>
          <div className="flex items-end gap-3 sm:contents">
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls="dict-filters"
              className="inline-flex h-11 shrink-0 items-center rounded-md border border-hairline-strong px-3 text-[14px] text-ink sm:hidden">
              {t(locale, "pg_dict_filters")}{filterCount > 0 && <span className="ml-1 tabular-nums">{filterCount}</span>}
            </button>
            <div className="min-w-0 flex-1 sm:order-last sm:w-[190px] sm:flex-none">
              <label htmlFor="dict-sort" className={fieldLabel}>{t(locale, "pg_dict_sort")}</label>
              <select id="dict-sort" value={s.sort} onChange={(e) => set({ sort: e.target.value as SortKey })} className={control}>
                <option value="name">{t(locale, "pg_dict_sort_name")}</option>
                <option value="used">{t(locale, "pg_dict_sort_used")}</option>
                <option value="changed">{t(locale, "pg_dict_sort_changed")}</option>
                {readerGen && <option value="unfamiliar">{t(locale, "dict_my_gen_first")}</option>}
              </select>
            </div>
          </div>
          <div id="dict-filters" className={cn("flex-col gap-3 sm:flex sm:flex-row sm:items-end", open ? "flex" : "hidden")}>{filters}</div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p role="status" className="text-[13px] tabular-nums text-charcoal">{count}</p>
          {anyFilter && <button type="button" onClick={clear} className={textButton}>{t(locale, "pg_dict_clear")}</button>}
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="rounded-lg border border-hairline px-6 py-6 text-[14px] leading-[1.6] text-charcoal">
          <p>{s.q.trim() ? t(locale, "pg_dict_no_q_result").replace("{q}", s.q.trim()) : t(locale, "pg_dict_no_filter_result")}</p>
          {outside > 0 && (
            <p className="mt-1">
              {t(locale, "pg_dict_elsewhere").replace("{n}", String(outside))}{" "}
              <button type="button" onClick={() => set({ regions: [] })} className={textButton}>{t(locale, "pg_dict_all_regions")}</button>
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <button type="button" onClick={clear} className="inline-flex h-10 items-center rounded-md border border-hairline-strong px-3 text-[14px] text-ink hover:border-ink">{t(locale, "pg_dict_clear")}</button>
            <Link href="/explain" className="text-[14px] text-link-blue hover:underline">{t(locale, "pg_dict_ask")}</Link>
          </div>
        </div>
      ) : (
        <>
          <div className="hidden md:block">
            <table className="w-full table-fixed border-collapse text-left">
              <caption className="sr-only">{t(locale, "pg_dict_caption")}</caption>
              <thead>
                <tr className="border-b border-hairline bg-surface-soft text-[13px] text-steel">
                  <th scope="col" aria-sort={s.sort === "name" ? "ascending" : undefined} className="px-3 py-2.5 font-medium">{t(locale, "dash_col_keyword")}</th>
                  <th scope="col" className="w-[170px] px-3 py-2.5 font-medium">{t(locale, "dash_col_stage")}</th>
                  <th scope="col" className="hidden w-[150px] px-3 py-2.5 font-medium xl:table-cell">{t(locale, "pg_dict_col_regions")}</th>
                  <th scope="col" aria-sort={s.sort === "used" ? "descending" : undefined} className="w-[110px] px-3 py-2.5 text-right font-medium">{t(locale, "pg_col_last_used")}</th>
                  <th scope="col" className="w-[130px] px-3 py-2.5 font-medium">{t(locale, "dash_col_risk")}</th>
                </tr>
              </thead>
              <tbody>
                {slice.map((r) => (
                  <tr key={r.term_id} className="border-b border-hairline align-top hover:bg-surface-soft">
                    <th scope="row" className="px-3 py-3 text-left font-normal">
                      <Link href={`/dictionary/${r.term_id}`} lang={r.name ? LOCALE_TAG[locale] : langTag(r.lang)} className="text-[15px] font-semibold text-ink hover:underline">{r.name ?? r.canonical}</Link>
                      {r.reading && <span lang={LOCALE_TAG[locale]} className="ml-2 text-[12px] text-steel">{r.reading}</span>}
                      <Gloss row={r} locale={locale} q={s.q} />
                      {!oneRegion && <p className="mt-0.5 text-[12px] text-steel xl:hidden"><Regions row={r} locale={locale} /></p>}
                    </th>
                    <td className="px-3 py-3"><StageCell diffusion={r.diffusion} lifecycle={r.lifecycle} locale={locale} /></td>
                    <td className="hidden px-3 py-3 text-[13px] text-charcoal xl:table-cell"><Regions row={r} locale={locale} /></td>
                    <td className="px-3 py-3 text-right text-[13px] tabular-nums text-charcoal">{fmtDate(r.last_used)}</td>
                    <td className="px-3 py-3"><RiskCell item={r} locale={locale} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
            {slice.map((r) => (
              <li key={r.term_id} className="py-3.5">
                <div className="flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <Link href={`/dictionary/${r.term_id}`} lang={r.name ? LOCALE_TAG[locale] : langTag(r.lang)} className="inline-block min-h-[32px] py-1 text-[16px] font-semibold text-ink hover:underline">{r.name ?? r.canonical}</Link>
                    {r.reading && <span lang={LOCALE_TAG[locale]} className="ml-2 text-[12px] text-steel">{r.reading}</span>}
                  </span>
                  <RiskCell item={r} locale={locale} />
                </div>
                <Gloss row={r} locale={locale} q={s.q} />
                <dl className="mt-2 space-y-1 text-[12px]">
                  <div className="flex flex-wrap items-center gap-x-2"><dt className="text-steel">{t(locale, "dash_col_stage")}</dt><dd><StageCell diffusion={r.diffusion} lifecycle={r.lifecycle} locale={locale} /></dd></div>
                  {!oneRegion && <div className="flex flex-wrap gap-x-2"><dt className="text-steel">{t(locale, "pg_dict_col_regions")}</dt><dd className="text-charcoal"><Regions row={r} locale={locale} /></dd></div>}
                  <div className="flex flex-wrap gap-x-2"><dt className="text-steel">{t(locale, "pg_col_last_used")}</dt><dd className="tabular-nums text-charcoal">{fmtDate(r.last_used)}</dd></div>
                </dl>
              </li>
            ))}
          </ul>

          {pages > 1 && (
            <nav aria-label={t(locale, "pg_dict_pages")} className="flex flex-wrap items-center justify-end gap-3 text-[13px]">
              <span className="tabular-nums text-steel">
                {t(locale, "pg_dict_range").replace("{total}", String(shown.length)).replace("{from}", String((page - 1) * PAGE_SIZE + 1)).replace("{to}", String(Math.min(page * PAGE_SIZE, shown.length)))}
              </span>
              <button type="button" disabled={page <= 1} onClick={() => { setS((p) => ({ ...p, page: page - 1 })); window.scrollTo({ top: 0 }); }}
                className="inline-flex h-11 items-center rounded-md border border-hairline-strong px-3 text-ink disabled:text-steel sm:h-9">{t(locale, "pg_dict_prev")}</button>
              <span className="tabular-nums text-charcoal" aria-current="page">{page} / {pages}</span>
              <button type="button" disabled={page >= pages} onClick={() => { setS((p) => ({ ...p, page: page + 1 })); window.scrollTo({ top: 0 }); }}
                className="inline-flex h-11 items-center rounded-md border border-hairline-strong px-3 text-ink disabled:text-steel sm:h-9">{t(locale, "pg_dict_next")}</button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
