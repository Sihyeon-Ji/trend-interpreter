"use client";

/* 시안 r-stage 의 만들기 상태 — 입력과 초안 실행을 한 곳에 둔다(React 밖의 작은 저장소, useSyncExternalStore 로 읽는다).
   만들기 → 초안 → 사전 항목 → 다시 초안으로 오가도 실행이 이어지고, 새로 고침하면 sessionStorage 에서 결과를 되살린다
   (사진 파일은 메모리에만, 저장하지 않는다). 부르는 순서는 components/make-flow.tsx 와 같다:
   /api/recommend → 시장마다 차례로 /api/generate → /api/copy-check → /api/poster. 백엔드는 모델 요청을 둘까지만 받으므로 시장은 차례로. */

import { useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import type { CampaignTone, CopyCheck, FitCategory, GenerationResult, PosterResult, RecommendItem, RecommendResult } from "@/lib/types";
import type { VerdictKind } from "./bits";
import { MARKETS, type Market } from "./copy";

export type Status = "wait" | "writing" | "checking" | "poster" | "done" | "failed" | "none" | "stopped";
export interface Column {
  market: Market;
  status: Status;
  pick: RecommendItem | null;
  alts: RecommendItem[];
  gen: GenerationResult | null;
  check: CopyCheck | null;
  checkFailed: boolean;
  poster: PosterResult | null;
  sign: { by: string; at: string } | null;
  rev: number;                     // 다시 쓸 때마다 올라간다 — 문구 등장 움직임을 다시 틀기 위해
  since?: string | null;           // 지금 단계를 시작한 때 — '몇 초째' 표시
}
export interface LiveWord { id: string; word: string; lang: string; gloss: string; verdict: VerdictKind }
export interface MarketLive { market: Market; count: number; words: LiveWord[]; failed?: boolean; at?: string | null }
export interface Pin { id: string; word: string; lang: string }
export interface Input { text: string; category: FitCategory | ""; tone: CampaignTone; markets: Market[]; pin: Pin | null }
export type RunError = "busy" | "failed" | "too_big" | "bad_type" | "need_input" | "stopped";
export interface Run {
  id: number;
  input: Input;
  phase: "reading" | "picked" | "error";
  error?: RunError;
  rec: RecommendResult | null;
  cols: Column[];
  at: string;
  locale: Locale;
  live: MarketLive[];
  photoUrl: string | null;
  active: Market | null;           // 무대 앞으로 나온 시장. null 이면 셋이 나란히
  follow: boolean;                 // 일하는 시장을 따라간다. 사람이 시장을 고르면 끈다
}
interface Photo { file: File; url: string }
interface State { input: Input; photo: Photo | null; run: Run | null }

const KEY = "r-stage-run-v1";
const DEFAULT_INPUT: Input = { text: "", category: "", tone: "friendly", markets: [...MARKETS], pin: null };
const SERVER: State = { input: DEFAULT_INPUT, photo: null, run: null };
const MAX_IMAGE = 5 * 1024 * 1024;
const BEAT_MS = 1600;              // 세 시장의 말이 나란히 서 있는 한 박자

let state: State = SERVER;
const listeners = new Set<() => void>();
let abort: AbortController | null = null;
let beatUntil = 0;
let doneAt = 0;                    // 앞에 선 시장이 끝난 때 — 다음 시장으로 넘어가기 전 잠깐 머문다
const DWELL_MS = 2600;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

function emit() {
  for (const l of listeners) l();
}

function persist() {
  if (typeof window === "undefined") return;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      const run = state.run;
      if (!run) sessionStorage.removeItem(KEY);
      else sessionStorage.setItem(KEY, JSON.stringify({ ...run, photoUrl: null }));
    } catch {
      /* 저장소가 막힌 브라우저 — 화면은 그대로 돈다 */
    }
  }, 150);
}

function set(next: Partial<State>) {
  state = { ...state, ...next };
  if ("run" in next) persist();
  emit();
}

function restore() {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return;
    const run = JSON.parse(raw) as Run;
    if (!run || !Array.isArray(run.cols)) return;
    const busy: Status[] = ["wait", "writing", "checking", "poster"];
    // 새로 고침으로 끊긴 요청은 이어 갈 수 없다 — 멈춘 곳을 알리고 다시 만들기 단추를 낸다
    const cols = run.cols.map((c) => (busy.includes(c.status) ? { ...c, status: "stopped" as Status } : c));
    const phase = run.phase === "reading" ? "error" : run.phase;
    state = { ...state, input: run.input ?? DEFAULT_INPUT, run: { ...run, cols, phase, error: run.phase === "reading" ? "stopped" : run.error, photoUrl: null } };
  } catch {
    /* 읽지 못하면 새로 시작 */
  }
}
if (typeof window !== "undefined") restore();

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useStage(): State {
  return useSyncExternalStore(subscribe, () => state, () => SERVER);
}

