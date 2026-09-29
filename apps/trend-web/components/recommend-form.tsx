"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { GenerationView } from "@/components/generation-view";
import { riskOf, stageLine } from "@/components/keyword-card";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, listJoin, regionLabel, sourceName } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CampaignTone, GenerationResult, RecommendItem, RecommendResult } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
type ErrorKey = "rec_need_input" | "rec_too_big" | "rec_bad_type" | "rec_failed";
const ERRORS: Record<string, ErrorKey> = { need_input: "rec_need_input", too_big: "rec_too_big", bad_type: "rec_bad_type" };

/** 어울리는 점 — 제품 설명과 밈의 쓰임 낱말이 겹친 곳(추천 점수의 근거). 이유는 모델이 쓰지 않고 이것·사전 뜻·현지 쓰임으로 보인다(Plan 07 5번). */
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
  const [inputKey, setInputKey] = useState(0);   // 사진을 빼면 파일 입력칸도 비운다 — 그대로 두면 같은 파일을 다시 고를 수 없었다
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
  // 만들기 요청마다 번호 — 새 추천을 받은 뒤에 도착한 옛 결과물은 버린다(검토 3차: 이전 톤의 카피가 새 목록 밑에 떴다)
  const genSeq = useRef(0);

  // 미리보기 주소는 이 탭 안에서만 산다 — 사진을 바꾸거나 빼거나 화면을 떠나면 돌려준다
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);

  const pick = (f: File | null) => {
    setError(null);
    if (f && f.size > MAX_IMAGE) { setError("rec_too_big"); setInputKey((k) => k + 1); return; }
    if (f && !["image/jpeg", "image/png", "image/webp"].includes(f.type)) { setError("rec_bad_type"); setInputKey((k) => k + 1); return; }
    if (!f) setInputKey((k) => k + 1);
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
      else { genSeq.current++; setResult(json); setPicked([]); setGen(null); setGenError(null); setGenBusy(false); setGenRegion(json.regions[0] ?? "KR"); }
    } catch {
      setError("rec_failed");
    }
    setBusy(false);
  };

  const togglePick = (id: string) => setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < 3 ? [...cur, id] : cur));
  // 결과물을 쓸 지역은 고른 밈을 그 말로 쓸 수 있는 곳만(백엔드 generate.writable 이 정한 write_regions) — 한국 밈으로 일본 카피를 만들지 않는다
  const covered = result ? result.regions.filter((r) => picked.some((id) => result.items.find((i) => i.term_id === id)?.write_regions.includes(r))) : [];
  const regionOptions = picked.length ? covered : result?.regions ?? [];
  const chosenRegion = regionOptions.includes(genRegion) ? genRegion : regionOptions[0] ?? "";
  const make = async () => {
    if (!result) return;
    if (!picked.length) { setGenError("gen_need_pick"); return; }
    const seq = ++genSeq.current;
    setGenBusy(true);
    setGenError(null);
    let got: GenerationResult | null = null;
    let failed = false;
    try {
      const res = await fetch("/api/generate", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ term_ids: picked, brief: result.brief, region: chosenRegion, tone: result.tone, lang: locale }) });
      if (res.ok) got = (await res.json()) as GenerationResult;
      else failed = true;
    } catch {
      failed = true;
    }
    if (seq !== genSeq.current) return;          // 그 사이 새 추천을 받았다 — 이 결과물은 지금 목록의 것이 아니다
    if (failed) setGenError("gen_failed");
    else setGen(got);
    setGenBusy(false);
  };
  // 결과물이 오면 그 제목으로 초점을 옮긴다 — 10~80초 걸린 뒤 무엇이 어디에 생겼는지 알린다(검토 3차)
  useEffect(() => { if (gen) document.getElementById("gen-title")?.focus(); }, [gen]);

  const field = "mt-1 block w-full rounded-[4px] border border-hairline bg-white px-3 py-2 text-[15px] text-ink";
  const chip = (on: boolean) => cn("rounded-full border px-3 py-1 text-[13px] whitespace-nowrap",
    on ? "border-primary bg-primary text-primary-foreground" : "border-hairline-strong text-charcoal hover:border-ink hover:text-ink");
  const category = result?.brief ? labels.fitCategory[result.brief.category] : "";

  return (
    <div className="space-y-10">
      <form className="max-w-[640px] space-y-5" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <div>
          <label htmlFor="rec-photo" className="block text-[13px] text-steel">{t(locale, "rec_photo")}</label>
          <input key={inputKey} id="rec-photo" type="file" accept="image/jpeg,image/png,image/webp" className="mt-1 block text-[14px] text-charcoal"
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

      {/* 화면 읽기 프로그램에 진행과 결과를 알린다 — 추천과 만들기 모두 */}
      <p aria-live="polite" className="sr-only">
        {busy ? t(locale, "rec_busy") : genBusy ? t(locale, "gen_busy") : gen ? `${t(locale, "gen_title")} ${gen.copies.length}`
          : result ? `${t(locale, "rec_results")} ${result.items.length}` : ""}
      </p>
      {result && (
        <section aria-labelledby="rec-results" className="space-y-5">
          {result.brief && (
            <div className="rounded-lg border border-hairline p-4">
              <h2 className="text-[14px] font-semibold text-ink">{t(locale, "rec_brief")}</h2>
              <p className="mt-1 text-[15px] text-ink">{result.brief.product} <span className="text-[13px] text-steel">· {category}</span></p>
              <p className="mt-1 text-[13px] text-charcoal">{listJoin(locale, result.brief.feelings.map((f) => labels.feeling[f]))}{result.brief.values?.length ? ` · ${result.brief.values.join(", ")}` : ""}</p>
              {result.brief_source === "sample" && <p className="mt-2 text-[13px] text-steel">{t(locale, "rec_brief_sample")}</p>}
            </div>
          )}
          <div>
            <h2 id="rec-results" className="text-[18px] font-semibold text-ink">{t(locale, "rec_results")} <span className="ml-1 text-[14px] font-normal text-steel">{result.items.length}</span></h2>
            <p className="mt-0.5 text-[13px] text-steel">{listJoin(locale, result.regions.map((r) => regionLabel(locale, r)))} · {labels.campaignTone[result.tone]}</p>
          </div>
          {result.items.length === 0 ? <p className="text-[14px] text-steel">{t(locale, result.brief_source === "none" ? "rec_not_ready" : "rec_none")}</p> : (
            <ol className="space-y-3">
              {result.items.map((it, n) => (
                <li key={it.term_id}>
                  <article className="rounded-lg border border-hairline p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 break-words text-[16px] font-semibold text-ink"><span className="mr-2 text-steel tabular-nums">{n + 1}</span>{it.canonical}</h3>
                      {(() => {
                        // 대시보드 카드와 같은 표시 — 주의와 '근거 부족'(검사했지만 문장이 모자람)
                        const risk = riskOf(it);
                        return risk && risk !== "avoid" && <span className="shrink-0 rounded border border-hairline-strong px-1.5 text-[12px] leading-[20px] text-charcoal">{t(locale, `risk_${risk}`)}</span>;
                      })()}
                    </div>
                    <p className="mt-1 text-[14px] leading-[1.55] text-charcoal">{locale === "ko" ? it.gloss_ko : it.gloss_en}</p>
                    <p className="mt-1 text-[12px] text-steel">{stageLine(locale, it)}</p>
                    <p className="mt-2 text-[14px] text-ink">
                      <span className="text-steel">{t(locale, "rec_match")}: </span>
                      {matchLine(locale, it, category)}
                    </p>
                    {it.local_note && it.local_region && (
                      <p className="mt-1 text-[13px] leading-[1.55] text-charcoal">
                        <span className="text-steel">{t(locale, "rec_local")} ({regionLabel(locale, it.local_region)}): </span>
                        {locale === "ko" ? it.local_note.ko : it.local_note.en}
                      </p>
                    )}
                    {(riskOf(it) === "caution" || riskOf(it) === "unknown") && <p className="mt-1 text-[12px] text-charcoal">{t(locale, `risk_${riskOf(it) as "caution" | "unknown"}_why`)}</p>}
                    <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12px]">
                      <label className="flex items-center gap-1.5 text-charcoal">
                        <input type="checkbox" checked={picked.includes(it.term_id)} disabled={!picked.includes(it.term_id) && picked.length >= 3}
                          onChange={() => togglePick(it.term_id)} />
                        {t(locale, "gen_pick")}
                      </label>
                      {/* 새 탭으로 — 사전을 보고 돌아와도 추천 결과가 남는다 */}
                      <Link href={`/dictionary/${it.term_id}`} target="_blank" rel="noopener" className="text-link-blue hover:underline">{t(locale, "rec_open_term")}</Link>
                      {it.evidences.map((e, i) => (
                        <a key={`${e.url}-${i}`} href={e.url} target="_blank" rel="noreferrer" className="text-steel hover:text-ink hover:underline">
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
                {picked.length > 0 && !chosenRegion && <p className="text-[13px] text-charcoal">{t(locale, "gen_no_region")}</p>}
              </div>
            </div>
          )}
        </section>
      )}
      {gen && <GenerationView result={gen} locale={locale} />}
    </div>
  );
}
