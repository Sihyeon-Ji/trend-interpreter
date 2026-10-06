"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ChipMark } from "@/components/chip-mark";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { Button } from "@/components/ui/button";
import { glossFor } from "@/lib/gloss";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L, regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CampaignTone, CopyCheck, FitCategory, GenerationResult, PosterResult, RecommendItem, RecommendResult } from "@/lib/types";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

/* 만들기 (Plan 20): 제품과 시장 → 나라별 초안 → 검토와 승인. 순위는 백엔드 규칙(/recommend), 카피는 모델(/generate)이 쓰고
   규칙 검사를 두 번 거친다(/generate 안에서 한 번, /copy-check 로 한 번 더 — 화면에 보이는 검사). 포스터는 구성안만 규칙이 만들고
   그림 생성이 켜져 있을 때만 그림이 온다. 백엔드는 모델 요청을 한 인스턴스에 둘까지만 받으므로 시장은 차례로 만든다. */

const MAX_MARKETS = 3;
const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);
const fieldLabel = "block text-[14px] font-semibold text-ink";

type Status = "wait" | "writing" | "checking" | "poster" | "done" | "failed" | "none";
interface Column {
  market: string;
  status: Status;
  pick: RecommendItem | null;
  alts: RecommendItem[];
  gen: GenerationResult | null;
  check: CopyCheck | null;
  poster: PosterResult | null;
  approved: boolean;
}
const STATUS_KEY: Record<Status, StringKey> = {
  wait: "col_wait", writing: "col_writing", checking: "col_checking", poster: "col_poster_busy", done: "col_done", failed: "col_failed", none: "col_none",
};

/** 표제어를 열 폭에 맞는 크기로 — 보이는 길이(한글·가나·한자 1, 라틴 0.56)로 네 단계. 줄은 낱말 사이에서만 바뀐다. */
function wordSize(name: string) {
  const w = [...name].reduce((n, ch) => n + (/[ᄀ-ᇿ぀-ヿ㐀-鿿가-힯]/.test(ch) ? 1 : ch === " " ? 0.3 : 0.56), 0);
  return w <= 4.5 ? "text-[56px]" : w <= 7 ? "text-[44px]" : w <= 11 ? "text-[34px]" : "text-[26px]";
}

async function post<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

/** 진짜 순서라 번호를 붙인다. 지금 단계는 먹 글자 + 아래 2px 선, 지난 단계는 먹, 아직은 회색. */
function Steps({ locale, current }: { locale: Locale; current: 1 | 2 | 3 }) {
  const items = [t(locale, "make_step1"), t(locale, "make_step2"), t(locale, "make_step3")];
  return (
    <ol aria-label={t(locale, "make_steps")} className="flex flex-wrap gap-x-8 gap-y-2 border-b border-hairline text-[14px]">
      {items.map((s, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        return (
          <li key={n} aria-current={n === current ? "step" : undefined}
            className={cn("-mb-px flex items-baseline gap-2 pb-3", n === current ? "border-b-2 border-ink font-semibold text-ink" : n < current ? "text-ink" : "text-steel")}>
            <span className="tabular-nums">{n}</span>{s}
          </li>
        );
      })}
    </ol>
  );
}

