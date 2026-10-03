"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CopyCheck, CopyMeme } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_TEXT = 1000;   // 백엔드 copycheck.MAX_TEXT
const X_LIMIT = 280;
const fieldLabel = "text-[14px] font-medium text-ink";
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);
type ErrorKey = "check_failed" | "check_busy" | "check_need_text" | "check_too_long";
const FIT_TONE = { ok: "good", off: "caution", unsure: "neutral" } as const;

/** 카피 검사 — 문구와 시장을 받아 같은 사이트의 /api/copy-check 로 보낸다(브라우저는 백엔드를 직접 부르지 않는다). 문구는 저장하지 않는다. */
export function CopyCheckForm({ locale, initialRegion }: { locale: Locale; initialRegion: string }) {
  const [text, setText] = useState("");
  const [region, setRegion] = useState(initialRegion);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const [result, setResult] = useState<CopyCheck | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  const submit = async () => {
    if (!text.trim()) {
      setError("check_need_text");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/copy-check", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, region, lang: locale }) });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setError(body?.error === "busy" ? "check_busy" : body?.error === "too_long" ? "check_too_long" : body?.error === "need_text" ? "check_need_text" : "check_failed");
        return;
      }
      setResult(body as CopyCheck);
    } catch {
      setError("check_failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <div>
          <label htmlFor="check-text" className={fieldLabel}>{t(locale, "check_text")}</label>
          <textarea ref={input} id="check-text" value={text} maxLength={MAX_TEXT} rows={5} placeholder={t(locale, "check_placeholder")}
            aria-invalid={error === "check_need_text" ? true : undefined} aria-describedby="check-count"
            onChange={(e) => { setText(e.target.value); if (error === "check_need_text") setError(null); }}
            className={cn("mt-2 block w-full rounded-md border bg-white px-3 py-2 text-[15px] text-ink placeholder:text-steel",
              error === "check_need_text" ? "border-error" : "border-hairline-strong")} />
          <p id="check-count" className="mt-1 text-right text-[12px] text-steel tabular-nums">{fill(t(locale, "check_count"), { n: text.length, max: MAX_TEXT })}</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="check-region" className={fieldLabel}>{t(locale, "check_region")}</label>
            <select id="check-region" value={region} disabled={busy} onChange={(e) => setRegion(e.target.value)}
              className="mt-2 block h-10 rounded-md border border-hairline-strong bg-white px-3 text-[14px] text-ink">
              {TARGET_REGIONS.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
            </select>
          </div>
          <Button type="submit" disabled={busy} className="h-10 rounded-md px-5 text-[14px]">{busy ? t(locale, "check_running") : t(locale, "check_submit")}</Button>
        </div>
        {error && <p role="alert" className="text-[13px] text-error">{t(locale, error)}</p>}
      </form>

      {result && <Result result={result} locale={locale} />}
    </div>
  );
}

function Result({ result, locale }: { result: CopyCheck; locale: Locale }) {
  const where = regionLabel(locale, result.region);
  const fitNote: Record<CopyCheck["fit_source"], StringKey | null> = { gemini: null, local: null, none: "fit_none", busy: "fit_busy", failed: "fit_failed" };
  const note = fitNote[result.fit_source];
  return (
    <section aria-labelledby="check-result" aria-live="polite" className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="check-result" className="text-[16px] font-semibold text-ink">{fill(t(locale, "check_found"), { n: result.memes.length })}</h2>
        <p className={cn("text-[13px] tabular-nums", result.x_length > X_LIMIT ? "text-error" : "text-steel")}>
          {fill(t(locale, "check_x"), { n: result.x_length })}{result.x_length > X_LIMIT && <> · {t(locale, "check_x_over")}</>}
        </p>
      </div>
      {result.unsafe && <StatePanel role="alert">{t(locale, "check_unsafe")}</StatePanel>}
      {result.memes.length ? (
        <ul className="space-y-3">
          {result.memes.map((m) => <MemeRow key={m.term_id} m={m} locale={locale} where={where} region={result.region} />)}
        </ul>
      ) : <StatePanel role="status" action={<Link href="/dictionary" className="text-[14px] text-link-blue hover:underline">{t(locale, "nav_dictionary")}</Link>}>{t(locale, "check_none")}</StatePanel>}
      {result.memes.length > 0 && note && <p className="text-[13px] text-steel">{t(locale, note)}</p>}
    </section>
  );
}

function MemeRow({ m, locale, where, region }: { m: CopyMeme; locale: Locale; where: string; region: string }) {
  return (
    <li className="rounded-md border border-hairline-strong p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <p className="text-[16px] font-semibold text-ink" lang={langTag(m.lang)}>
            {m.canonical}{m.matched.toLowerCase() !== m.canonical.toLowerCase() && <span className="ml-1.5 text-[13px] font-normal text-steel">“{m.matched}”</span>}
          </p>
          <p className="mt-0.5 text-[14px] leading-[1.55] text-charcoal">{locale === "en" ? m.gloss_en : m.gloss_ko}</p>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <StageCell diffusion={m.diffusion} lifecycle={m.lifecycle} locale={locale} />
          <RiskCell item={m} locale={locale} />
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        <p className="text-[13px] font-medium text-charcoal">{t(locale, "check_issues")}</p>
        {m.issues.length ? (
          <ul className="space-y-1 text-[14px] leading-[1.55] text-ink">
            {m.issues.map((i) => (
              <li key={i.code} className="flex gap-2">
                <span aria-hidden className={i.code === "avoid" ? "text-avoid" : "text-caution"}>•</span>
                <span>
                  {fill(t(locale, `issue_${i.code}` as StringKey), { region: where })}
                  {i.code === "caution" && locale === "ko" && i.note && <span className="mt-0.5 block text-[13px] text-steel">{i.note}</span>}
                </span>
              </li>
            ))}
          </ul>
        ) : <p className="text-[14px] text-good">{t(locale, "check_ok")}</p>}
      </div>

      {m.fit && (
        <div className="mt-3 space-y-1">
          <p className="text-[13px] font-medium text-charcoal">{t(locale, "fit_title")}</p>
          <p className="flex flex-wrap items-center gap-2 text-[14px] text-ink">
            <StatusBadge tone={FIT_TONE[m.fit]}>{t(locale, `fit_${m.fit}`)}</StatusBadge>
            {m.fit_note && <span className="text-charcoal">{m.fit_note}</span>}
          </p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
        <Link href={`/dictionary/${encodeURIComponent(m.term_id)}?regions=${region}`} className="text-link-blue hover:underline">{t(locale, "check_to_dictionary")}</Link>
        {m.issues.some((i) => i.code !== "caution" && i.code !== "undecided") && (
          <Link href={`/recommend?regions=${region}`} className="text-link-blue hover:underline">{t(locale, "check_to_kit")}</Link>
        )}
      </div>
    </li>
  );
}
