"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ListTabs } from "@/components/list-tabs";
import { Sparkline } from "@/components/sparkline";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, fmtDateTime, joinGens, joinRegions, sourceName } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import type { Evidence, Meaning, ReviewItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/* 검수 대기 목록 (docs/트렌드/디자인-개편.md, 관리 화면 검토 09-29).
   행에는 (검토) 하나만 두고, 펼친 한 항목 안에서 근거·지금 실린 뜻을 본 뒤 결정한다 — 한 번에 하나만 펼치므로 검정 버튼도 하나다.
   승인·제외는 6초 동안 되돌릴 수 있고, 그 뒤에 본 뜻의 id 와 함께 보낸다(그사이 새 판이 생겼으면 서버가 409 로 막는다).
   건너뛰기는 아무것도 기록하지 않는다. */

export type ReviewKind = "new" | "changed" | "trend";
const REVIEW_KINDS: ReviewKind[] = ["new", "changed", "trend"];
const kindOf = (it: ReviewItem): ReviewKind => (it.proposed.created_by === "tracking_agent" ? "trend" : it.current || it.proposed.version > 1 ? "changed" : "new");
const KIND_KEY = { new: "adm_kind_new", changed: "adm_kind_changed", trend: "adm_kind_trend" } as const;

type Sort = "oldest" | "newest" | "evidence";
type Decision = "approve" | "reject";
const UNDO_MS = 6000;
const PAGE = 50;
const DAY = 86_400_000;

export const BTN = "inline-flex h-10 items-center justify-center rounded-md px-3 text-[13px] font-medium whitespace-nowrap sm:h-8";
export const BTN_OUTLINE = cn(BTN, "border border-hairline-strong bg-background text-ink hover:border-ink");
const BTN_PRIMARY = cn(BTN, "bg-ink text-white hover:bg-ink/85");
const FIELD = "h-10 rounded-md border border-hairline-strong bg-background px-3 text-[14px] text-ink sm:h-8 sm:text-[13px]";

const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replace(`{${k}}`, String(x)), s);

/** 인용문에서 표현만 굵게. 대소문자만 다른 것까지 찾는다. */
function Quote({ text, term, lang }: { text: string; term: string; lang?: string }) {
  const i = term ? text.toLowerCase().indexOf(term.toLowerCase()) : -1;
  return (
    <q lang={lang} className="text-[14px] leading-[1.55] text-ink">
      {i < 0 ? text : <>{text.slice(0, i)}<strong className="font-semibold">{text.slice(i, i + term.length)}</strong>{text.slice(i + term.length)}</>}
    </q>
  );
}

function MeaningBlock({ m, locale, title }: { m: Meaning; locale: Locale; title: string }) {
  const rows: [string, string][] = [
    [t(locale, "adm_f_origin"), m.origin],
    [t(locale, "adm_f_nuance"), m.nuance],
    [t(locale, "adm_f_regions"), joinRegions(locale, m.regions)],
    [t(locale, "adm_f_generations"), joinGens(locale, m.generations)],
  ];
  return (
    <div className="min-w-0 space-y-2">
      <h4 className="text-[13px] font-medium text-steel">{title}</h4>
      <p className="text-[15px] leading-[1.55] text-ink" lang={scriptLang(m.definition)}>{m.definition}</p>
      <dl className="grid grid-cols-[88px_minmax(0,1fr)] gap-x-3 gap-y-1 text-[13px]">
        {rows.filter(([, v]) => v).map(([k, v]) => (
          <Fragment key={k}><dt className="text-steel">{k}</dt><dd className="text-charcoal">{v}</dd></Fragment>
        ))}
      </dl>
    </div>
  );
}

function changedFields(a: Meaning, b: Meaning, locale: Locale): string[] {
  const same = (x: string[], y: string[]) => [...x].sort().join() === [...y].sort().join();
  const out: string[] = [];
  if (a.definition !== b.definition) out.push(t(locale, "adm_f_definition"));
  if (a.origin !== b.origin && !b.origin.startsWith("(v")) out.push(t(locale, "adm_f_origin"));
  if (a.nuance !== b.nuance) out.push(t(locale, "adm_f_nuance"));
  if (!same(a.regions, b.regions)) out.push(t(locale, "adm_f_regions"));
  if (!same(a.generations, b.generations)) out.push(t(locale, "adm_f_generations"));
  return out;
}

