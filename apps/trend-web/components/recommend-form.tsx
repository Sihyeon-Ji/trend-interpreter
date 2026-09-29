"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { GenerationView } from "@/components/generation-view";
import { StatusBadge } from "@/components/status-badge";
import { riskOf, stageLine } from "@/lib/keyword";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, listJoin, regionLabel, sourceName } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CampaignTone, GenerationResult, RecommendItem, RecommendResult } from "@/lib/types";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";

const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
type ErrorKey = "rec_need_input" | "rec_too_big" | "rec_bad_type" | "rec_failed";
const ERRORS: Record<string, ErrorKey> = { need_input: "rec_need_input", too_big: "rec_too_big", bad_type: "rec_bad_type" };

/** 어울리는 점 — 제품 설명과 밈의 쓰임 낱말이 겹친 곳(추천 점수의 근거). 이유는 모델이 쓰지 않고 이것·사전 뜻·현지 쓰임으로 보인다(Plan 07 5번).
 *  서로 다른 사실은 가운뎃점으로 잇지 않고 칸을 나눈다(docs/트렌드/디자인-개편.md 원칙 6). */
function MatchLine({ locale, it, category }: { locale: Locale; it: RecommendItem; category: string }) {
  const labels = L(locale);
  return (
    <span className="flex flex-wrap gap-x-4 gap-y-0.5">
      {it.matched_category ? <span><span className="text-steel">{t(locale, "rec_match_category")}</span> {category}</span>
        : it.any_category ? <span>{t(locale, "rec_match_any")}</span> : null}
      {it.matched_feelings.length > 0 && <span><span className="text-steel">{t(locale, "rec_match_feeling")}</span> {listJoin(locale, it.matched_feelings.map((f) => labels.feeling[f]))}</span>}
    </span>
  );
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

  const field = "mt-1.5 block w-full rounded-md border border-hairline-strong bg-white px-3 py-2 text-[15px] text-ink placeholder:text-steel";
  const chip = chipClass;
  const fieldLabel = "block text-[13px] font-medium text-ink";
  const category = result?.brief ? labels.fitCategory[result.brief.category] : "";
  const step = gen ? 3 : result && result.items.length ? 2 : 1;

  return (
    <div className="space-y-6">
      <Stepper locale={locale} current={step} />
      <div className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)] lg:items-start">
        <form className="space-y-5 rounded-lg border border-hairline p-5 lg:sticky lg:top-6" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <h2 className="text-[16px] font-semibold text-ink">{t(locale, "rec_step1")}</h2>
          <div>
            <span className={fieldLabel}>{t(locale, "rec_photo")}</span>
            {/* 브라우저 기본 파일 칸은 'Choose File' 같은 영어가 섞여 나온다 — 입력은 숨기고(키보드로는 그대로 닿는다) 우리 단추로 보인다 */}
            <input key={inputKey} id="rec-photo" type="file" accept="image/jpeg,image/png,image/webp" className="peer sr-only"
              onChange={(e) => pick(e.target.files?.[0] ?? null)} />
            <label htmlFor="rec-photo" className="mt-1.5 inline-flex h-9 cursor-pointer items-center rounded-md border border-hairline-strong bg-background px-3 text-[14px] text-ink hover:border-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring">
              {photo ? t(locale, "rec_photo_change") : t(locale, "rec_photo_pick")}
            </label>
            <p className="mt-1.5 text-[12px] text-steel">{t(locale, "rec_photo_hint")}</p>
            {photo && (
              <div className="mt-2 flex items-end gap-3">
                {/* 올린 사진 미리보기 — 브라우저 안의 임시 주소라 next/image 최적화를 쓰지 않는다 */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={photo.url} alt="" className="h-20 w-20 rounded-md border border-hairline object-cover" />
                <button type="button" className="text-[13px] text-link-blue hover:underline" onClick={() => pick(null)}>{t(locale, "rec_photo_remove")}</button>
              </div>
            )}
          </div>
          <div>
            <label htmlFor="rec-copy" className={fieldLabel}>{t(locale, "rec_copy")} <span className="font-normal text-steel tabular-nums">{text.length}/500</span></label>
            <textarea id="rec-copy" value={text} maxLength={500} rows={4} onChange={(e) => setText(e.target.value)} placeholder={t(locale, "rec_copy_ph")} className={field} />
          </div>
          <fieldset>
            <legend className={fieldLabel}>{t(locale, "rec_regions")}</legend>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {TARGET_REGIONS.map((r) => (
                <button key={r} type="button" aria-pressed={regions.includes(r)} className={chip(regions.includes(r))} onClick={() => toggleRegion(r)}>{regionLabel(locale, r)}</button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className={fieldLabel}>{t(locale, "rec_tone")}</legend>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {TONES.map((x) => (
                <button key={x} type="button" aria-pressed={tone === x} className={chip(tone === x)} onClick={() => setTone(x)}>{labels.campaignTone[x]}</button>
              ))}
            </div>
          </fieldset>
          <div className="space-y-2 border-t border-hairline pt-4">
            {/* 추천을 받은 뒤에는 '만들기' 가 이 화면의 주요 작업이 된다 — 검정 단추는 하나만 */}
            <Button type="submit" disabled={busy || genBusy} variant={result ? "outline" : "default"} className="h-10 w-full rounded-md">
              {busy ? t(locale, "rec_busy") : result ? t(locale, "rec_resubmit") : t(locale, "rec_submit")}
            </Button>
            {error && <p role="alert" className="text-[13px] text-error">{t(locale, error)}</p>}
          </div>
        </form>

        <div className="min-w-0 space-y-6">
          {/* 화면 읽기 프로그램에 진행과 결과를 알린다 — 추천과 만들기 모두 */}
          <p aria-live="polite" className="sr-only">
            {busy ? t(locale, "rec_busy") : genBusy ? t(locale, "gen_busy") : gen ? `${t(locale, "gen_title")} ${gen.copies.length}`
              : result ? `${t(locale, "rec_results")} ${result.items.length}` : ""}
          </p>
          {!result && (
            <div className="rounded-lg border border-dashed border-hairline-strong px-6 py-10">
              <h2 className="text-[16px] font-semibold text-ink">{t(locale, "rec_empty_title")}</h2>
              <p className="mt-1.5 max-w-[560px] text-[14px] leading-[1.6] text-charcoal">{t(locale, "rec_empty_body")}</p>
            </div>
          )}
          {result && (
            <section aria-labelledby="rec-results" className="space-y-5">
              {result.brief && (
                <div className="rounded-lg bg-surface px-5 py-4">
                  <h2 className="text-[14px] font-semibold text-ink">{t(locale, "rec_brief")}</h2>
                  <dl className="mt-2 grid gap-x-4 gap-y-1.5 text-[14px] sm:grid-cols-[120px_minmax(0,1fr)]">
                    <dt className="text-steel">{t(locale, "rec_brief_product")}</dt><dd className="text-ink">{result.brief.product}</dd>
                    <dt className="text-steel">{t(locale, "rec_brief_category")}</dt><dd className="text-ink">{category}</dd>
                    <dt className="text-steel">{t(locale, "rec_brief_feelings")}</dt><dd className="text-ink">{listJoin(locale, result.brief.feelings.map((f) => labels.feeling[f]))}</dd>
                    {result.brief.values?.length ? <><dt className="text-steel">{t(locale, "rec_brief_values")}</dt><dd className="text-ink">{listJoin(locale, result.brief.values)}</dd></> : null}
                  </dl>
                  {result.brief_source === "sample" && <p className="mt-3 text-[13px] text-steel">{t(locale, "rec_brief_sample")}</p>}
                </div>
              )}
              <div>
                <h2 id="rec-results" className="text-[18px] font-semibold text-ink">{t(locale, "rec_results")} <span className="ml-1 text-[14px] font-normal text-steel tabular-nums">{result.items.length}</span></h2>
                <p className="mt-0.5 flex flex-wrap gap-x-4 text-[13px] text-steel">
                  <span>{t(locale, "rec_regions")} <span className="text-charcoal">{listJoin(locale, result.regions.map((r) => regionLabel(locale, r)))}</span></span>
                  <span>{t(locale, "rec_tone")} <span className="text-charcoal">{labels.campaignTone[result.tone]}</span></span>
                </p>
              </div>
              {result.items.length === 0 ? (
                <p className="rounded-lg border border-hairline px-5 py-6 text-[14px] text-charcoal">{t(locale, result.brief_source === "none" ? "rec_not_ready" : "rec_none")}</p>
              ) : (
                <ol className="divide-y divide-hairline border-y border-hairline">
                  {result.items.map((it, n) => {
                    const risk = riskOf(it);
                    const on = picked.includes(it.term_id);
                    return (
                      <li key={it.term_id}>
                        <article className="flex gap-3 py-4">
                        <input type="checkbox" checked={on} disabled={!on && picked.length >= 3} onChange={() => togglePick(it.term_id)}
                          aria-label={`${t(locale, "gen_pick")}: ${it.canonical}`} className="mt-1.5 h-4 w-4 shrink-0 accent-[#17191c]" />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <span className="text-[13px] text-steel tabular-nums">{n + 1}</span>
                            <h3 className="min-w-0 break-words text-[16px] font-semibold text-ink">{it.canonical}</h3>
                            {risk && risk !== "avoid" && <StatusBadge tone={risk === "caution" ? "caution" : "muted"}>{t(locale, `risk_${risk}`)}</StatusBadge>}
                          </div>
                          <p className="mt-1 text-[14px] leading-[1.55] text-charcoal">{locale === "ko" ? it.gloss_ko : it.gloss_en}</p>
                          <dl className="mt-2.5 grid gap-x-4 gap-y-1.5 text-[13px] sm:grid-cols-[96px_minmax(0,1fr)]">
                            <dt className="text-steel">{t(locale, "rec_stage")}</dt><dd className="text-charcoal">{stageLine(locale, it)}</dd>
                            <dt className="text-steel">{t(locale, "rec_match")}</dt><dd className="text-ink"><MatchLine locale={locale} it={it} category={category} /></dd>
                            {it.local_note && it.local_region && (
                              <><dt className="text-steel">{t(locale, "rec_local")}</dt>
                                <dd className="text-charcoal"><span className="text-steel">{regionLabel(locale, it.local_region)}</span> {locale === "ko" ? it.local_note.ko : it.local_note.en}</dd></>
                            )}
                            {(risk === "caution" || risk === "unknown") && (
                              <><dt className="text-steel">{t(locale, "rec_care")}</dt><dd className="text-charcoal">{t(locale, `risk_${risk}_why`)}</dd></>
                            )}
                            <dt className="text-steel">{t(locale, "rec_sources")}</dt>
                            <dd className="flex flex-wrap gap-x-4 gap-y-1">
                              {it.evidences.map((e, i) => (
                                <a key={`${e.url}-${i}`} href={e.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
                                  {sourceName(locale, e.source_domain)} <span className="text-steel tabular-nums">{fmtDate(e.observed_at)}</span>
                                </a>
                              ))}
                              {/* 새 탭으로 — 사전을 보고 돌아와도 추천 결과가 남는다 */}
                              <Link href={`/dictionary/${it.term_id}`} target="_blank" rel="noopener" className="text-link-blue hover:underline">{t(locale, "rec_open_term")}</Link>
                            </dd>
                          </dl>
                        </div>
                        </article>
                      </li>
                    );
                  })}
                </ol>
              )}
              <p className="text-[12px] text-steel">{t(locale, "rec_note")}</p>
              {result.items.length > 0 && (
                <section aria-labelledby="gen-step" className="space-y-3 rounded-lg border border-hairline p-5">
                  <h2 id="gen-step" className="text-[16px] font-semibold text-ink">{t(locale, "rec_step3")}</h2>
                  <p className="text-[13px] text-steel">{t(locale, "gen_pick_hint")}</p>
                  <div className="flex flex-wrap items-end gap-3">
                    {regionOptions.length > 1 && (
                      <label className="text-[13px] font-medium text-ink">
                        {t(locale, "gen_region")}
                        <select value={chosenRegion} onChange={(e) => setGenRegion(e.target.value)} className="mt-1.5 block h-10 rounded-md border border-hairline-strong bg-white px-3 text-[14px] font-normal text-ink">
                          {regionOptions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
                        </select>
                      </label>
                    )}
                    <Button type="button" disabled={genBusy || (picked.length > 0 && !chosenRegion)} onClick={() => void make()} className="h-10 rounded-md px-4">
                      {genBusy ? t(locale, "gen_busy") : t(locale, "gen_submit")}
                    </Button>
                  </div>
                  {genError && <p role="alert" className="text-[13px] text-error">{t(locale, genError)}</p>}
                  {picked.length > 0 && !chosenRegion && <p className="text-[13px] text-charcoal">{t(locale, "gen_no_region")}</p>}
                </section>
              )}
            </section>
          )}
          {gen && <GenerationView result={gen} locale={locale} />}
        </div>
      </div>
    </div>
  );
}

/* 추천의 세 단계 — 진짜 순서라 번호를 붙인다(docs/트렌드/디자인-개편.md 원칙 5). 지금 단계는 채운 원, 지난 단계는 테두리 원. */
function Stepper({ locale, current }: { locale: Locale; current: number }) {
  const steps = [t(locale, "rec_step1"), t(locale, "rec_step2"), t(locale, "rec_step3")];
  return (
    <ol aria-label={t(locale, "rec_steps")} className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[14px]">
      {steps.map((s, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "current" : "todo";
        return (
          <li key={n} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-2.5">
            <span className={cn("inline-flex h-6 w-6 items-center justify-center rounded-full border text-[12px] font-medium tabular-nums",
              state === "current" ? "border-ink bg-ink text-white" : state === "done" ? "border-ink text-ink" : "border-hairline-strong text-steel")}>{n}</span>
            <span className={cn(state === "todo" ? "text-steel" : "text-ink", state === "current" && "font-medium")}>{s}</span>
            {n < steps.length && <span aria-hidden className="mx-1 hidden h-px w-10 bg-hairline-strong sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}
