"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ChipMark } from "@/components/chip-mark";
import { Button } from "@/components/ui/button";
import { GenerationView } from "@/components/generation-view";
import { StatePanel } from "@/components/state-panel";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { riskOf } from "@/lib/keyword";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L, fmtDate, regionLabel, sourceName } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { CampaignTone, GenerationResult, RecommendItem, RecommendResult } from "@/lib/types";
import { chipClass } from "@/lib/ui";
import { cn } from "@/lib/utils";
import { glossFor } from "@/lib/gloss";

const MAX_IMAGE = 5 * 1024 * 1024;
const MAX_PICK = 3;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
type PhotoError = "rec_too_big" | "rec_bad_type";
type RequestError = "rec_failed" | "rec_too_many";
type GenError = "gen_failed" | "gen_need_pick" | "rec_too_many";
export type Pinned = { id: string; name: string; lang?: string };
type Snapshot = { text: string; file: File | null; regions: string; tone: CampaignTone };

const fieldLabel = "block text-[14px] font-medium text-ink";
const chipInput = "relative cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring";
// 같은 종류의 값 목록은 쉼표로 — 가운뎃점은 서로 다른 사실을 잇는 것처럼 읽혔다(원칙 6)
const list = (xs: string[]) => xs.join(", ");
const fmtSize = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const gloss = (it: RecommendItem, locale: Locale) => glossFor(it, locale);
const hasDetails = (it: RecommendItem) => it.matched_feelings.length > 0 || it.matched_category || it.any_category || !!(it.local_note && it.local_region)
  || riskOf(it) === "caution" || riskOf(it) === "unknown";

/** 새 탭으로 여는 링크 — 사전을 보고 돌아와도 추천 결과가 남는다. 표제어 원문에만 lang 을 붙이고 안내는 화면 언어로 읽힌다.
 *  ?from=recommend 면 사전 항목이 '이 밈으로 만들기' 를 내지 않는다(이미 추천 흐름 안이다). */
function TermLink({ it, locale, className }: { it: RecommendItem; locale: Locale; className?: string }) {
  return (
    <Link href={`/dictionary/${it.term_id}?from=recommend`} target="_blank" rel="noopener" className={cn("font-semibold break-words text-ink hover:underline", className)}>
      <span lang={langTag(it.lang)}>{it.canonical}</span><span className="sr-only"> {t(locale, "rec_new_tab")}</span>
    </Link>
  );
}

/** 맞는 점 — 제품 설명과 밈의 쓰임 낱말이 겹친 곳(추천 점수의 근거), 현지 쓰임, 조심할 점. 서로 다른 사실은 줄을 나눈다(원칙 6). */
function Details({ it, locale, category }: { it: RecommendItem; locale: Locale; category: string }) {
  const labels = L(locale);
  const risk = riskOf(it);
  const line = (label: string, value: React.ReactNode) => <p><span className="text-steel">{label}:</span> {value}</p>;
  return (
    <div className="space-y-0.5 text-[13px] leading-[1.5] text-charcoal">
      {it.matched_feelings.length > 0 && line(t(locale, "rec_match_feeling"), list(it.matched_feelings.map((f) => labels.feeling[f])))}
      {(it.matched_category || it.any_category) && line(t(locale, "rec_match_category"), it.matched_category ? category : t(locale, "rec_match_any"))}
      {it.local_note && it.local_region && line(`${t(locale, "rec_local")} (${regionLabel(locale, it.local_region)})`, locale === "ko" ? it.local_note.ko : it.local_note.en)}
      {(risk === "caution" || risk === "unknown") && line(t(locale, "rec_care_line"), t(locale, `risk_${risk}_why`))}
    </div>
  );
}

