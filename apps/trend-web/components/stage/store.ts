"use client";

/* 만들기 상태 — 입력과 초안 실행을 한 곳에 둔다(React 밖의 작은 저장소, useSyncExternalStore 로 읽는다).
   만들기 → 초안 → 사전 항목 → 다시 초안으로 오가도 실행이 이어지고, 새로 고침하면 sessionStorage 에서 결과를 되살린다
   (사진 파일은 메모리에만, 저장하지 않는다). 부르는 순서:
   /api/recommend → 시장마다 차례로 /api/generate → /api/copy-check/all(문구 모두 규칙으로, AI 의견은 한 문구에만) → /api/poster.
   백엔드는 모델 요청을 둘까지만 받으므로 시장은 차례로. 승인·검수 요청은 /api/approvals 가 서버에 적는다(로그인한 사람만). */

import { useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { fullText } from "@/lib/approval";
import type { ApprovalState, CampaignTone, CopyCheck, CopyChecks, FitCategory, GenerationResult, PosterResult, RecommendItem, RecommendResult } from "@/lib/types";
import type { VerdictKind } from "./bits";
import { MARKETS, type Market } from "./copy";

export type Status = "wait" | "writing" | "checking" | "poster" | "done" | "failed" | "none" | "stopped";
export interface Column {
  market: Market;
  status: Status;
  pick: RecommendItem | null;
  alts: RecommendItem[];
  gen: GenerationResult | null;
  checks: CopyCheck[] | null;      // 문구마다 규칙으로 다시 본 결과(gen.copies 와 같은 순서)
  opinion: number | null;          // AI 의견을 받은 문구의 번호 — 시장마다 한 번
  checkFailed: boolean;
  poster: PosterResult | null;
  approval: ApprovalState | null;  // 서버에 적은 검수 요청·승인(예시 모드면 sample, 적지 않음)
  sending: boolean;                // 요청·승인을 보내는 중
  sendError: SendError | null;
  rev: number;                     // 다시 쓸 때마다 올라간다 — 문구 등장 움직임을 다시 틀기 위해
  since?: string | null;           // 지금 단계를 시작한 때 — '몇 초째' 표시
}
export type SendError = "blocked" | "signed_out" | "forbidden" | "busy" | "failed";
export interface LiveWord { id: string; word: string; lang: string; gloss: string; verdict: VerdictKind; readings?: Record<string, string> }
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

const KEY = "stage-run-v2";        // v2: 문구마다의 검사(checks)와 서버 승인 기록(approval)
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
    const cols = run.cols.map((c) => ({ ...(busy.includes(c.status) ? { ...c, status: "stopped" as Status } : c), sending: false }));
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
  patchCol(runId, market, { status: "writing", gen: null, checks: null, opinion: null, checkFailed: false, poster: null, approval: null, sending: false,
    sendError: null, rev, since: new Date().toISOString() });
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
  // 문구 모두를 규칙으로 다시 본다. AI 의견은 첫 Instagram 문구 하나에만 — 시장마다 모델 한 번
  const ask = Math.max(0, gen.copies.findIndex((c) => c.platform === "instagram"));
  let got: CopyChecks | null = null;
  if (gen.copies.length) {
    try {
      got = await post<CopyChecks>("/api/copy-check/all", { texts: gen.copies.map(fullText), region: market, lang: run.locale, opinion: ask }, signal);
    } catch {
      got = null;
    }
  }
  if (!live(runId)) return;
  const checks = got && got.items.length === gen.copies.length ? got.items : null;
  patchCol(runId, market, { checks, opinion: checks ? got!.opinion : null, checkFailed: gen.copies.length > 0 && !checks, status: "poster" });
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
  const cols: Column[] = markets.map((m) => ({ market: m, status: "wait", pick: null, alts: [], gen: null, checks: null, opinion: null, checkFailed: false,
    poster: null, approval: null, sending: false, sendError: null, rev: 0 }));
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

/** 다시 확인만 — 규칙 검사가 시간 안에 안 돌아왔을 때(504) 같은 문구를 다시 본다. 문구는 그대로 둔다(10-15 데모 점검) */
export async function recheck(market: Market) {
  const run = state.run;
  const col = run?.cols.find((c) => c.market === market);
  if (!run || !col?.gen?.copies.length) return;
  if (!abort || abort.signal.aborted) abort = new AbortController();
  const gen = col.gen;
  patchCol(run.id, market, { status: "checking", checkFailed: false });
  const ask = Math.max(0, gen.copies.findIndex((c) => c.platform === "instagram"));
  const got = await post<CopyChecks>("/api/copy-check/all", { texts: gen.copies.map(fullText), region: market, lang: run.locale, opinion: ask }, abort.signal)
    .catch(() => null);
  if (!live(run.id)) return;
  const checks = got && got.items.length === gen.copies.length ? got.items : null;
  patchCol(run.id, market, { checks, opinion: checks ? got!.opinion : null, checkFailed: !checks, status: "done" });
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

/** AI 의견(시장마다 한 번) — 의견을 받은 문구에서 고른 밈의 것, 없으면 그 문구의 첫 의견 */
export function opinionOf(col: Column) {
  const check = col.opinion != null ? col.checks?.[col.opinion] : undefined;
  const memes = check?.memes ?? [];
  return memes.find((m) => m.fit && m.term_id === col.pick?.term_id) ?? memes.find((m) => m.fit) ?? null;
}

/** 검수 요청(로그인한 계정) 또는 검수자의 바로 승인. 서버가 세션·권한을 다시 보고 규칙 검사도 다시 한다 —
 *  보내는 것은 시장·고른 밈·제품 한 줄·문구들·AI 의견뿐이고, 요청한 사람의 이름은 서버가 세션에서 넣는다 */
export async function submitApproval(market: Market, approve: boolean) {
  const run = state.run;
  const col = run?.cols.find((c) => c.market === market);
  if (!run || !col?.gen || !col.pick || col.sending) return;
  const fit = opinionOf(col);
  const rev = col.rev;
  // 그사이 다시 쓴 초안에 옛 문구의 결과를 붙이지 않는다(같은 실행 안에서 다시 쓰면 rev 가 오른다)
  const same = () => state.run?.id === run.id && state.run.cols.find((c) => c.market === market)?.rev === rev;
  patchCol(run.id, market, { sending: true, sendError: null });
  let res: Response;
  try {
    res = await fetch("/api/approvals", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        market, term_id: col.pick.term_id, product: (run.rec?.brief?.product ?? run.input.text).trim().slice(0, 200),
        copies: col.gen.copies.map((c) => ({ platform: c.platform, text: c.text, hashtags: c.hashtags ?? [] })),
        fit: fit?.fit ?? null, fit_note: fit?.fit_note ?? null, fit_copy: fit ? col.opinion : null, decision: approve ? "approve" : null,
      }),
    });
  } catch {
    if (same()) patchCol(run.id, market, { sending: false, sendError: "failed" });
    return;
  }
  const json = (await res.json().catch(() => ({}))) as ApprovalState & { error?: string };
  if (!same()) return;
  if (res.ok) { patchCol(run.id, market, { sending: false, approval: json }); return; }
  const err: SendError = json.error === "blocked" ? "blocked" : res.status === 401 ? "signed_out" : res.status === 403 ? "forbidden" : res.status === 429 ? "busy" : "failed";
  patchCol(run.id, market, { sending: false, sendError: err });
}

/** 기다리는 요청의 상태를 다시 읽는다(초안 화면을 열 때·다시 볼 때) — 검수자가 관리 화면에서 정한 결과가 여기로 온다 */
export async function refreshApprovals() {
  const run = state.run;
  if (!run) return;
  for (const col of run.cols) {
    const a = col.approval;
    if (!a || a.sample || a.status !== "pending") continue;
    try {
      const res = await fetch(`/api/approvals/${encodeURIComponent(a.approval_id)}`, { cache: "no-store" });
      if (!res.ok) continue;
      const next = (await res.json()) as ApprovalState;
      // 기다리는 사이 다시 썼으면(요청이 지워졌으면) 옛 요청의 결과를 새 초안에 붙이지 않는다
      if (state.run?.id === run.id && state.run.cols.find((c) => c.market === col.market)?.approval?.approval_id === a.approval_id) {
        patchCol(run.id, col.market, { approval: next });
      }
    } catch {
      /* 다음에 다시 본다 */
    }
  }
}

/** 지금 실행을 멈추고 버린다(입력은 남긴다) */
export function clearRun() {
  abort?.abort();
  abort = null;
  set({ run: null });
}