/* ---------- 입력 ---------- */

export function setInput(patch: Partial<Input>) {
  set({ input: { ...state.input, ...patch } });
}

export function toggleMarket(m: Market) {
  const cur = state.input.markets;
  const markets = cur.includes(m) ? cur.filter((x) => x !== m) : MARKETS.filter((x) => x === m || cur.includes(x));
  setInput({ markets });
}

/** 사진 고르기. 받을 수 없으면 오류 낱말을 돌려준다 */
export function setPhoto(file: File | null): "too_big" | "bad_type" | null {
  if (file && file.size > MAX_IMAGE) return "too_big";
  if (file && !["image/jpeg", "image/png", "image/webp"].includes(file.type)) return "bad_type";
  const old = state.photo;
  // 실행 중인 초안이 같은 사진을 포스터 자리에 쓰고 있으면 주소를 지우지 않는다
  if (old && old.url !== state.run?.photoUrl) URL.revokeObjectURL(old.url);
  set({ photo: file ? { file, url: URL.createObjectURL(file) } : null });
  return null;
}

/** 시작 화면에 주소로 넘어온 시장·밈을 한 번 넣는다(둘러보기·사전 항목의 '이 말로 초안 만들기') */
export function seedInput(markets: Market[] | null, pin: Pin | null) {
  const patch: Partial<Input> = {};
  if (markets?.length) patch.markets = markets;
  if (pin) patch.pin = pin;
  if (Object.keys(patch).length) setInput(patch);
}

/* ---------- 실행 ---------- */

async function post<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

function patchCol(runId: number, market: Market, p: Partial<Column>) {
  const run = state.run;
  if (!run || run.id !== runId) return;
  set({ run: { ...run, cols: run.cols.map((c) => (c.market === market ? { ...c, ...p } : c)) } });
}

function patchRun(runId: number, p: Partial<Run>) {
  const run = state.run;
  if (!run || run.id !== runId) return;
  set({ run: { ...run, ...p } });
}

const live = (runId: number) => state.run?.id === runId;

/** 시장 하나의 초안: 문구 → 다시 확인 → 포스터. 앞 단계가 실패하면 그 시장만 실패로 둔다 */
async function draft(runId: number, market: Market, item: RecommendItem, signal: AbortSignal) {
  const run = state.run;
  if (!run || run.id !== runId || !run.rec) return;
  const r = run.rec;
  const rev = (run.cols.find((c) => c.market === market)?.rev ?? 0) + 1;
  patchCol(runId, market, { status: "writing", gen: null, check: null, checkFailed: false, poster: null, sign: null, rev, since: new Date().toISOString() });
  // 일하는 시장을 무대 앞으로 — 한 박자 동안은 셋이 나란히, 앞 시장이 막 끝났으면 잠깐 머문 뒤에
  const wait = Math.max(beatUntil - Date.now(), doneAt + DWELL_MS - Date.now(), 0);
  const bring = () => { const r = state.run; if (r && r.id === runId && r.follow && r.cols.find((c) => c.market === market)?.status !== "wait") patchRun(runId, { active: market }); };
  if (run.follow) { if (wait > 0) setTimeout(bring, wait); else bring(); }
  let gen: GenerationResult;
  try {
    gen = await post<GenerationResult>("/api/generate", { term_ids: [item.term_id], brief: r.brief, region: market, tone: r.tone, lang: run.locale }, signal);
  } catch {
    if (live(runId) && !signal.aborted) patchCol(runId, market, { status: "failed" });
    return;
  }
  if (!live(runId)) return;
  patchCol(runId, market, { gen, status: "checking", since: new Date().toISOString() });
  const first = gen.copies.find((c) => c.platform === "instagram") ?? gen.copies[0];
  let check: CopyCheck | null = null;
  if (first) {
    try {
      check = await post<CopyCheck>("/api/copy-check", { text: first.text, region: market, lang: run.locale }, signal);
    } catch {
      check = null;
    }
  }
  if (!live(runId)) return;
  patchCol(runId, market, { check, checkFailed: !!first && !check, status: "poster" });
  const poster = await post<PosterResult>("/api/poster", { market, brief: r.brief, term_ids: [item.term_id] }, signal).catch(() => null);
  if (!live(runId)) return;
  patchCol(runId, market, { poster, status: "done" });
  doneAt = Date.now();
}

