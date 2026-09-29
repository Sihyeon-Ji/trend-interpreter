"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { GenerationView } from "@/components/generation-view";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, listJoin, regionLabel, sourceName } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CampaignTone, GenerationResult, RecommendItem, RecommendResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
type ErrorKey = "rec_need_input" | "rec_too_big" | "rec_bad_type" | "rec_failed";
const ERRORS: Record<string, ErrorKey> = { need_input: "rec_need_input", too_big: "rec_too_big", bad_type: "rec_bad_type" };

/** 모델이 쓴 이유가 없으면(사전 뜻과 겹치지 않아 버렸거나 모델이 꺼져 있으면) 겹친 낱말로 규칙 문장을 만든다. */
function matchLine(locale: Locale, it: RecommendItem, category: string) {
  const labels = L(locale);
  const parts: string[] = [];
  if (it.matched_category) parts.push(`${t(locale, "rec_match_category")} ${category}`);
  else if (it.any_category) parts.push(t(locale, "rec_match_any"));
  if (it.matched_feelings.length) parts.push(`${t(locale, "rec_match_feeling")} ${listJoin(locale, it.matched_feelings.map((f) => labels.feeling[f]))}`);
  return parts.join(" · ");
}

export function RecommendForm({ locale, initialRegions }: { locale: Locale; initialRegions: string[] }) {
  const labels = L(locale);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [regions, setRegions] = useState<string[]>(initialRegions);
  const [tone, setTone] = useState<CampaignTone>("friendly");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const [result, setResult] = useState<RecommendResult | null>(null);
  // 만들기(Plan 08): 추천에서 밈을 최대 3개 고르고, 결과물을 쓸 지역 하나를 정한다
  const [picked, setPicked] = useState<string[]>([]);
  const [genRegion, setGenRegion] = useState<string>("");
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState<"gen_failed" | "gen_need_pick" | null>(null);
  const [gen, setGen] = useState<GenerationResult | null>(null);

  // 미리보기 주소는 이 탭 안에서만 산다 — 사진을 바꾸거나 빼거나 화면을 떠나면 돌려준다
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);

  const pick = (f: File | null) => {
    setError(null);
    if (f && f.size > MAX_IMAGE) { setError("rec_too_big"); return; }
    if (f && !["image/jpeg", "image/png", "image/webp"].includes(f.type)) { setError("rec_bad_type"); return; }
    setPhoto(f ? { file: f, url: URL.createObjectURL(f) } : null);
  };
  const toggleRegion = (r: string) => setRegions((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const submit = async () => {
    if (!text.trim() && !photo) { setError("rec_need_input"); return; }
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.set("text", text.trim());
    body.set("tone", tone);
    body.set("lang", locale);
    body.set("regions", regions.join(","));
    if (photo) body.set("image", photo.file);
    try {
      const res = await fetch("/api/recommend", { method: "POST", body });
      const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
      if (!res.ok) setError(ERRORS[json.error ?? ""] ?? "rec_failed");
      else { setResult(json); setPicked([]); setGen(null); setGenError(null); setGenRegion(json.regions[0] ?? "KR"); }
    } catch {
      setError("rec_failed");
    }
    setBusy(false);
  };

  const togglePick = (id: string) => setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < 3 ? [...cur, id] : cur));
  // 결과물을 쓸 지역은 고른 밈이 실제로 쓰이는 곳만 — 한국 밈으로 일본 카피를 만들지 않는다(백엔드도 거른다)
  const covered = result ? result.regions.filter((r) => picked.some((id) => result.items.find((i) => i.term_id === id)?.regions.includes(r))) : [];
  const regionOptions = picked.length ? covered : result?.regions ?? [];
  const chosenRegion = regionOptions.includes(genRegion) ? genRegion : regionOptions[0] ?? "";
  const make = async () => {
    if (!result) return;
    if (!picked.length) { setGenError("gen_need_pick"); return; }
    setGenBusy(true);
    setGenError(null);
    try {
      const res = await fetch("/api/generate", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ term_ids: picked, brief: result.brief, region: chosenRegion, tone: result.tone, lang: locale }) });
      if (!res.ok) setGenError("gen_failed");
      else setGen((await res.json()) as GenerationResult);
    } catch {
      setGenError("gen_failed");
    }
    setGenBusy(false);
  };

  const field = "mt-1 block w-full rounded-[4px] border border-hairline bg-white px-3 py-2 text-[15px] text-ink";
  const chip = (on: boolean) => cn("rounded-full border px-3 py-1 text-[13px] whitespace-nowrap",
    on ? "border-primary bg-primary text-primary-foreground" : "border-hairline-strong text-charcoal hover:border-ink hover:text-ink");
  const category = result ? labels.fitCategory[result.brief.category] : "";

  return (
    <div className="space-y-10">
      <form className="max-w-[640px] space-y-5" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <div>
          <label htmlFor="rec-photo" className="block text-[13px] text-steel">{t(locale, "rec_photo")}</label>
          <input id="rec-photo" type="file" accept="image/jpeg,image/png,image/webp" className="mt-1 block text-[14px] text-charcoal"
            onChange={(e) => pick(e.target.files?.[0] ?? null)} />
          <p className="mt-1 text-[12px] text-steel">{t(locale, "rec_photo_hint")}</p>
          {photo && (
            <div className="mt-2 flex items-end gap-3">
              {/* 올린 사진 미리보기 — 브라우저 안의 임시 주소라 next/image 최적화를 쓰지 않는다 */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photo.url} alt="" className="h-24 w-24 rounded-[4px] border border-hairline object-cover" />
              <button type="button" className="text-[13px] text-link-blue hover:underline" onClick={() => pick(null)}>{t(locale, "rec_photo_remove")}</button>
            </div>
          )}
        </div>
        <label className="block text-[13px] text-steel">
          {t(locale, "rec_copy")} <span className="tabular-nums">({text.length}/500)</span>
          <textarea id="rec-copy" value={text} maxLength={500} rows={3} onChange={(e) => setText(e.target.value)} placeholder={t(locale, "rec_copy_ph")} className={field} />
        </label>
        <fieldset>
          <legend className="text-[13px] text-steel">{t(locale, "rec_regions")}</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {TARGET_REGIONS.map((r) => (
              <button key={r} type="button" aria-pressed={regions.includes(r)} className={chip(regions.includes(r))} onClick={() => toggleRegion(r)}>{regionLabel(locale, r)}</button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-[13px] text-steel">{t(locale, "rec_tone")}</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            {TONES.map((x) => (
              <button key={x} type="button" aria-pressed={tone === x} className={chip(tone === x)} onClick={() => setTone(x)}>{labels.campaignTone[x]}</button>
            ))}
          </div>
        </fieldset>
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={busy} className="rounded-lg px-4">{busy ? t(locale, "rec_busy") : t(locale, "rec_submit")}</Button>
          {error && <p role="alert" className="text-[13px] text-error">{t(locale, error)}</p>}
        </div>
      </form>

      {result && (
        <section aria-labelledby="rec-results" className="space-y-5">
          <div className="rounded-lg border border-hairline p-4">
            <h2 className="text-[14px] font-semibold text-ink">{t(locale, "rec_brief")}</h2>
            <p className="mt-1 text-[15px] text-ink">{result.brief.product} <span className="text-[13px] text-steel">· {category}</span></p>
            <p className="mt-1 text-[13px] text-charcoal">{listJoin(locale, result.brief.feelings.map((f) => labels.feeling[f]))}{result.brief.values?.length ? ` · ${result.brief.values.join(", ")}` : ""}</p>
            {result.brief_source === "sample" && <p className="mt-2 text-[13px] text-steel">{t(locale, "rec_brief_sample")}</p>}
          </div>
          <div>
            <h2 id="rec-results" className="text-[18px] font-semibold text-ink">{t(locale, "rec_results")} <span className="ml-1 text-[14px] font-normal text-steel">{result.items.length}</span></h2>
            <p className="mt-0.5 text-[13px] text-steel">{listJoin(locale, result.regions.map((r) => regionLabel(locale, r)))} · {labels.campaignTone[result.tone]}</p>
          </div>
          {result.items.length === 0 ? <p className="text-[14px] text-steel">{t(locale, "rec_none")}</p> : (
            <ol className="space-y-3">
              {result.items.map((it, n) => (
                <li key={it.term_id}>
                  <article className="rounded-lg border border-hairline p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 break-words text-[16px] font-semibold text-ink"><span className="mr-2 text-steel tabular-nums">{n + 1}</span>{it.canonical}</h3>
                      {(it.risk_level === "caution") && <span className="shrink-0 rounded border border-hairline-strong px-1.5 text-[12px] leading-[20px] text-charcoal">{t(locale, "risk_caution")}</span>}
                    </div>
                    <p className="mt-1 text-[14px] leading-[1.55] text-charcoal">{locale === "ko" ? it.gloss_ko : it.gloss_en}</p>
                    <p className="mt-1 text-[12px] text-steel">{[it.diffusion ? t(locale, `diffusion_${it.diffusion}`) : null, labels.lifecycle[it.lifecycle]].filter(Boolean).join(" · ")}</p>
                    <p className="mt-2 text-[14px] text-ink">
                      <span className="text-steel">{it.reason ? t(locale, "rec_why") : t(locale, "rec_match")}: </span>
                      {it.reason ?? matchLine(locale, it, category)}
                    </p>
                    {it.risk_level === "caution" && <p className="mt-1 text-[12px] text-charcoal">{t(locale, "risk_caution_why")}</p>}
                    <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12px]">
                      <label className="flex items-center gap-1.5 text-charcoal">
                        <input type="checkbox" checked={picked.includes(it.term_id)} disabled={!picked.includes(it.term_id) && picked.length >= 3}
                          onChange={() => togglePick(it.term_id)} />
                        {t(locale, "gen_pick")}
                      </label>
                      <Link href={`/dictionary/${it.term_id}`} className="text-link-blue hover:underline">{t(locale, "rec_open_term")}</Link>
                      {it.evidences.map((e) => (
                        <a key={e.url} href={e.url} target="_blank" rel="noreferrer" className="text-steel hover:text-ink hover:underline">
                          {sourceName(locale, e.source_domain)} · {fmtDate(e.observed_at)}
                        </a>
                      ))}
                    </div>
                  </article>
                </li>
              ))}
            </ol>
          )}
          <p className="text-[12px] text-steel">{t(locale, "rec_note")}</p>
          {result.items.length > 0 && (
            <div className="space-y-2 border-t border-hairline pt-4">
              <p className="text-[13px] text-steel">{t(locale, "gen_pick_hint")}</p>
              <div className="flex flex-wrap items-center gap-3">
                {regionOptions.length > 1 && (
                  <label className="text-[13px] text-steel">
                    {t(locale, "gen_region")}{" "}
                    <select value={chosenRegion} onChange={(e) => setGenRegion(e.target.value)} className="rounded-[4px] border border-hairline bg-white px-2 py-1 text-[14px] text-ink">
                      {regionOptions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
                    </select>
                  </label>
                )}
                <Button type="button" disabled={genBusy || (picked.length > 0 && !chosenRegion)} onClick={() => void make()} className="rounded-lg px-4">{genBusy ? t(locale, "gen_busy") : t(locale, "gen_submit")}</Button>
                {genError && <p role="alert" className="text-[13px] text-error">{t(locale, genError)}</p>}
              </div>
            </div>
          )}
        </section>
      )}
      {gen && <GenerationView result={gen} locale={locale} />}
    </div>
  );
}