/** 오른쪽 안내 — 만드는 순서 다섯 단계. 화면이 하는 일과 사람이 하는 일을 처음부터 밝힌다. */
function How({ locale }: { locale: Locale }) {
  const rows: [StringKey, StringKey][] = [["make_how1", "make_how1_body"], ["make_how2", "make_how2_body"], ["make_how3", "make_how3_body"],
    ["make_how4", "make_how4_body"], ["make_how5", "make_how5_body"]];
  return (
    <aside aria-labelledby="make-how" className="rubric">
      <h2 id="make-how" className="text-[18px] font-bold tracking-[-0.01em] text-ink">{t(locale, "make_how")}</h2>
      <ol className="mt-4 divide-y divide-hairline">
        {rows.map(([title, body], i) => (
          <li key={title} className="grid grid-cols-[32px_minmax(0,1fr)] gap-x-2 py-3.5">
            <span className="text-[20px] leading-[1.2] font-extrabold text-ink tabular-nums">{i + 1}</span>
            <div>
              <p className="text-[15px] font-semibold text-ink">{t(locale, title)}</p>
              <p className="mt-0.5 text-[14px] leading-[1.6] text-charcoal">{t(locale, body)}</p>
            </div>
          </li>
        ))}
      </ol>
      <dl className="mt-5 space-y-2 border-t border-hairline pt-4 text-[14px]">
        <div><dt className="inline text-charcoal">{t(locale, "make_have_copy")} </dt><dd className="inline"><Link href="/check" className="text-link-blue underline underline-offset-[3px] decoration-hairline-strong hover:decoration-link-blue">{t(locale, "make_go_check")}</Link></dd></div>
        <div><dt className="inline text-charcoal">{t(locale, "make_or_browse")} </dt><dd className="inline"><Link href="/trends" className="text-link-blue underline underline-offset-[3px] decoration-hairline-strong hover:decoration-link-blue">{t(locale, "make_go_browse")}</Link></dd></div>
      </dl>
    </aside>
  );
}