function Sources({ it, locale, inline }: { it: RecommendItem; locale: Locale; inline?: boolean }) {
  if (!it.evidences.length) return <span className="text-steel">—</span>;
  return (
    <ul className={cn("text-[13px]", inline ? "flex flex-wrap gap-x-4 gap-y-1" : "space-y-1.5")}>
      {it.evidences.map((e, i) => (
        <li key={`${e.url}-${i}`}>
          <a href={e.url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
            {sourceName(locale, e.source_domain)}<span className="sr-only"> {t(locale, "rec_new_tab")}</span>
          </a>
          <span className={cn("text-[12px] text-steel tabular-nums", inline ? "ml-1.5" : "block")}>{fmtDate(e.observed_at)}</span>
        </li>
      ))}
    </ul>
  );
}

/** 고르기 칸 — 누르는 곳 44×44. 이름에 밈을 넣어 양식 목록으로 훑어도 어느 밈의 것인지 알게 한다. */
function PickBox({ it, locale, on, disabled, onToggle }: { it: RecommendItem; locale: Locale; on: boolean; disabled: boolean; onToggle: () => void }) {
  return (
    <label className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-md", disabled ? "cursor-not-allowed" : "cursor-pointer")}>
      <input type="checkbox" checked={on} disabled={disabled} onChange={onToggle} aria-label={t(locale, "gen_pick").replace("{name}", it.canonical)}
        className="h-[18px] w-[18px] accent-link-blue" />
    </label>
  );
}

/* 추천 목록. 데스크톱은 대시보드 표와 같은 칸(단계·쓸 때 조심·근거), 휴대폰은 한 줄씩. 고른 행은 옅은 바탕. */
function RecommendTable({ items, locale, category, picked, locked, onToggle }: {
  items: RecommendItem[]; locale: Locale; category: string; picked: string[]; locked: boolean; onToggle: (id: string) => void;
}) {
  const disabled = (id: string) => locked || (!picked.includes(id) && picked.length >= MAX_PICK);
  return (
    <>
      <div className="hidden md:block">
        <table className="w-full table-fixed border-collapse text-left">
          <caption className="sr-only">{t(locale, "rec_results").replace("{n}", String(items.length))}</caption>
          <thead>
            <tr className="border-b border-hairline text-[13px] text-steel">
              <th scope="col" className="w-12 py-2.5 font-medium">{t(locale, "rec_col_pick")}</th>
              <th scope="col" className="py-2.5 pr-4 font-medium">{t(locale, "rec_col_term")}</th>
              <th scope="col" className="w-[136px] py-2.5 pr-3 font-medium">{t(locale, "rec_stage")}</th>
              <th scope="col" className="w-[112px] py-2.5 pr-3 font-medium">{t(locale, "rec_care")}</th>
              <th scope="col" className="w-[108px] py-2.5 font-medium">{t(locale, "rec_sources")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const on = picked.includes(it.term_id);
              return (
                <tr key={it.term_id} className={cn("border-b border-hairline align-top", on && "bg-surface")}>
                  <td className="py-1.5"><PickBox it={it} locale={locale} on={on} disabled={disabled(it.term_id)} onToggle={() => onToggle(it.term_id)} /></td>
                  <td className="py-3 pr-4">
                    <TermLink it={it} locale={locale} className="text-[15px]" />
                    {it.pinned && <p className="text-[12px] text-steel">{t(locale, "rec_pinned")}</p>}
                    <p className="mt-0.5 text-[13px] leading-[1.5] text-charcoal">{gloss(it, locale)}</p>
                    {hasDetails(it) && <div className="mt-1.5"><Details it={it} locale={locale} category={category} /></div>}
                  </td>
                  <td className="py-3 pr-3"><StageCell diffusion={it.diffusion} lifecycle={it.lifecycle} locale={locale} /></td>
                  <td className="py-3 pr-3"><RiskCell item={it} locale={locale} /></td>
                  <td className="py-3"><Sources it={it} locale={locale} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
        {items.map((it) => {
          const on = picked.includes(it.term_id);
          return (
            <li key={it.term_id} className={cn("flex gap-1 py-2 pr-1", on && "bg-surface")}>
              <PickBox it={it} locale={locale} on={on} disabled={disabled(it.term_id)} onToggle={() => onToggle(it.term_id)} />
              <div className="min-w-0 flex-1 pt-2">
                <div className="flex items-start justify-between gap-3">
                  <TermLink it={it} locale={locale} className="min-w-0 text-[16px]" />
                  <RiskCell item={it} locale={locale} />
                </div>
                {it.pinned && <p className="text-[12px] text-steel">{t(locale, "rec_pinned")}</p>}
                <p className="mt-1 text-[14px] leading-[1.5] text-charcoal">{gloss(it, locale)}</p>
                <dl className="mt-2 grid grid-cols-[64px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[13px]">
                  <dt className="text-steel">{t(locale, "rec_stage")}</dt>
                  <dd><StageCell diffusion={it.diffusion} lifecycle={it.lifecycle} locale={locale} /></dd>
                  {hasDetails(it) && <><dt className="text-steel">{t(locale, "rec_match")}</dt>
                    <dd><Details it={it} locale={locale} category={category} /></dd></>}
                  <dt className="text-steel">{t(locale, "rec_sources")}</dt>
                  <dd><Sources it={it} locale={locale} inline /></dd>
                </dl>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}

/* 추천의 세 단계 — 진짜 순서라 번호를 붙인다(원칙 5). 번호 원은 칠하지 않는다: 지금은 파랑 테두리, 지난 단계는 먹 테두리, 아직은 회색.
   지난 단계와 이미 만든 결과물은 누르면 그리로 돌아간다(고른 밈은 그대로). */
function Stepper({ locale, current, reachable, onGo }: { locale: Locale; current: number; reachable: (n: number) => boolean; onGo: (n: number) => void }) {
  const steps = [t(locale, "rec_step1"), t(locale, "rec_step2"), t(locale, "rec_step3")];
  return (
    <ol aria-label={t(locale, "rec_steps")} className="flex flex-nowrap items-center gap-x-3 text-[13px] sm:text-[14px]">
      {steps.map((s, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "current" : "todo";
        const body = (
          <>
            <span className={cn("inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[12px] font-medium tabular-nums",
              state === "current" ? "border-link-blue text-ink shadow-[inset_0_0_0_1px_var(--link-blue)]" : state === "done" ? "border-ink text-ink" : "border-hairline-strong text-steel")}>{n}</span>
            <span className={cn("whitespace-nowrap", state === "todo" && !reachable(n) ? "text-steel" : "text-ink", state === "current" && "font-semibold")}>{s}</span>
            {state === "done" && <span className="sr-only"> {t(locale, "rec_step_done")}</span>}
          </>
        );
        return (
          <li key={n} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-2">
            {state !== "current" && reachable(n) ? (
              <button type="button" onClick={() => onGo(n)} className="-my-2 flex min-h-10 items-center gap-2 rounded-md hover:underline">{body}</button>
            ) : <span className="flex items-center gap-2">{body}</span>}
            {n < steps.length && <span aria-hidden className="mx-1 hidden h-px w-10 bg-hairline-strong sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}

export function RecommendForm({ locale, initialRegions, pinned, sample }: { locale: Locale; initialRegions: string[]; pinned: Pinned | null; sample: boolean }) {
  const labels = L(locale);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);   // 사진을 빼면 파일 입력칸도 비운다 — 그대로 두면 같은 파일을 다시 고를 수 없었다
  const [drag, setDrag] = useState(false);
  const [regions, setRegions] = useState<string[]>(initialRegions);   // 비어 있으면 목표 지역 전체(대시보드 dash_all 과 같은 규칙)
  const [tone, setTone] = useState<CampaignTone>("friendly");
  const [busy, setBusy] = useState(false);
  const [needInput, setNeedInput] = useState(false);
  const [photoError, setPhotoError] = useState<PhotoError | null>(null);
  const [reqError, setReqError] = useState<RequestError | null>(null);
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [asked, setAsked] = useState<Snapshot | null>(null);        // 마지막으로 추천받은 입력 — 입력이 바뀌면 알린다
  const [editing, setEditing] = useState(true);                      // xl 미만: 추천을 받으면 1단계를 요약으로 접는다
  const [briefOpen, setBriefOpen] = useState(false);                 // 휴대폰: 읽은 내용은 접어 둔다
  // 만들기(Plan 08): 추천에서 밈을 최대 3개 고르고, 결과물을 쓸 지역 하나를 정한다
  const [picked, setPicked] = useState<string[]>([]);
  const [genRegion, setGenRegion] = useState<string>("");
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState<GenError | null>(null);
  const [stopped, setStopped] = useState(false);
  const [gen, setGen] = useState<GenerationResult | null>(null);
  const [genAsked, setGenAsked] = useState<{ picked: string; region: string } | null>(null);
  const [view, setView] = useState<"pick" | "drafts">("pick");      // 3단계는 2단계 자리에 바꿔 끼운다
  const [elapsed, setElapsed] = useState(0);
  // 만들기 요청마다 번호 — 새 추천을 받은 뒤에 도착한 옛 결과물은 버린다(검토 3차: 이전 톤의 카피가 새 목록 밑에 떴다)
  const genSeq = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const copyInput = useRef<HTMLTextAreaElement>(null);
  const stopButton = useRef<HTMLButtonElement>(null);
  const makeButton = useRef<HTMLButtonElement>(null);
  const moved = useRef<"results" | "drafts" | "wait" | "make" | null>(null);

  // 미리보기 주소는 이 탭 안에서만 산다 — 사진을 바꾸거나 빼거나 화면을 떠나면 돌려준다
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  // 화면을 떠나면 만들던 요청도 끊는다
  useEffect(() => () => abort.current?.abort(), []);
  // 만드는 동안 지난 시간(초). 화면 읽기 프로그램에는 시작과 끝만 알린다(aria-live 밖)
  useEffect(() => {
    if (!genBusy) return;
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [genBusy]);
  // 결과가 오면 그 제목으로 초점과 화면을 옮긴다 — 휴대폰에서는 결과가 첫 화면 밖에 생겨 눌러도 바뀌지 않은 것처럼 보였다
  useEffect(() => {
    const target = moved.current;
    if (!target) return;
    moved.current = null;
    const el = target === "results" ? document.getElementById("rec-results") : target === "drafts" ? document.getElementById("gen-title")
      : target === "wait" ? stopButton.current : makeButton.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: target === "results" || target === "drafts" ? "start" : "nearest", behavior: reduce ? "auto" : "smooth" });
  });

  const pick = (f: File | null) => {
    setPhotoError(null);
    const bad: PhotoError | null = f && f.size > MAX_IMAGE ? "rec_too_big" : f && !["image/jpeg", "image/png", "image/webp"].includes(f.type) ? "rec_bad_type" : null;
    if (bad) { setPhotoError(bad); setInputKey((k) => k + 1); return; }
    if (!f) setInputKey((k) => k + 1);
    if (f) setNeedInput(false);
    setPhoto(f ? { file: f, url: URL.createObjectURL(f) } : null);
  };
  // '목표 지역 전체' 를 보다가 한 나라를 고르면 그 나라만, 다 빼면 전체로 돌아간다(대시보드 지역 칩과 같다)
  const toggleRegion = (r: string) => setRegions((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const submit = async (override?: { regions: string[] }) => {
    const wanted = override?.regions ?? regions;
    if (!text.trim() && !photo) { setNeedInput(true); copyInput.current?.focus(); return; }
    setBusy(true);
    setNeedInput(false);
    setPhotoError(null);
    setReqError(null);
    const body = new FormData();
    body.set("text", text.trim());
    body.set("tone", tone);
    body.set("lang", locale);
    body.set("regions", wanted.join(","));
    if (pinned) body.set("term", pinned.id);
    if (photo) body.set("image", photo.file);
    try {
      const res = await fetch("/api/recommend", { method: "POST", body });
      const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
      if (!res.ok) {
        const code = json.error ?? "";
        if (code === "need_input") { setNeedInput(true); copyInput.current?.focus(); }
        else if (code === "too_big" || code === "bad_type") { setPhotoError(code === "too_big" ? "rec_too_big" : "rec_bad_type"); fileInput.current?.focus(); }
        else setReqError(code === "busy" ? "rec_too_many" : "rec_failed");
      } else {
        genSeq.current++;
        abort.current?.abort();
        setResult(json);
        setAsked({ text: text.trim(), file: photo?.file ?? null, regions: wanted.join(","), tone });
        setPicked(json.items.filter((i) => i.pinned).map((i) => i.term_id).slice(0, MAX_PICK));
        setGen(null); setGenAsked(null); setGenError(null); setStopped(false); setGenBusy(false); setView("pick");
        setGenRegion(json.regions[0] ?? "KR");
        setEditing(false);
        moved.current = "results";
      }
    } catch {
      setReqError("rec_failed");
    }
    setBusy(false);
  };

  const togglePick = (id: string) => {
    setStopped(false);
    setGenError(null);
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < MAX_PICK ? [...cur, id] : cur));
  };
  // 결과물을 쓸 지역은 고른 밈을 그 말로 쓸 수 있는 곳만(백엔드 generate.writable 이 정한 write_regions) — 한국 밈으로 일본 카피를 만들지 않는다
  const covered = result ? result.regions.filter((r) => picked.some((id) => result.items.find((i) => i.term_id === id)?.write_regions.includes(r))) : [];
  const regionOptions = picked.length ? covered : result?.regions ?? [];
  const chosenRegion = regionOptions.includes(genRegion) ? genRegion : regionOptions[0] ?? "";

  const make = async () => {
    if (!result) return;
    if (!picked.length) { setGenError("gen_need_pick"); return; }
    const seq = ++genSeq.current;
    const ctrl = new AbortController();
    abort.current?.abort();
    abort.current = ctrl;
    const request = { picked: picked.join(","), region: chosenRegion };
    setGenBusy(true);
    setElapsed(0);
    setGenError(null);
    setStopped(false);
    setView("drafts");
    moved.current = "wait";
    let got: GenerationResult | null = null;
    let failed: GenError | "aborted" | null = null;
    try {
      const res = await fetch("/api/generate", { method: "POST", headers: { "content-type": "application/json" }, signal: ctrl.signal,
        body: JSON.stringify({ term_ids: picked, brief: result.brief, region: chosenRegion, tone: result.tone, lang: locale }) });
      if (res.ok) got = (await res.json()) as GenerationResult;
      else failed = ((await res.json().catch(() => ({}))) as { error?: string }).error === "busy" ? "rec_too_many" : "gen_failed";
    } catch {
      failed = ctrl.signal.aborted ? "aborted" : "gen_failed";
    }
    if (seq !== genSeq.current) return;          // 그 사이 새 추천을 받았거나 다시 만들었다 — 이 결과물은 지금 것이 아니다
    setGenBusy(false);
    abort.current = null;
    if (failed || !got) {
      // 멈추거나 실패하면 2단계를 그대로 두고 만들기 줄 위에 알린다
      if (failed === "aborted") setStopped(true);
      else setGenError(failed ?? "gen_failed");
      setView("pick");
      moved.current = "make";
      return;
    }
    setGen(got);
    setGenAsked(request);
    moved.current = "drafts";
  };
  const stop = () => abort.current?.abort();

  const category = result?.brief ? labels.fitCategory[result.brief.category] : "";
  const step = view === "drafts" ? 3 : result ? 2 : 1;
  const reachable = (n: number) => (n === 1 ? !!result : n === 2 ? !!result : !!gen && !genBusy);
  const go = (n: number) => {
    if (n === 1) { setEditing(true); setTimeout(() => copyInput.current?.focus(), 0); }
    else if (n === 2) setView("pick");
    else { setView("drafts"); moved.current = "drafts"; }
  };
  const changed = !!(result && asked && (text.trim() !== asked.text || (photo?.file ?? null) !== asked.file || regions.join(",") !== asked.regions || tone !== asked.tone));
  const genChanged = !!(gen && genAsked && (picked.join(",") !== genAsked.picked || chosenRegion !== genAsked.region));
  const collapsed = !!result && !editing;
  const pinnedMissing = !!(result && pinned && !result.items.some((i) => i.term_id === pinned.id));
  const all = regions.length === 0;
  const used = gen && result ? result.items.filter((i) => gen.memes.includes(i.canonical)) : [];
  const live = busy ? t(locale, "rec_busy") : genBusy ? t(locale, "gen_busy") : view === "drafts" && gen ? t(locale, "gen_done")
    : result ? t(locale, "rec_results").replace("{n}", String(result.items.length)) : "";

  return (
    <div className="space-y-6">
      <Stepper locale={locale} current={step} reachable={reachable} onGo={go} />
      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)] xl:items-start xl:gap-8">
        <div className="min-w-0 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-3rem)] xl:overflow-y-auto">
          {collapsed && result && (
            <section aria-label={t(locale, "rec_step1")} className="rounded-lg border border-hairline p-4 xl:hidden">
              <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[14px]">
                {asked?.text && <><dt className="text-steel">{t(locale, "rec_summary_copy")}</dt><dd className="truncate text-ink">{asked.text.split("\n")[0]}</dd></>}
                {asked?.file && <><dt className="text-steel">{t(locale, "rec_summary_photo")}</dt><dd className="truncate text-ink">{asked.file.name}</dd></>}
                <dt className="text-steel">{t(locale, "gen_region_short")}</dt>
                <dd className="text-ink">{result.regions.length === TARGET_REGIONS.length ? t(locale, "dash_all") : list(result.regions.map((r) => regionLabel(locale, r)))}</dd>
                <dt className="text-steel">{t(locale, "rec_tone")}</dt><dd className="text-ink">{labels.campaignTone[result.tone]}</dd>
              </dl>
              <Button type="button" variant="outline" className="mt-3 h-10 rounded-md px-4" onClick={() => go(1)}>{t(locale, "rec_edit")}</Button>
            </section>
          )}
          <form aria-busy={busy} aria-labelledby="rec-form-title" className={cn("space-y-5 rounded-lg border border-hairline p-5", collapsed && "hidden xl:block")}
            onSubmit={(e) => { e.preventDefault(); void submit(); }}>
            <div className="space-y-2">
              <h2 id="rec-form-title" className="text-[16px] font-semibold text-ink">{t(locale, "rec_step1")}</h2>
              <p id="rec-required" className={cn("text-[13px] leading-[1.5]", needInput ? "font-medium text-error" : "text-charcoal")} role={needInput ? "alert" : undefined}>
                {t(locale, "rec_need_input")}
              </p>
              {sample && <p className="text-[13px] leading-[1.5] text-charcoal">{t(locale, "rec_brief_sample")}</p>}
              {pinned && (
                <p className="text-[13px] leading-[1.5] text-charcoal">
                  {t(locale, "rec_pinned_intro").split("{name}").flatMap((part, i) => (i ? [<span key={i} lang={pinned.lang} className="font-medium text-ink">{pinned.name}</span>, part] : [part]))}
                </p>
              )}
            </div>

            <div>
              <span className={fieldLabel}>{t(locale, "rec_photo")}</span>
              <div className={cn("mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border px-3 py-3", drag ? "border-ink" : "border-hairline-strong")}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0] ?? null); }}>
                {/* 브라우저 기본 파일 칸은 'Choose File' 같은 영어가 섞여 나온다 — 입력은 숨기고(키보드로는 그대로 닿는다) 우리 단추로 보인다 */}
                <input ref={fileInput} key={inputKey} id="rec-photo" type="file" accept="image/jpeg,image/png,image/webp" className="peer sr-only"
                  aria-invalid={photoError ? true : undefined} aria-describedby={cn("rec-photo-hint", photoError && "rec-photo-error")}
                  onChange={(e) => pick(e.target.files?.[0] ?? null)} />
                <label htmlFor="rec-photo" className="inline-flex h-10 cursor-pointer items-center rounded-md border border-hairline-strong bg-background px-3 text-[14px] font-medium text-ink hover:border-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring">
                  {photo ? t(locale, "rec_photo_change") : t(locale, "rec_photo_pick")}
                </label>
                <span className="text-[13px] text-steel">{t(locale, "rec_photo_drop")}</span>
              </div>
              <p id="rec-photo-hint" className="mt-1.5 text-[13px] leading-[1.5] text-steel">{t(locale, "rec_photo_hint")}</p>
              {photoError && <p id="rec-photo-error" role="alert" className="mt-1 text-[13px] text-error">{t(locale, photoError)}</p>}
              {photo && (
                <div className="mt-3 flex items-center gap-3">
                  {/* 올린 사진 미리보기 — 브라우저 안의 임시 주소라 next/image 최적화를 쓰지 않는다 */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={photo.url} alt={t(locale, "rec_photo_alt")} className="h-20 w-20 shrink-0 rounded-md border border-hairline object-cover" />
                  <div className="min-w-0 text-[13px]">
                    <p className="truncate text-ink">{photo.file.name}</p>
                    <p className="text-steel tabular-nums">{fmtSize(photo.file.size)}</p>
                    <button type="button" className="-ml-1 h-8 px-1 text-link-blue hover:underline" onClick={() => pick(null)}>{t(locale, "rec_photo_remove")}</button>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="rec-copy" className={fieldLabel}>{t(locale, "rec_copy")}</label>
              <textarea ref={copyInput} id="rec-copy" value={text} maxLength={500} rows={4} placeholder={t(locale, "rec_copy_ph")}
                aria-invalid={needInput ? true : undefined} aria-describedby="rec-required rec-copy-count"
                onChange={(e) => { setText(e.target.value); if (e.target.value.trim()) setNeedInput(false); }}
                className={cn("mt-2 block w-full rounded-md border bg-white px-3 py-2 text-[15px] text-ink placeholder:text-steel", needInput ? "border-error" : "border-hairline-strong")} />
              <p id="rec-copy-count" className="mt-1 text-right text-[12px] text-steel tabular-nums">{text.length}/500</p>
            </div>

            <fieldset>
              <legend className={fieldLabel}>{t(locale, "rec_regions")}</legend>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <label className={cn(chipClass(all), chipInput)}>
                  <input type="checkbox" className="sr-only" checked={all} onChange={() => setRegions([])} />
                  <ChipMark on={all} />{t(locale, "dash_all")}
                </label>
                {TARGET_REGIONS.map((r) => {
                  const on = !all && regions.includes(r);
                  return (
                    <label key={r} className={cn(chipClass(on), chipInput)}>
                      <input type="checkbox" className="sr-only" checked={on} onChange={() => toggleRegion(r)} />
                      <ChipMark on={on} />{regionLabel(locale, r)}
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <fieldset aria-describedby="rec-tone-hint">
              <legend className={fieldLabel}>{t(locale, "rec_tone")}</legend>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {TONES.map((x) => (
                  <label key={x} className={cn(chipClass(tone === x), chipInput)}>
                    <input type="radio" name="rec-tone" value={x} className="sr-only" checked={tone === x} onChange={() => setTone(x)} />
                    <ChipMark on={tone === x} round />{labels.campaignTone[x]}
                  </label>
                ))}
              </div>
              <p id="rec-tone-hint" className="mt-2 text-[13px] leading-[1.5] text-steel">{t(locale, "rec_tone_hint")}</p>
            </fieldset>

            {/* 검정은 지금 단계의 다음 행동 하나 — 추천을 받은 뒤에는 '카피·대본 만들기' 가 검정이다 */}
            <Button type="submit" disabled={busy || genBusy} variant={result ? "outline" : "default"} className="h-11 w-full rounded-md text-[14px] sm:h-10">
              {busy ? t(locale, "rec_busy") : result ? t(locale, "rec_resubmit") : t(locale, "rec_submit")}
            </Button>
          </form>
        </div>

        <div className="min-w-0 space-y-5">
          {/* 화면 읽기 프로그램에 진행과 결과를 알린다 — 추천과 만들기 모두, 시작과 끝만 */}
          <p aria-live="polite" className="sr-only">{live}</p>
          {changed && !busy && <p className="border-b border-hairline pb-3 text-[13px] text-charcoal">{t(locale, "rec_input_changed")}</p>}
          {reqError && !busy && (
            <StatePanel role="alert" action={<Button type="button" variant="outline" className="h-10 rounded-md px-4" onClick={() => void submit()}>{t(locale, "rec_retry")}</Button>}>
              {t(locale, reqError)}
            </StatePanel>
          )}
          {busy && <StatePanel>{t(locale, "rec_waiting")}</StatePanel>}
          {!result && !busy && !reqError && <div className="hidden xl:block"><StatePanel>{t(locale, "rec_empty_body")}</StatePanel></div>}

          {result && !busy && view === "drafts" && (genBusy ? (
            <section aria-labelledby="gen-wait" className="rounded-lg border border-hairline px-6 py-6">
              <p id="gen-wait" className="text-[14px] leading-[1.6] text-ink">{t(locale, "gen_busy")}</p>
              <p className="mt-1 text-[13px] text-steel tabular-nums">{t(locale, "gen_elapsed").replace("{n}", String(elapsed))}</p>
              <Button ref={stopButton} type="button" variant="outline" className="mt-3 h-10 rounded-md px-4" onClick={stop}>{t(locale, "gen_stop")}</Button>
            </section>
          ) : gen && (
            <GenerationView result={gen} locale={locale} used={used} changed={genChanged}
              onRepick={() => setView("pick")} onRemake={() => void make()} />
          ))}

          {result && !busy && view === "pick" && (
            <section aria-labelledby="rec-results" className="space-y-5">
              <div>
                <h2 id="rec-results" tabIndex={-1} className="scroll-mt-20 text-[18px] font-semibold text-ink outline-none">
                  {t(locale, "rec_results").replace("{n}", String(result.items.length))}
                </h2>
                {result.items.length > 0 && <p className="mt-1 text-[14px] leading-[1.55] text-charcoal">{t(locale, "rec_note")}</p>}
              </div>

              {result.brief && (
                <section aria-labelledby="rec-brief" className="rounded-lg border border-hairline px-5 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 id="rec-brief" className="flex items-center gap-2 text-[15px] font-semibold text-ink">
                      {t(locale, "rec_brief")}
                      {result.brief_source === "sample" && <StatusBadge tone="muted">{t(locale, "rec_sample_badge")}</StatusBadge>}
                    </h3>
                    <button type="button" className="h-10 shrink-0 px-1 text-[13px] text-link-blue hover:underline md:hidden" aria-expanded={briefOpen} aria-controls="rec-brief-body"
                      onClick={() => setBriefOpen((o) => !o)}>{t(locale, briefOpen ? "rec_brief_hide" : "rec_brief_show")}</button>
                  </div>
                  <div id="rec-brief-body" className={cn(briefOpen ? "block" : "hidden", "md:block")}>
                    <dl className="mt-3 grid gap-x-6 gap-y-2 text-[14px] sm:grid-cols-2">
                      {([
                        ["rec_brief_product", result.brief.product, false],
                        ["rec_brief_category", category, false],
                        ["rec_brief_feelings", list(result.brief.feelings.map((f) => labels.feeling[f])), false],
                        ["rec_brief_values", list(result.brief.values ?? []), false],
                        ["rec_brief_scene", result.brief.scene ?? "", true],
                        ["rec_brief_avoid", list(result.brief.avoid ?? []), true],
                      ] as const).filter(([, v]) => v).map(([k, v, wide]) => (
                        <div key={k} className={cn("grid grid-cols-[88px_minmax(0,1fr)] gap-x-3", wide && "sm:col-span-2")}>
                          <dt className="text-steel">{t(locale, k)}</dt><dd className="text-ink">{v}</dd>
                        </div>
                      ))}
                    </dl>
                    {result.brief_source === "sample" && !sample && <p className="mt-3 text-[13px] text-charcoal">{t(locale, "rec_brief_sample")}</p>}
                    <p className="mt-3 text-[13px] leading-[1.5] text-steel">{t(locale, "rec_brief_fix")}</p>
                  </div>
                </section>
              )}

              {pinnedMissing && pinned && (
                <p className="text-[13px] leading-[1.5] text-charcoal">
                  {t(locale, "rec_pinned_missing").split("{name}").flatMap((part, i) => (i ? [<span key={i} lang={pinned.lang} className="font-medium text-ink">{pinned.name}</span>, part] : [part]))}
                </p>
              )}

              {result.items.length === 0 ? (
                <StatePanel action={!all || result.regions.length < TARGET_REGIONS.length ? (
                  <Button type="button" variant="outline" className="h-10 rounded-md px-4" onClick={() => { setRegions([]); void submit({ regions: [] }); }}>
                    {t(locale, "rec_retry_all")}
                  </Button>
                ) : undefined}>
                  {t(locale, result.brief_source === "none" ? "rec_not_ready" : "rec_none")}
                </StatePanel>
              ) : (
                <div aria-busy={genBusy} className="space-y-3">
                  <p className="text-[14px] font-medium text-ink">{t(locale, "gen_pick_hint")}</p>
                  <RecommendTable items={result.items} locale={locale} category={category} picked={picked} locked={genBusy} onToggle={togglePick} />
                  {/* 고른 밈과 만들기 — 표 아래에 붙어 따라온다(그림자 없이 위쪽 선만) */}
                  <div className="sticky bottom-0 z-10 -mx-4 space-y-2 border-t border-hairline bg-background px-4 py-3 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
                    {picked.length >= MAX_PICK && <p role="status" className="text-[13px] text-charcoal">{t(locale, "gen_limit")}</p>}
                    {picked.length > 0 && !chosenRegion && <p role="status" className="text-[13px] text-charcoal">{t(locale, "gen_no_region")}</p>}
                    {genError && <p role="alert" className="text-[13px] text-error">{t(locale, genError)}</p>}
                    {stopped && <p role="status" className="text-[13px] text-charcoal">{t(locale, "gen_stopped")}</p>}
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[14px]">
                        <span className="font-medium text-ink tabular-nums">{t(locale, "gen_picked").replace("{n}", String(picked.length))}</span>
                        <span className="flex items-center gap-2">
                          {regionOptions.length > 1 ? (
                            <>
                              <label htmlFor="gen-region" className="text-steel">{t(locale, "gen_region")}</label>
                              <select id="gen-region" value={chosenRegion} disabled={genBusy} onChange={(e) => setGenRegion(e.target.value)}
                                className="h-10 rounded-md border border-hairline-strong bg-white px-3 text-[14px] text-ink">
                                {regionOptions.map((r) => <option key={r} value={r}>{regionLabel(locale, r)}</option>)}
                              </select>
                            </>
                          ) : (
                            <><span className="text-steel">{t(locale, "gen_region")}</span><span className="text-ink">{chosenRegion ? regionLabel(locale, chosenRegion) : "—"}</span></>
                          )}
                        </span>
                      </div>
                      <Button ref={makeButton} type="button" disabled={genBusy || (picked.length > 0 && !chosenRegion)} onClick={() => void make()}
                        className="h-11 w-full rounded-md px-4 text-[14px] sm:h-10 sm:w-auto">
                        {t(locale, "gen_submit")}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