/** 초안 시작. 입력이 모자라면 오류 낱말을 돌려주고 시작하지 않는다 */
export function startRun(opts: { locale: Locale; live: MarketLive[] }): "need_input" | "need_market" | null {
  const { input, photo } = state;
  if (!input.markets.length) return "need_market";
  if (!input.text.trim() && !photo) return "need_input";
  abort?.abort();
  const ctrl = new AbortController();
  abort = ctrl;
  const id = (state.run?.id ?? 0) + 1;
  const markets = MARKETS.filter((m) => input.markets.includes(m));
  const cols: Column[] = markets.map((m) => ({ market: m, status: "wait", pick: null, alts: [], gen: null, check: null, checkFailed: false, poster: null, sign: null, rev: 0 }));
  set({
    run: {
      id, input: { ...input, markets }, phase: "reading", rec: null, cols, at: new Date().toISOString(), locale: opts.locale,
      live: opts.live.filter((l) => markets.includes(l.market)), photoUrl: photo?.url ?? null, active: null, follow: true,
    },
  });
  void recommend(id, ctrl.signal);
  return null;
}

async function recommend(runId: number, signal: AbortSignal) {
  const run = state.run;
  if (!run) return;
  const { input } = run;
  const body = new FormData();
  body.set("text", input.text.trim());
  body.set("tone", input.tone);
  body.set("lang", run.locale);
  body.set("regions", input.markets.join(","));
  if (input.category) body.set("category", input.category);
  if (input.pin) body.set("term", input.pin.id);
  if (state.photo && state.photo.url === run.photoUrl) body.set("image", state.photo.file);
  let rec: RecommendResult | null = null;
  try {
    const res = await fetch("/api/recommend", { method: "POST", body, signal });
    const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
    if (res.ok) rec = json;
    else {
      const e = json.error;
      patchRun(runId, { phase: "error", error: e === "busy" ? "busy" : e === "too_big" ? "too_big" : e === "bad_type" ? "bad_type" : e === "need_input" ? "need_input" : "failed" });
      return;
    }
  } catch {
    if (!signal.aborted) patchRun(runId, { phase: "error", error: "failed" });
    return;
  }
  if (!live(runId) || !rec) return;
  // 시장마다 그 나라 말로 쓸 수 있는 밈만(백엔드 generate 의 write_regions). 규칙 순위 그대로 — 첫째가 초안, 다음 둘이 다른 후보
  const cur = state.run!;
  const cols = cur.cols.map((c) => {
    const fit = rec!.items.filter((i) => i.write_regions.includes(c.market));
    return { ...c, status: (fit.length && rec!.brief ? "wait" : "none") as Status, pick: fit[0] ?? null, alts: fit.slice(1, 3) };
  });
  beatUntil = Date.now() + BEAT_MS;
  patchRun(runId, { rec, cols, phase: "picked", active: null });
  // 한 박자 뒤 일하는 시장을 무대 앞으로(사람이 그새 시장을 골랐으면 그대로 둔다)
  setTimeout(() => {
    const r = state.run;
    if (!r || r.id !== runId || !r.follow) return;
    const working = r.cols.find((c) => c.status === "writing" || c.status === "checking" || c.status === "poster") ?? r.cols.find((c) => c.pick);
    if (working) patchRun(runId, { active: working.market });
  }, BEAT_MS);
  for (const c of cols) {
    if (!live(runId) || signal.aborted) return;
    if (c.pick && c.status === "wait") await draft(runId, c.market, c.pick, signal);
  }
}

/** 시장 하나 다시 쓰기(다른 후보로 바꾸기 포함) */
export async function redo(market: Market, termId?: string) {
  const run = state.run;
  if (!run?.rec) return;
  const pool = run.rec.items.filter((i) => i.write_regions.includes(market));
  const col = run.cols.find((c) => c.market === market);
  const item = termId ? pool.find((i) => i.term_id === termId) : col?.pick;
  if (!item) return;
  if (!abort || abort.signal.aborted) abort = new AbortController();
  patchCol(run.id, market, { pick: item, alts: pool.filter((i) => i.term_id !== item.term_id).slice(0, 2) });
  set({ run: { ...state.run!, active: market } });
  await draft(run.id, market, item, abort.signal);
}

/** 처음부터 다시(멈춘 실행). 같은 입력으로 */
export function restart(locale: Locale) {
  const run = state.run;
  if (!run) return;
  set({ input: run.input });
  startRun({ locale, live: run.live });
}

/** 사람이 시장을 무대 앞으로 — 이후로는 일하는 시장을 따라가지 않는다 */
export function focusMarket(m: Market | null) {
  const run = state.run;
  if (!run) return;
  set({ run: { ...run, active: m, follow: false } });
}

export function sign(market: Market, by: string) {
  const run = state.run;
  if (run) patchCol(run.id, market, { sign: { by, at: new Date().toISOString() } });
}

export function unsign(market: Market) {
  const run = state.run;
  if (run) patchCol(run.id, market, { sign: null });
}

/** 지금 실행을 멈추고 버린다(입력은 남긴다) */
export function clearRun() {
  abort?.abort();
  abort = null;
  set({ run: null });
}