/** 열 하나 = 시장 하나. 위에서부터 고른 밈(포스터 낱말) → 다른 후보 → 카피 → 다시 검사 → 포스터 → 승인. */
function MarketColumn({ col, locale, feelings, onSwap, onRetry, onApprove }: {
  col: Column; locale: Locale; feelings: string[]; onSwap: (id: string) => void; onRetry: () => void; onApprove: () => void;
}) {
  const labels = L(locale);
  const busy = col.status === "wait" || col.status === "writing" || col.status === "checking" || col.status === "poster";
  const copy = col.gen?.copies.find((c) => c.platform === "instagram") ?? col.gen?.copies[0];
  const x = col.gen?.copies.find((c) => c.platform === "x");
  const headline = col.gen?.thumbnail?.headline ?? copy?.text.split(/[.!?。！？\n]/)[0] ?? "";
  const issues = col.check?.memes.flatMap((m) => m.issues.map((i) => ({ m, i }))) ?? [];
  const fits = col.check?.memes.filter((m) => m.fit && m.fit !== "ok") ?? [];
  const name = regionLabel(locale, col.market);
  return (
    <section aria-labelledby={`col-${col.market}`} aria-busy={busy} className="min-w-0 border-t-[3px] border-ink pt-3 md:px-6 md:first:pl-0 md:last:pr-0">
      <header className="flex items-baseline justify-between gap-3">
        <h3 id={`col-${col.market}`} className="text-[18px] font-bold text-ink">{name}</h3>
        <p role="status" className={cn("text-[13px]", col.status === "done" ? "text-good" : col.status === "failed" ? "text-error" : "text-steel")}>
          {col.status === "none" ? "" : t(locale, STATUS_KEY[col.status])}
        </p>
      </header>

      {col.status === "none" || !col.pick ? (
        <div className="mt-6 space-y-2 text-[14px] leading-[1.6]">
          <p className="text-charcoal">{t(locale, "col_none")}</p>
          <Link href={`/trends?regions=${col.market}`} className="text-link-blue underline decoration-hairline-strong underline-offset-[3px] hover:decoration-link-blue">
            {fill(t(locale, "col_browse"), { region: name })}
          </Link>
        </div>
      ) : (
        <>
          <div className="mt-6">
            <Link href={`/dictionary/${encodeURIComponent(col.pick.term_id)}?regions=${col.market}&from=recommend`} target="_blank" rel="noopener" className="group block">
              <span lang={langTag(col.pick.lang)} className={cn("poster-word block group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4", wordSize(col.pick.canonical))}>{col.pick.canonical}</span>
            </Link>
            <p className="mt-3 text-[15px] leading-[1.6] text-ink">{glossFor(col.pick, locale)}</p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
              <StageCell diffusion={col.pick.diffusion} lifecycle={col.pick.lifecycle} locale={locale} />
              <RiskCell item={col.pick} locale={locale} />
              {col.pick.evidences.length > 0 && <span className="text-[13px] text-steel tabular-nums">{fill(t(locale, "col_sources"), { n: col.pick.evidences.length })}</span>}
            </div>
          </div>

          {col.alts.length > 0 && (
            <div className="mt-5 border-t border-hairline pt-3">
              <p className="text-[13px] font-semibold text-charcoal">{t(locale, "col_alternatives")}</p>
              <ul className="mt-1.5">
                {col.alts.map((a) => (
                  <li key={a.term_id} className="flex items-baseline justify-between gap-3 py-1">
                    <span lang={langTag(a.lang)} className="min-w-0 truncate text-[15px] font-semibold text-ink">{a.canonical}</span>
                    <button type="button" disabled={busy} onClick={() => onSwap(a.term_id)}
                      className="shrink-0 text-[13px] text-link-blue underline decoration-hairline-strong underline-offset-[3px] hover:decoration-link-blue disabled:text-steel disabled:no-underline">
                      {t(locale, "col_use")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-6 border-t border-hairline pt-4">
            <h4 className="text-[13px] font-semibold text-charcoal">{t(locale, "col_copy")}</h4>
            {copy ? (
              <div className="mt-2 space-y-3">
                <p lang={col.gen ? langTag(col.gen.language) : undefined} className="text-[16px] leading-[1.6] text-ink">{copy.text}
                  {copy.hashtags?.length ? <span className="text-steel"> {copy.hashtags.map((h) => `#${h}`).join(" ")}</span> : null}</p>
                {x && <p lang={col.gen ? langTag(col.gen.language) : undefined} className="text-[14px] leading-[1.6] text-charcoal"><span className="mr-2 text-[12px] text-steel">X</span>{x.text}</p>}
              </div>
            ) : <p className="mt-2 text-[14px] text-steel">{busy ? "…" : t(locale, "col_failed")}</p>}
          </div>

          {(col.check || col.status === "checking") && (
            <div className="mt-4">
              <h4 className="text-[13px] font-semibold text-charcoal">{t(locale, "col_check")}</h4>
              {col.check && (issues.length === 0 && fits.length === 0 ? (
                <p className="mt-1.5 text-[14px] text-good">{t(locale, "check_ok")}</p>
              ) : (
                <ul className="mt-1.5 space-y-1.5 text-[14px] leading-[1.55]">
                  {issues.map(({ m, i }, k) => (
                    <li key={`${m.term_id}-${i.code}-${k}`} className={cn(i.code === "avoid" ? "text-avoid" : i.code === "caution" ? "text-caution" : "text-charcoal")}>
                      <span lang={langTag(m.lang)} className="font-semibold">{m.matched}</span> {fill(t(locale, `issue_${i.code}` as StringKey), { region: name })}
                    </li>
                  ))}
                  {fits.map((m) => (
                    <li key={`fit-${m.term_id}`} className="text-charcoal">
                      <StatusBadge tone={m.fit === "off" ? "caution" : "neutral"}>{t(locale, `fit_${m.fit}` as StringKey)}</StatusBadge>{" "}
                      {m.fit_note}
                    </li>
                  ))}
                </ul>
              ))}
            </div>
          )}

          <div className="mt-6 border-t border-hairline pt-4">
            <h4 className="text-[13px] font-semibold text-charcoal">{t(locale, "col_poster")}</h4>
            <figure className="mt-2 max-w-[360px]">
              <div className="relative aspect-[4/5] w-full overflow-hidden border border-hairline-strong bg-surface">
                {col.poster?.images[0] ? (
                  // 생성 그림은 data URL 이라 next/image 최적화를 쓰지 않는다
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={col.poster.images[0]} alt="" className="absolute inset-0 h-full w-full object-cover" />
                ) : null}
                {headline && (
                  <p lang={col.gen ? langTag(col.gen.language) : undefined}
                    className="poster-word absolute inset-x-0 top-0 bg-background/92 px-4 pt-4 pb-3 text-[26px]">{headline}</p>
                )}
                {!col.poster?.images[0] && col.poster && (
                  <dl className="absolute inset-x-4 bottom-4 space-y-1 text-[12px] leading-[1.45] text-charcoal">
                    {feelings.length > 0 && <div><dt className="inline text-steel">{t(locale, "col_poster_mood")} </dt><dd className="inline">{feelings.join(", ")}</dd></div>}
                    {col.poster.plan.colors.length > 0 && <div><dt className="inline text-steel">{t(locale, "col_poster_colors")} </dt><dd className="inline">{col.poster.plan.colors.join(", ")}</dd></div>}
                  </dl>
                )}
              </div>
              {col.poster && !col.poster.enabled && <figcaption className="mt-1.5 text-[12px] text-steel">{t(locale, "col_poster_off")}</figcaption>}
            </figure>
          </div>

          {col.gen && col.gen.dropped.length > 0 && (
            <details className="mt-4 text-[13px] text-charcoal">
              <summary className="cursor-pointer text-steel">{fill(t(locale, "col_dropped"), { n: col.gen.dropped.length })}</summary>
              <ul className="mt-1.5 list-disc space-y-1 pl-5">{col.gen.dropped.map((d) => <li key={d.id}>{t(locale, `gen_drop_${d.code}` as StringKey)}</li>)}</ul>
            </details>
          )}
        </>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-hairline pt-4">
        {col.status === "done" && (
          <button type="button" aria-pressed={col.approved} onClick={onApprove}
            className={cn("inline-flex h-10 items-center gap-2 rounded-lg border px-4 text-[14px] font-medium",
              col.approved ? "border-2 border-link-blue px-[15px] text-ink" : "border-hairline-strong text-ink hover:border-ink")}>
            <ChipMark on={col.approved} />{col.approved ? t(locale, "col_approved") : t(locale, "col_approve")}
          </button>
        )}
        {(col.status === "failed" || col.status === "done") && (
          <button type="button" onClick={onRetry} className="text-[13px] text-link-blue underline decoration-hairline-strong underline-offset-[3px] hover:decoration-link-blue">{t(locale, "col_retry")}</button>
        )}
        {col.pick && col.status === "done" && (
          <Link href={`/recommend?term=${encodeURIComponent(col.pick.term_id)}&regions=${col.market}`} className="text-[13px] text-link-blue underline decoration-hairline-strong underline-offset-[3px] hover:decoration-link-blue">{t(locale, "col_more")}</Link>
        )}
      </div>
      {col.status !== "none" && col.pick && <p className="sr-only">{labels.lifecycle[col.pick.lifecycle]}</p>}
    </section>
  );
}

export function MakeFlow({ locale, initialMarkets, sample }: { locale: Locale; initialMarkets: string[]; sample: boolean }) {
  const labels = L(locale);
  const categories = Object.keys(labels.fitCategory) as FitCategory[];
  const [markets, setMarkets] = useState<string[]>(initialMarkets);
  const [category, setCategory] = useState<FitCategory | "">("");
  const [tone, setTone] = useState<CampaignTone>("friendly");
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [formError, setFormError] = useState<StringKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [cols, setCols] = useState<Column[]>([]);
  const [editing, setEditing] = useState(true);
  const [copied, setCopied] = useState(false);
  const run = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const resultsTitle = useRef<HTMLHeadingElement>(null);

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => () => abort.current?.abort(), []);

  const toggleMarket = (m: string) => {
    setFormError(null);
    setMarkets((cur) => (cur.includes(m) ? cur.filter((x) => x !== m) : cur.length >= MAX_MARKETS ? (setFormError("make_markets_max"), cur) : [...cur, m]));
  };
  const pickPhoto = (f: File | null) => {
    setFormError(null);
    if (f && (f.size > MAX_IMAGE || !["image/jpeg", "image/png", "image/webp"].includes(f.type))) {
      setFormError(f.size > MAX_IMAGE ? "rec_too_big" : "rec_bad_type");
      setInputKey((k) => k + 1);
      return;
    }
    if (!f) setInputKey((k) => k + 1);
    setPhoto(f ? { file: f, url: URL.createObjectURL(f) } : null);
  };
  const patch = (market: string, p: Partial<Column>) => setCols((cur) => cur.map((c) => (c.market === market ? { ...c, ...p } : c)));

  /** 시장 하나의 초안: 카피 → 다시 검사 → 포스터. 앞 단계가 실패하면 그 열만 실패로 둔다. */
  const draft = async (market: string, item: RecommendItem, rec: RecommendResult, seq: number, signal: AbortSignal) => {
    const live = () => seq === run.current;
    patch(market, { status: "writing", gen: null, check: null, poster: null, approved: false });
    try {
      const gen = await post<GenerationResult>("/api/generate", { term_ids: [item.term_id], brief: rec.brief, region: market, tone: rec.tone, lang: locale }, signal);
      if (!live()) return;
      patch(market, { gen, status: "checking" });
      const first = gen.copies.find((c) => c.platform === "instagram") ?? gen.copies[0];
      const check = first ? await post<CopyCheck>("/api/copy-check", { text: first.text, region: market, lang: locale }, signal).catch(() => null) : null;
      if (!live()) return;
      patch(market, { check, status: "poster" });
      const poster = await post<PosterResult>("/api/poster", { market, brief: rec.brief, term_ids: [item.term_id] }, signal).catch(() => null);
      if (!live()) return;
      patch(market, { poster, status: "done" });
    } catch {
      if (live() && !signal.aborted) patch(market, { status: "failed" });
    }
  };

  const submit = async () => {
    if (!markets.length) { setFormError("make_markets_need"); return; }
    if (!text.trim() && !photo) { setFormError("rec_need_input"); return; }
    const seq = ++run.current;
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setBusy(true);
    setFormError(null);
    const body = new FormData();
    body.set("text", text.trim());
    body.set("tone", tone);
    body.set("lang", locale);
    body.set("regions", markets.join(","));
    if (category) body.set("category", category);
    if (photo) body.set("image", photo.file);
    let rec: RecommendResult | null = null;
    try {
      const res = await fetch("/api/recommend", { method: "POST", body, signal: ctrl.signal });
      const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
      if (res.ok) rec = json;
      else setFormError(json.error === "busy" ? "make_busy" : json.error === "too_big" ? "rec_too_big" : json.error === "bad_type" ? "rec_bad_type" : "make_failed");
    } catch {
      if (!ctrl.signal.aborted) setFormError("make_failed");
    }
    setBusy(false);
    if (!rec || seq !== run.current) return;
    // 시장마다 그 나라 말로 쓸 수 있는 밈만(백엔드 generate 가 정한 write_regions) — 규칙 순위 그대로, 첫째가 초안, 다음 둘이 다른 후보
    const next: Column[] = markets.map((m) => {
      const fit = rec!.items.filter((i) => i.write_regions.includes(m));
      return { market: m, status: fit.length ? "wait" : "none", pick: fit[0] ?? null, alts: fit.slice(1, 3), gen: null, check: null, poster: null, approved: false };
    });
    setResult(rec);
    setCols(next);
    setEditing(false);
    setTimeout(() => resultsTitle.current?.focus(), 0);
    for (const c of next) {
      if (seq !== run.current) return;
      if (c.pick) await draft(c.market, c.pick, rec, seq, ctrl.signal);
    }
  };

  const redo = async (market: string, termId?: string) => {
    if (!result) return;
    const col = cols.find((c) => c.market === market);
    const pool = result.items.filter((i) => i.write_regions.includes(market));
    const item = termId ? pool.find((i) => i.term_id === termId) : col?.pick;
    if (!item) return;
    patch(market, { pick: item, alts: pool.filter((i) => i.term_id !== item.term_id).slice(0, 2) });
    await draft(market, item, result, run.current, (abort.current ?? new AbortController()).signal);
  };

  const approved = cols.filter((c) => c.approved);
  const copyApproved = async () => {
    const lines = approved.map((c) => {
      const cp = c.gen?.copies.find((x) => x.platform === "instagram") ?? c.gen?.copies[0];
      return `[${regionLabel(locale, c.market)}] ${cp?.text ?? ""}${cp?.hashtags?.length ? ` ${cp.hashtags.map((h) => `#${h}`).join(" ")}` : ""}`;
    });
    try { await navigator.clipboard.writeText(lines.join("\n\n")); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* 클립보드가 막힌 브라우저 — 글은 화면에 그대로 있다 */ }
  };

  const step: 1 | 2 | 3 = editing ? 1 : approved.length ? 3 : 2;
  // 시장 칩의 잘못은 칩 바로 아래에 — 맨 아래 단추 옆에 나오면 눌러도 반응이 없는 것처럼 보였다
  const marketError = formError === "make_markets_max" || formError === "make_markets_need";
  const form = (
    <form aria-busy={busy} onSubmit={(e) => { e.preventDefault(); void submit(); }} className="divide-y divide-hairline border-t border-hairline">
      <fieldset className="py-5">
        <legend className={fieldLabel}>{t(locale, "make_markets")}</legend>
        <p className="mt-1 text-[13px] text-steel">{t(locale, "make_markets_hint")}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {TARGET_REGIONS.map((r) => {
            const on = markets.includes(r);
            return (
              <label key={r} className={cn(chipClass(on), "cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring")}>
                <input type="checkbox" className="sr-only" checked={on} onChange={() => toggleMarket(r)} />
                <ChipMark on={on} />{regionLabel(locale, r)}
                {on && <span className="text-[12px] text-steel tabular-nums">{markets.indexOf(r) + 1}</span>}
              </label>
            );
          })}
        </div>
        {marketError && <p role="alert" className="mt-2 text-[14px] text-error">{t(locale, formError!)}</p>}
      </fieldset>

      <div className="grid gap-6 py-5 sm:grid-cols-2">
        <div>
          <label htmlFor="make-category" className={fieldLabel}>{t(locale, "make_category")}</label>
          <select id="make-category" value={category} onChange={(e) => setCategory(e.target.value as FitCategory | "")}
            className="mt-2 h-10 w-full rounded-lg border border-hairline-strong bg-background px-3 text-[14px] text-ink">
            <option value="">{t(locale, "make_category_auto")}</option>
            {categories.map((c) => <option key={c} value={c}>{labels.fitCategory[c]}</option>)}
          </select>
        </div>
        <fieldset>
          <legend className={fieldLabel}>{t(locale, "make_tone")}</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {TONES.map((tn) => (
              <label key={tn} className={cn(chipClass(tone === tn), "cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring")}>
                <input type="radio" name="make-tone" className="sr-only" checked={tone === tn} onChange={() => setTone(tn)} />
                <ChipMark on={tone === tn} round />{labels.campaignTone[tn]}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="py-5">
        <label htmlFor="make-pitch" className={fieldLabel}>{t(locale, "make_pitch")}</label>
        <textarea id="make-pitch" value={text} maxLength={500} rows={3} placeholder={t(locale, "rec_copy_ph")}
          onChange={(e) => { setText(e.target.value); if (formError === "rec_need_input") setFormError(null); }}
          className="mt-2 w-full rounded-lg border border-hairline-strong bg-background px-3 py-2.5 text-[15px] leading-[1.6] text-ink placeholder:text-steel" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <input key={inputKey} id="make-photo" type="file" accept="image/jpeg,image/png,image/webp" className="peer sr-only" onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
          <label htmlFor="make-photo" className="inline-flex h-10 cursor-pointer items-center rounded-lg border border-hairline-strong px-3 text-[14px] font-medium text-ink hover:border-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring">
            {photo ? t(locale, "rec_photo_change") : t(locale, "rec_photo_pick")}
          </label>
          {photo && (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photo.url} alt={t(locale, "rec_photo_alt")} className="h-10 w-10 border border-hairline object-cover" />
              <button type="button" onClick={() => pickPhoto(null)} className="text-[13px] text-link-blue underline decoration-hairline-strong underline-offset-[3px]">{t(locale, "rec_photo_remove")}</button>
            </>
          )}
          <span className="text-[13px] text-steel">{t(locale, "rec_photo_hint")}</span>
        </div>
        {sample && <p className="mt-3 text-[13px] text-charcoal">{t(locale, "rec_brief_sample")}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-4 py-5">
        <Button type="submit" disabled={busy} className="h-11 rounded-lg px-6 text-[15px]">{busy ? t(locale, "make_reading") : t(locale, "make_submit")}</Button>
        {formError && !marketError && <p role="alert" className="text-[14px] text-error">{t(locale, formError)}</p>}
      </div>
    </form>
  );

  return (
    <div className="space-y-8">
      <Steps locale={locale} current={step} />

      {editing ? (
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_340px]">
          {form}
          <How locale={locale} />
        </div>
      ) : result && (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-3 border-b border-hairline pb-4">
            <dl className="flex flex-wrap gap-x-8 gap-y-1 text-[14px]">
              <div><dt className="inline text-steel">{t(locale, "rec_brief_product")} </dt><dd className="inline font-semibold text-ink">{result.brief?.product ?? text}</dd></div>
              {result.brief && <div><dt className="inline text-steel">{t(locale, "make_category")} </dt><dd className="inline text-ink">{labels.fitCategory[result.brief.category]}</dd></div>}
              <div><dt className="inline text-steel">{t(locale, "make_tone")} </dt><dd className="inline text-ink">{labels.campaignTone[result.tone]}</dd></div>
            </dl>
            <button type="button" onClick={() => { abort.current?.abort(); run.current++; setEditing(true); }}
              className="text-[14px] text-link-blue underline decoration-hairline-strong underline-offset-[3px] hover:decoration-link-blue">{t(locale, "rec_edit")}</button>
          </div>

          {result.brief && (
            <details className="text-[14px]">
              <summary className="cursor-pointer text-charcoal">{t(locale, "make_read")}</summary>
              <dl className="mt-2 grid max-w-[720px] grid-cols-[88px_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-charcoal">
                {result.brief.feelings.length > 0 && <><dt className="text-steel">{t(locale, "rec_brief_feelings")}</dt><dd>{result.brief.feelings.map((f) => labels.feeling[f]).join(", ")}</dd></>}
                {!!result.brief.values?.length && <><dt className="text-steel">{t(locale, "rec_brief_values")}</dt><dd>{result.brief.values.join(", ")}</dd></>}
                {result.brief.scene && <><dt className="text-steel">{t(locale, "rec_brief_scene")}</dt><dd>{result.brief.scene}</dd></>}
              </dl>
            </details>
          )}

          <h2 ref={resultsTitle} tabIndex={-1} className="sr-only">{t(locale, "make_step2")}</h2>
          <div className={cn("grid gap-12 md:gap-0 md:divide-x md:divide-hairline", cols.length === 1 ? "md:grid-cols-1 md:max-w-[520px]" : cols.length === 2 ? "md:grid-cols-2" : "md:grid-cols-3")}>
            {cols.map((c) => (
              <MarketColumn key={c.market} col={c} locale={locale} feelings={(result.brief?.feelings ?? []).map((f) => labels.feeling[f])}
                onSwap={(id) => void redo(c.market, id)} onRetry={() => void redo(c.market)}
                onApprove={() => patch(c.market, { approved: !c.approved })} />
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 border-t-[3px] border-ink pt-4">
            <div>
              <p className="text-[15px] font-semibold text-ink tabular-nums">{fill(t(locale, "make_approved"), { n: approved.length, m: cols.filter((c) => c.status !== "none").length })}</p>
              <p className="text-[13px] text-steel">{t(locale, "make_local_note")}</p>
            </div>
            <div className="flex items-center gap-3">
              {copied && <span role="status" className="text-[13px] text-good">{t(locale, "make_copied")}</span>}
              <Button type="button" disabled={!approved.length} onClick={() => void copyApproved()} className="h-11 rounded-lg px-6 text-[15px]">{t(locale, "make_copy_approved")}</Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