function Sources({ list, term, lang, locale }: { list: Evidence[]; term: string; lang?: string; locale: Locale }) {
  const kind = L(locale).evidenceKind;
  return (
    <ul className="divide-y divide-hairline">
      {list.map((e, i) => {
        const text = e.excerpt || e.title || "";
        return (
          <li key={`${e.evidence_id}-${i}`} className="grid gap-x-4 gap-y-1 py-2.5 md:grid-cols-[minmax(0,1fr)_140px_96px_80px] md:items-baseline">
            <Quote text={text} term={term} lang={scriptLang(text) ?? lang} />
            <span className="text-[13px] text-charcoal">{sourceName(locale, e.source_domain)} <span className="text-steel">{kind[e.kind]}</span></span>
            <span className="text-[13px] tabular-nums text-steel">{fmtDate(e.observed_at)}</span>
            <a href={e.url} target="_blank" rel="noreferrer noopener" className="text-[13px] text-link-blue hover:underline">{t(locale, "adm_open_source")}</a>
          </li>
        );
      })}
    </ul>
  );
}

export function ReviewTable({ items, live = false, locale, kind }: { items: ReviewItem[]; live?: boolean; locale: Locale; kind: ReviewKind | "all" }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("oldest");
  const [limit, setLimit] = useState(PAGE);
  const [open, setOpen] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, Decision>>({});
  const [sending, setSending] = useState<Record<string, true>>({});
  const [gone, setGone] = useState<Record<string, true>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [announce, setAnnounce] = useState("");
  const [now] = useState(() => Date.now());
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const queued = useRef(new Map<string, { termId: string; decision: Decision }>());
  const focusNext = useRef<string | null>(null);
  const reviewBtns = useRef(new Map<string, HTMLButtonElement>());
  const undoBtns = useRef(new Map<string, HTMLButtonElement>());

  const alive = items.filter((it) => !gone[it.proposed.meaning_id]);
  const counts = { all: alive.length, new: 0, changed: 0, trend: 0 } as Record<ReviewKind | "all", number>;
  for (const it of alive) counts[kindOf(it)] += 1;
  const needle = q.trim().toLowerCase();
  const by = { oldest: (a: ReviewItem, b: ReviewItem) => a.queued_at.localeCompare(b.queued_at),
    newest: (a: ReviewItem, b: ReviewItem) => b.queued_at.localeCompare(a.queued_at),
    evidence: (a: ReviewItem, b: ReviewItem) => b.evidence_count - a.evidence_count || a.queued_at.localeCompare(b.queued_at) }[sort];
  const rows = alive.filter((it) => (kind === "all" || kindOf(it) === kind)
    && (!needle || it.canonical.toLowerCase().includes(needle) || it.proposed.definition.toLowerCase().includes(needle))).sort(by);
  const visible = rows.slice(0, limit);

  // 보내는 일은 한곳에서: 되돌리기 시간이 지났을 때, 또는 페이지를 떠날 때(keepalive)
  const send = async (id: string, keepalive = false) => {
    const job = queued.current.get(id);
    if (!job) return;
    queued.current.delete(id);
    const tm = timers.current.get(id);
    if (tm) clearTimeout(tm);
    timers.current.delete(id);
    if (!live) { finish(id); return; }
    setSending((s) => ({ ...s, [id]: true }));
    try {
      const res = await fetch(`/api/review/${encodeURIComponent(job.termId)}`, {
        method: "POST", headers: { "content-type": "application/json" }, keepalive,
        body: JSON.stringify({ decision: job.decision, meaning_id: id }),
      });
      if (!res.ok) throw new Error(String(res.status));
      finish(id);
      router.refresh();   // 요약 칸과 탭 건수를 다시 읽는다(관리 조회는 캐시하지 않는다)
    } catch (e) {
      const code = (e as Error).message;
      const key = code === "401" ? "adm_err_401" : code === "403" ? "adm_err_403" : code === "409" ? "adm_err_409" : "adm_err_other";
      setPending((p) => { const n = { ...p }; delete n[id]; return n; });
      setErrors((x) => ({ ...x, [id]: t(locale, key) }));
      if (code === "409") router.refresh();   // 새 제안을 다시 읽는다
    } finally {
      setSending((s) => { const n = { ...s }; delete n[id]; return n; });
    }
  };
  const finish = (id: string) => {
    const idx = visible.findIndex((it) => it.proposed.meaning_id === id);
    focusNext.current = visible[idx + 1]?.proposed.meaning_id ?? visible[idx - 1]?.proposed.meaning_id ?? null;
    setGone((g) => ({ ...g, [id]: true }));
  };
  const sendRef = useRef(send);
  useEffect(() => { sendRef.current = send; });
  useEffect(() => {
    const flush = () => { for (const id of [...queued.current.keys()]) void sendRef.current(id, true); };
    window.addEventListener("pagehide", flush);
    return () => { window.removeEventListener("pagehide", flush); flush(); };   // 다른 화면으로 옮겨 가도 바로 보낸다
  }, []);
  // 초점: 결정하면 (되돌리기)로, 되돌리거나 건너뛰면 그 행의 (검토)로, 줄이 빠지면 다음 행의 (검토)로 — 그린 뒤에 옮긴다
  const [focusTo, setFocusTo] = useState<{ id: string; on: "undo" | "review"; n: number } | null>(null);
  useEffect(() => {
    if (!focusTo) return;
    (focusTo.on === "undo" ? undoBtns : reviewBtns).current.get(focusTo.id)?.focus();
  }, [focusTo]);
  useEffect(() => {
    const id = focusNext.current;
    if (id) { focusNext.current = null; setFocusTo((f) => ({ id, on: "review", n: (f?.n ?? 0) + 1 })); }
  }, [gone]);
  const focus = (id: string, on: "undo" | "review") => setFocusTo((f) => ({ id, on, n: (f?.n ?? 0) + 1 }));

  const decide = (it: ReviewItem, d: Decision) => {
    const id = it.proposed.meaning_id;
    setErrors((x) => { const n = { ...x }; delete n[id]; return n; });
    setPending((p) => ({ ...p, [id]: d }));
    setOpen(null);
    queued.current.set(id, { termId: it.term_id, decision: d });
    timers.current.set(id, setTimeout(() => void sendRef.current(id), UNDO_MS));
    setAnnounce(`${it.canonical} ${t(locale, d === "approve" ? "adm_done_approved" : "adm_done_rejected")}`);
    focus(id, "undo");
  };
  const undo = (it: ReviewItem) => {
    const id = it.proposed.meaning_id;
    const tm = timers.current.get(id);
    if (tm) clearTimeout(tm);
    timers.current.delete(id);
    queued.current.delete(id);
    setPending((p) => { const n = { ...p }; delete n[id]; return n; });
    setAnnounce("");
    focus(id, "review");
  };
  const skip = (it: ReviewItem) => {
    setOpen(null);
    setAnnounce(`${it.canonical} ${t(locale, "adm_done_skipped")}`);
    focus(it.proposed.meaning_id, "review");
  };

  const tabs = (["all", ...REVIEW_KINDS] as const).map((k) => ({
    id: k, label: t(locale, k === "all" ? "adm_kind_all" : KIND_KEY[k]), count: counts[k], href: k === "all" ? "/admin" : `/admin?kind=${k}`,
  }));
  const sortLabel = t(locale, `adm_sort_${sort}`);
  const grid = "md:grid md:grid-cols-[160px_minmax(0,1fr)_72px_64px_96px] md:gap-x-4 xl:grid-cols-[160px_minmax(0,1fr)_260px_72px_64px_96px]";

  if (!items.length) {
    return (
      <div className="rounded-lg border border-hairline px-6 py-6 text-[14px] leading-[1.6] text-charcoal">
        <p>{t(locale, "adm_review_empty")}</p>
        <Link href="/admin/status" className="mt-3 inline-block text-link-blue hover:underline">{t(locale, "adm_see_status")}</Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <ListTabs items={tabs} current={kind} label={t(locale, "adm_kind_label")} />
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input type="search" value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder={t(locale, "adm_find")} aria-label={t(locale, "adm_find")}
            className={cn(FIELD, "w-full sm:w-[220px] placeholder:text-steel")} />
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label={t(locale, "adm_sort")} className={FIELD}>
            {(["oldest", "newest", "evidence"] as const).map((s) => <option key={s} value={s}>{t(locale, `adm_sort_${s}`)}</option>)}
          </select>
        </div>
      </div>

      <p role="status" aria-live="polite" className="sr-only">{announce}</p>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-hairline px-6 py-6 text-[14px] text-charcoal">{needle ? fill(t(locale, "adm_no_match"), { q: q.trim() }) : t(locale, "adm_review_empty")}</p>
      ) : (
        <section aria-label={fill(t(locale, "adm_caption_review"), { n: rows.length, sort: sortLabel })}>
          <div aria-hidden className={cn("hidden border-b border-hairline bg-surface px-3 py-2 text-[13px] font-medium text-steel", grid)}>
            <span>{t(locale, "adm_col_term")}</span>
            <span>{t(locale, "adm_col_proposal")}</span>
            <span className="hidden xl:block">{t(locale, "adm_col_reasons")}</span>
            <span className="text-right">{t(locale, "adm_col_evidence")}</span>
            <span className="text-right">{t(locale, "adm_col_waiting")}</span>
            <span />
          </div>
          <ul className="divide-y divide-hairline border-b border-hairline">
            {visible.map((it) => {
              const id = it.proposed.meaning_id;
              const k = kindOf(it);
              const lang = langTag(it.lang) ?? scriptLang(it.canonical);
              const days = Math.max(0, Math.floor((now - Date.parse(it.queued_at)) / DAY));
              const decided = pending[id];
              const isOpen = open === id;
              if (decided) {
                return (
                  <li key={id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-3 text-[14px]">
                    <span lang={lang} className="font-semibold text-ink">{it.canonical}</span>
                    <span className="text-charcoal">
                      {t(locale, decided === "approve" ? "adm_done_approved" : "adm_done_rejected")}
                      {!live && ` ${t(locale, "adm_sample_note")}`}
                    </span>
                    <button type="button" ref={(el) => { if (el) undoBtns.current.set(id, el); else undoBtns.current.delete(id); }}
                      disabled={!!sending[id]} onClick={() => undo(it)} className={cn(BTN_OUTLINE, "ml-auto disabled:opacity-50")}>{t(locale, "adm_undo")}</button>
                  </li>
                );
              }
              return (
                <li key={id}>
                  <div className={cn("space-y-2 px-3 py-3 md:space-y-0", grid, isOpen && "bg-surface")}>
                    <div className="flex items-baseline justify-between gap-3 md:block">
                      <span lang={lang} className="text-[15px] font-semibold text-ink [overflow-wrap:break-word]">{it.canonical}</span>
                      <span className="text-[13px] tabular-nums whitespace-nowrap text-steel md:hidden" title={fill(t(locale, "adm_since"), { date: fmtDateTime(it.queued_at, locale) })}>
                        {fill(t(locale, "adm_waiting_n"), { n: days })}
                      </span>
                      <span className="hidden text-[13px] text-steel md:block">{t(locale, KIND_KEY[k])}</span>
                    </div>
                    <div className="flex items-baseline justify-between gap-3 text-[13px] text-steel md:hidden">
                      <span>{t(locale, KIND_KEY[k])}</span>
                      <span className="tabular-nums">{fill(t(locale, "adm_evidence_n"), { n: it.evidence_count })}</span>
                    </div>
                    <p className="line-clamp-3 text-[14px] leading-[1.55] text-charcoal md:col-start-2 md:row-start-1">{it.proposed.definition}</p>
                    <div className="text-[13px] text-charcoal md:col-start-2 md:row-start-2 md:pt-2 xl:col-start-3 xl:row-start-1 xl:pt-0">
                      <span className="text-steel md:sr-only">{t(locale, "adm_col_reasons")}</span>
                      <ul className="list-disc space-y-0.5 pl-4">{it.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                    </div>
                    <span className="hidden text-right text-[14px] tabular-nums whitespace-nowrap text-charcoal md:col-start-3 md:row-start-1 md:block xl:col-start-4">
                      <span className="sr-only">{t(locale, "adm_col_evidence")} </span>{fill(t(locale, "adm_count"), { n: it.evidence_count })}
                    </span>
                    <span className="hidden text-right text-[14px] tabular-nums whitespace-nowrap text-charcoal md:col-start-4 md:row-start-1 md:block xl:col-start-5"
                      title={fill(t(locale, "adm_since"), { date: fmtDateTime(it.queued_at, locale) })}>
                      <span className="sr-only">{t(locale, "adm_col_waiting")} </span>{fill(t(locale, "adm_days"), { n: days })}
                    </span>
                    <div className="pt-1 md:col-start-5 md:row-start-1 md:pt-0 md:text-right xl:col-start-6">
                      <button type="button" ref={(el) => { if (el) reviewBtns.current.set(id, el); else reviewBtns.current.delete(id); }}
                        aria-expanded={isOpen} aria-controls={`rv-${id}`} aria-label={fill(t(locale, "adm_action_aria"), { term: it.canonical, action: t(locale, isOpen ? "adm_close_btn" : "adm_review_btn") })}
                        onClick={() => setOpen(isOpen ? null : id)} className={cn(BTN_OUTLINE, "w-full md:w-auto")}>
                        {t(locale, isOpen ? "adm_close_btn" : "adm_review_btn")}
                      </button>
                    </div>
                    {errors[id] && <p role="alert" className="text-[13px] text-avoid md:col-span-full md:pt-2">{errors[id]}</p>}
                  </div>
                  {isOpen && <Detail it={it} kind={k} lang={lang} locale={locale} onDecide={(d) => decide(it, d)} onSkip={() => skip(it)} />}
                </li>
              );
            })}
          </ul>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 text-[13px] text-steel">
            <span className="tabular-nums">{fill(t(locale, "adm_range"), { total: rows.length, n: visible.length })}</span>
            {rows.length > visible.length && <button type="button" onClick={() => setLimit((n) => n + PAGE)} className={cn(BTN_OUTLINE, "w-full sm:w-auto")}>{t(locale, "adm_more")}</button>}
          </div>
          <p className="pt-2 text-[13px]"><Link href="/updates" className="text-link-blue hover:underline">{t(locale, "adm_past_decisions")}</Link></p>
        </section>
      )}
    </div>
  );
}

function Detail({ it, kind, lang, locale, onDecide, onSkip }: { it: ReviewItem; kind: ReviewKind; lang?: string; locale: Locale; onDecide: (d: Decision) => void; onSkip: () => void }) {
  const id = it.proposed.meaning_id;
  const evs = it.evidences ?? [];
  const cur = it.current ?? null;
  const changed = cur && kind === "changed" ? changedFields(cur, it.proposed, locale) : [];
  return (
    <div id={`rv-${id}`} role="region" aria-labelledby={`rv-${id}-h`} className="space-y-5 border-t border-hairline bg-surface px-3 pb-5 pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`rv-${id}-h`} lang={lang} className="text-[18px] font-semibold text-ink">{it.canonical}</h3>
        {changed.length > 0 && <span className="text-[13px] text-steel">{t(locale, "adm_changed_fields")}: {changed.join(", ")}</span>}
      </div>

      {kind === "trend" ? (
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <h4 className="text-[13px] font-medium text-steel">{t(locale, "adm_col_proposal")}</h4>
            <p className="text-[15px] leading-[1.55] text-ink">{it.proposed.definition}</p>
            {it.reasons.length > 0 && <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-charcoal">{it.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
          </div>
          {(it.weekly?.length ?? 0) > 1 && (
            <div className="space-y-2">
              <h4 className="text-[13px] font-medium text-steel">{t(locale, "adm_trend_weekly")}</h4>
              <Sparkline points={it.weekly!} width={280} height={56} label={t(locale, "spark_label").replace("{n}", String(it.weekly!.length)).replace("{last}", String(it.weekly!.at(-1)?.count ?? 0)).replace("{max}", String(Math.max(0, ...it.weekly!.map((p) => p.count))))} />
            </div>
          )}
        </div>
      ) : kind === "changed" ? (
        <div className="grid gap-5 md:grid-cols-2">
          {cur ? <MeaningBlock m={cur} locale={locale} title={t(locale, "adm_current")} />
            : <div className="space-y-2"><h4 className="text-[13px] font-medium text-steel">{t(locale, "adm_current")}</h4><p className="text-[14px] text-charcoal">{t(locale, "adm_no_current")}</p></div>}
          <MeaningBlock m={it.proposed} locale={locale} title={t(locale, "adm_proposed")} />
        </div>
      ) : (
        <div className="max-w-[720px] space-y-3">
          <MeaningBlock m={it.proposed} locale={locale} title={t(locale, "adm_proposed")} />
          <p className="text-[13px] text-steel">{t(locale, "adm_no_current")}</p>
        </div>
      )}

      <div className="space-y-1">
        <h4 className="text-[13px] font-medium text-steel">{fill(t(locale, "adm_evidence_title"), { n: evs.length })}</h4>
        {evs.length ? <Sources list={evs} term={it.canonical} lang={lang} locale={locale} /> : <p className="text-[14px] text-charcoal">{t(locale, "adm_no_evidence")}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="grid w-full grid-cols-3 gap-2 sm:flex sm:w-auto">
          <button type="button" onClick={() => onDecide("approve")} aria-label={fill(t(locale, "adm_action_aria"), { term: it.canonical, action: t(locale, "adm_approve") })} className={BTN_PRIMARY}>{t(locale, "adm_approve")}</button>
          <button type="button" onClick={onSkip} aria-label={fill(t(locale, "adm_action_aria"), { term: it.canonical, action: t(locale, "adm_skip") })} className={BTN_OUTLINE}>{t(locale, "adm_skip")}</button>
          <button type="button" onClick={() => onDecide("reject")} aria-label={fill(t(locale, "adm_action_aria"), { term: it.canonical, action: t(locale, "adm_reject") })} className={BTN_OUTLINE}>{t(locale, "adm_reject")}</button>
        </div>
        <a href={`/dictionary/${encodeURIComponent(it.term_id)}`} target="_blank" rel="noreferrer" className="text-[13px] text-link-blue hover:underline sm:ml-auto">{t(locale, "adm_open_dict")}</a>
      </div>
    </div>
  );
}
