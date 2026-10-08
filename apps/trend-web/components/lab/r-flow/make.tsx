"use client";

/* 만들기 — 입력 상자(제품·사진·시장·분야·말투) → 같은 화면에서 실행으로 펼쳐진다.
   순서는 components/make-flow.tsx 와 같다: /api/recommend(규칙이 시장마다 밈을 고름, AI 가 제품을 읽음) →
   시장마다 차례로 /api/generate(AI 문구) → /api/copy-check(규칙 재검사 + AI 의견) → /api/poster(규칙 구성안) → 사람 승인.
   백엔드는 모델 요청을 한 인스턴스에 둘까지만 받으므로 시장은 차례로 만든다. 결과는 서버에 저장하지 않고 이 브라우저에만 남긴다. */
import Link from "next/link";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ImagePlus, Pencil, RotateCcw, Square, X } from "lucide-react";
import type { Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L } from "@/lib/labels";
import type { CampaignTone, CopyCheck, FitCategory, GenerationResult, PosterResult, RecommendItem, RecommendResult } from "@/lib/types";
import { MARKETS, marketName, num, tr, type CopyKey, type Market } from "./copy";
import { Mark } from "./glyph";
import { LaneDetail, flaggedCopy, type LaneState } from "./lane";
import { Matrix, STEPS, ghostLanes, type CellView, type LaneView, type Step, type StepKey } from "./matrix";
import { createStore, useStore } from "./store";

const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
const TONE_HINT: Record<CampaignTone, CopyKey> = { friendly: "tone_friendly_hint", witty: "tone_witty_hint", premium: "tone_premium_hint" };

export interface Pinned { id: string; name: string; lang: string }
interface Input { text: string; markets: Market[]; category: FitCategory | ""; tone: CampaignTone; photo: boolean; pin: Pinned | null }
type Phase = "reading" | "running" | "done" | "stopped" | "error";
interface Run { id: string; at: number; input: Input; rec: RecommendResult | null; lanes: LaneState[]; phase: Phase; error?: CopyKey; restored?: boolean }

const NO_RUNS: Run[] = [];
const runs = createStore<Run[]>("rf-runs-v1", NO_RUNS, (raw) => {
  const v = JSON.parse(raw) as unknown;
  return Array.isArray(v) ? (v.filter((r) => r && typeof r.id === "string" && Array.isArray(r.lanes)) as Run[]).slice(0, 4) : NO_RUNS;
});
/** 저장할 때는 근거 목록을 빼 크기를 줄이고, 돌던 단계는 '멈춤' 으로 */
function save(run: Run) {
  const slim: Run = {
    ...run,
    rec: run.rec ? { ...run.rec, items: run.rec.items.map((i) => ({ ...i, evidences: [] })) } : null,
    lanes: run.lanes.map((l) => ({ ...l, fresh: undefined, alts: l.alts.map((a) => ({ ...a, evidences: [] })), pick: l.pick ? { ...l.pick, evidences: [] } : null })),
    restored: undefined,
  };
  runs.write([slim, ...runs.read().filter((r) => r.id !== run.id)].slice(0, 4));
}

async function post<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

/** 지금 시각 — 이벤트·요청 흐름에서만 부른다(렌더 중에는 부르지 않는다) */
const clock = () => Date.now();
const wait = (): Step => ({ s: "wait" });
const fresh = (): Record<StepKey, Step> => ({ pick: wait(), write: wait(), check: wait(), poster: wait(), sign: wait() });

const stamp = (locale: Locale, t = clock()) =>
  new Date(t).toLocaleString(locale === "ko" ? "ko-KR" : "en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

/** 진행표 한 줄에 보일 글 — 받은 결과를 짧게 옮긴다 */
function cellsOf(lane: LaneState, rec: RecommendResult | null, locale: Locale): Record<StepKey, CellView> {
  const st = lane.steps;
  const m = lane.market;
  const pool = rec?.pool?.[m] ?? 0;
  const n = rec?.considered_by_region?.[m] ?? 0;
  const copies = lane.gen?.copies ?? [];
  const flagged = lane.check ? copies.filter((c) => flaggedCopy(c, lane.check, lane.pick?.term_id)).length : 0;
  const waitCell = (s: Step["s"]): CellView => ({ main: s === "stop" ? tr(locale, "cell_stop") : s === "none" ? "–" : tr(locale, "cell_wait") });
  const pick: CellView = st.pick.s === "run" ? { main: tr(locale, "cell_pick_run") }
    : st.pick.s === "fail" ? { main: tr(locale, "run_fail_failed").split(/[.。]/)[0] }
      : lane.pick ? { main: lane.pick.canonical, lang: lane.pick.lang, word: true, meta: lane.by === "rule" ? tr(locale, "cell_pick_meta", { pool: num(pool), n: num(n) }) : tr(locale, lane.by === "swap" ? "cell_pick_swapped" : "cell_pick_pinned"), actor: lane.by === "rule" ? "rule" : "person" }
        : st.pick.s === "none" ? { main: tr(locale, "cell_pick_none"), meta: tr(locale, "cell_pick_none_meta", { pool: num(pool) }) }
          : waitCell(st.pick.s);
  const write: CellView = st.write.s === "run" ? { main: tr(locale, "cell_write_run") }
    : st.write.s === "fail" ? { main: tr(locale, "cell_write_fail") }
      : lane.gen ? { main: tr(locale, "cell_write_done", { n: copies.length }), meta: [lane.gen.script ? tr(locale, "cell_write_script") : "", lane.gen.dropped.length ? tr(locale, "cell_write_dropped", { n: lane.gen.dropped.length }) : ""].filter(Boolean).join(", ") || undefined }
        : waitCell(st.write.s);
  const check: CellView = st.check.s === "run" ? { main: tr(locale, "cell_check_run") }
    : st.check.s === "fail" ? { main: tr(locale, "cell_check_fail") }
      : lane.check ? (flagged ? { main: tr(locale, "cell_check_flag", { f: flagged }), meta: issueSummary(lane, locale) } : { main: tr(locale, "cell_check_ok", { n: copies.length }) })
        : waitCell(st.check.s);
  const poster: CellView = st.poster.s === "run" ? { main: tr(locale, "cell_poster_run") }
    : st.poster.s === "fail" ? { main: tr(locale, "cell_poster_fail") }
      : lane.poster ? { main: tr(locale, "cell_poster_done"), meta: lane.poster.images.length ? tr(locale, "cell_poster_img", { n: lane.poster.images.length }) : tr(locale, "cell_poster_off") }
        : waitCell(st.poster.s);
  const sign: CellView = lane.sign ? { main: tr(locale, "cell_sign_done", { name: lane.sign.by }), meta: lane.sign.at }
    : st.sign.s === "wait" && lane.poster ? { main: tr(locale, "cell_sign_wait") } : waitCell(st.sign.s);
  return { pick, write, check, poster, sign };
}

function issueSummary(lane: LaneState, locale: Locale): string | undefined {
  const pm = lane.check?.memes.find((x) => x.term_id === lane.pick?.term_id);
  const parts: string[] = [];
  if (pm) {
    for (const i of pm.issues) parts.push(tr(locale, (`issue_${i.code}`) as CopyKey));
    if (pm.fit && pm.fit !== "ok") parts.push(`AI: ${tr(locale, pm.fit === "off" ? "fit_off" : "fit_unsure")}`);
  }
  return parts.length ? parts.join(", ") : undefined;
}

/** 실행 머리의 한 줄 — 지금 누가 무엇을 하는지(도는 단계), 끝나면 사람이 할 일 */
function Status({ run, locale }: { run: Run; locale: Locale }) {
  const going = run.lanes.flatMap((l) => STEPS.filter((s) => l.steps[s.key].s === "run").map((s) => ({ l, s })))[0];
  const waiting = run.lanes.filter((l) => l.pick && !l.sign && l.poster).length;
  const picked = run.lanes.filter((l) => l.pick).length;
  let actor: "rule" | "ai" | "person" = "rule";
  let text = "";
  if (run.phase === "reading") { actor = "ai"; text = tr(locale, "now_reading"); }
  else if (going) {
    const market = marketName(locale, going.l.market);
    actor = going.s.actor;
    text = tr(locale, going.s.key === "write" ? "now_write" : going.s.key === "check" ? "now_check" : "now_poster", { market });
  } else if (run.phase === "stopped") text = tr(locale, "now_stopped");
  else if (run.phase === "error") return null;
  else if (picked && run.lanes.every((l) => !l.pick || l.sign)) { actor = "person"; text = tr(locale, "now_all"); }
  else if (waiting) { actor = "person"; text = tr(locale, "now_wait", { n: waiting }); }
  if (!text) return null;
  return (
    <p className="rf-status" data-tone={actor} role="status">
      <Mark actor={actor} filled={!going && run.phase !== "reading" ? actor !== "person" || waiting === 0 : true} />
      <b>{text}</b>
      {(going || run.phase === "reading") && <span className="rf-dots" aria-hidden="true" style={{ color: actor === "ai" ? "var(--rf-ai)" : "var(--rf-ink)" }}><i /><i /><i /></span>}
    </p>
  );
}

export function Make({ locale, counts, initialMarkets, pinned, signer, sample }: {
  locale: Locale; counts: Record<string, number> | null; initialMarkets: Market[]; pinned: Pinned | null; signer: string | null; sample: boolean;
}) {
  const labels = L(locale);
  const categories = Object.keys(labels.fitCategory) as FitCategory[];
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [markets, setMarkets] = useState<Market[]>(initialMarkets);
  const [category, setCategory] = useState<FitCategory | "">("");
  const [tone, setTone] = useState<CampaignTone>("friendly");
  const [pin, setPin] = useState<Pinned | null>(pinned);
  const [msg, setMsg] = useState<CopyKey | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [sel, setSel] = useState<Market | null>(null);
  const [live, setLive] = useState("");
  const saved = useStore(runs);
  const seq = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const follow = useRef(true);
  const current = useRef<Run | null>(null);
  const head = useRef<HTMLHeadingElement>(null);

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => () => abort.current?.abort(), []);

  // 1·2·3 으로 시장 바꾸기(입력 중이 아닐 때)
  useEffect(() => {
    if (!run) return;
    const key = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      const idx = Number(e.key) - 1;
      const lane = run.lanes[idx];
      if (lane) { follow.current = false; setSel(lane.market); }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [run]);

  /** 실행 상태의 원본은 ref 하나 — 이어지는 요청이 늘 최신 값을 읽고, 화면에는 같은 값을 넘긴다 */
  const commit = (next: Run | null) => {
    current.current = next;
    setRun(next);
  };
  const update = (fn: (r: Run) => Run) => {
    const r = current.current;
    if (r) commit(fn(r));
  };
  const patchLane = (id: string, market: Market, fn: (l: LaneState) => LaneState) =>
    update((r) => (r.id !== id ? r : { ...r, lanes: r.lanes.map((l) => (l.market === market ? fn(l) : l)) }));
  const step = (l: LaneState, k: StepKey, s: Step["s"]): LaneState => {
    const now = clock();
    const prev = l.steps[k];
    const next: Step = s === "run" ? { s, t0: now } : s === "wait" || s === "none" ? { s } : { s, t0: prev.t0, t1: now };
    return { ...l, steps: { ...l.steps, [k]: next } };
  };
  const announce = (market: Market, k: StepKey, result: string) =>
    setLive(tr(locale, "live_done", { market: marketName(locale, market), step: tr(locale, STEPS.find((s) => s.key === k)!.title), result }));

  const toggle = (m: Market) => {
    setMsg(null);
    setMarkets((cur) => (cur.includes(m) ? cur.filter((x) => x !== m) : MARKETS.filter((x) => x === m || cur.includes(x))));
  };
  const pickPhoto = (f: File | null) => {
    setMsg(null);
    if (f && (f.size > MAX_IMAGE || !["image/jpeg", "image/png", "image/webp"].includes(f.type))) {
      setMsg(f.size > MAX_IMAGE ? "mk_too_big" : "mk_bad_type");
      setInputKey((k) => k + 1);
      return;
    }
    if (!f) setInputKey((k) => k + 1);
    setPhoto(f ? { file: f, url: URL.createObjectURL(f) } : null);
  };

  /** 시장 하나: 문구 → 다시 검사 → 포스터. 앞 단계가 실패하면 그 시장만 멈춘다 */
  const draft = async (id: string, market: Market, item: RecommendItem, rec: RecommendResult, my: number, signal: AbortSignal) => {
    const alive = () => my === seq.current && !signal.aborted;
    if (follow.current) setSel(market);
    patchLane(id, market, (l) => step(step(step(step({ ...l, gen: null, check: null, poster: null, sign: null }, "write", "run"), "check", "wait"), "poster", "wait"), "sign", "wait"));
    let gen: GenerationResult;
    try {
      gen = await post<GenerationResult>("/api/generate", { term_ids: [item.term_id], brief: rec.brief, region: market, tone: rec.tone, lang: locale }, signal);
    } catch {
      if (alive()) patchLane(id, market, (l) => step(l, "write", "fail"));
      return;
    }
    if (!alive()) return;
    patchLane(id, market, (l) => step(step({ ...l, gen, fresh: { ...l.fresh, copies: clock() } }, "write", "done"), "check", "run"));
    announce(market, "write", tr(locale, "cell_write_done", { n: gen.copies.length }));
    const first = gen.copies.find((c) => c.platform === "instagram") ?? gen.copies[0];
    let check: CopyCheck | null = null;
    if (first) check = await post<CopyCheck>("/api/copy-check", { text: first.text, region: market, lang: locale }, signal).catch(() => null);
    if (!alive()) return;
    const flagged = check ? gen.copies.filter((c) => flaggedCopy(c, check, item.term_id)).length : 0;
    const pm = check?.memes.find((x) => x.term_id === item.term_id);
    const warn = !!check && (flagged > 0 || (!!pm?.fit && pm.fit !== "ok"));
    patchLane(id, market, (l) => step(step({ ...l, check }, "check", check ? (warn ? "warn" : "done") : "fail"), "poster", "run"));
    announce(market, "check", check ? (flagged ? tr(locale, "cell_check_flag", { f: flagged }) : tr(locale, "cell_check_ok", { n: gen.copies.length })) : tr(locale, "cell_check_fail"));
    const poster = await post<PosterResult>("/api/poster", { market, brief: rec.brief, term_ids: [item.term_id] }, signal).catch(() => null);
    if (!alive()) return;
    patchLane(id, market, (l) => step(step({ ...l, poster }, "poster", poster ? "done" : "fail"), "sign", "wait"));
    if (current.current) save(current.current);
  };

  const start = async (inp?: Input) => {
    const input: Input = inp ?? { text: text.trim(), markets, category, tone, photo: !!photo, pin };
    if (!input.markets.length) { setMsg("mk_need_market"); return; }
    if (!input.text && !photo) { setMsg("mk_need_input"); return; }
    const my = ++seq.current;
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    follow.current = true;
    setMsg(null);
    const id = `r${clock().toString(36)}`;
    const t0 = clock();
    const lanes: LaneState[] = input.markets.map((m) => ({ market: m, steps: { ...fresh(), pick: { s: "run", t0 } }, pick: null, alts: [], by: "rule", gen: null, check: null, poster: null, sign: null }));
    commit({ id, at: t0, input, rec: null, lanes, phase: "reading" });
    setSel(input.markets[0]);
    requestAnimationFrame(() => head.current?.focus({ preventScroll: true }));

    const body = new FormData();
    body.set("text", input.text);
    body.set("tone", input.tone);
    body.set("lang", locale);
    body.set("regions", input.markets.join(","));
    if (input.category) body.set("category", input.category);
    if (input.pin) body.set("term", input.pin.id);
    if (photo && input.photo) body.set("image", photo.file);
    let rec: RecommendResult | null = null;
    let err: CopyKey = "run_fail_failed";
    try {
      const res = await fetch("/api/recommend", { method: "POST", body, signal: ctrl.signal });
      const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
      if (res.ok) rec = json;
      else err = json.error === "busy" ? "run_fail_busy" : json.error === "too_big" ? "run_fail_too_big" : json.error === "bad_type" ? "run_fail_bad_type" : "run_fail_failed";
    } catch {
      if (ctrl.signal.aborted) return;
    }
    if (my !== seq.current) return;
    if (!rec) {
      update((r) => ({ ...r, phase: "error", error: err, lanes: r.lanes.map((l) => step(l, "pick", "fail")) }));
      return;
    }
    const got = rec;
    // 시장마다 그 나라 말로 쓸 수 있는 밈만(규칙 순위 그대로). 고정한 밈이 그 시장에 맞으면 그것을, 아니면 첫째를
    update((r) => ({
      ...r, rec: got, phase: "running",
      lanes: r.lanes.map((l) => {
        const fit = got.items.filter((i) => i.write_regions.includes(l.market));
        const pinnedItem = input.pin ? fit.find((i) => i.term_id === input.pin!.id) : undefined;
        const pick = pinnedItem ?? fit[0] ?? null;
        const alts = fit.filter((i) => i.term_id !== pick?.term_id).slice(0, 2);
        const base: LaneState = { ...l, pick, alts, by: pinnedItem ? "pin" : "rule" };
        if (!pick) return { ...base, steps: { pick: { s: "none", t0, t1: clock() }, write: { s: "none" }, check: { s: "none" }, poster: { s: "none" }, sign: { s: "none" } } };
        return step(base, "pick", "done");
      }),
    }));
    setLive(tr(locale, "run_brief") + ": " + (got.brief?.product ?? ""));
    for (const m of input.markets) {
      if (my !== seq.current) return;
      const lane = current.current?.lanes.find((l) => l.market === m);
      if (lane?.pick) await draft(id, m, lane.pick, got, my, ctrl.signal);
    }
    if (my !== seq.current) return;
    update((r) => ({ ...r, phase: "done" }));
    if (current.current) save(current.current);
  };

  const redo = async (market: Market, termId?: string) => {
    const r = current.current;
    if (!r?.rec) return;
    const fit = r.rec.items.filter((i) => i.write_regions.includes(market));
    const lane = r.lanes.find((l) => l.market === market);
    const item = termId ? fit.find((i) => i.term_id === termId) : lane?.pick;
    if (!item) return;
    follow.current = false;
    setSel(market);
    const ctrl = abort.current && !abort.current.signal.aborted ? abort.current : new AbortController();
    abort.current = ctrl;
    // 사람이 바꾼 고르기에는 걸린 시간을 달지 않는다
    if (termId) patchLane(r.id, market, (l) => ({ ...l, steps: { ...l.steps, pick: { s: "done" } }, pick: item, alts: fit.filter((i) => i.term_id !== item.term_id).slice(0, 2), by: "swap" }));
    update((x) => ({ ...x, phase: "running", restored: false }));
    await draft(r.id, market, item, r.rec, seq.current, ctrl.signal);
    update((x) => ({ ...x, phase: x.lanes.some((l) => STEPS.some((s) => l.steps[s.key].s === "run")) ? "running" : "done" }));
  };

  const stop = () => {
    seq.current++;
    abort.current?.abort();
    update((r) => ({ ...r, phase: "stopped", lanes: r.lanes.map((l) => ({ ...l, steps: Object.fromEntries(STEPS.map((s) => [s.key, l.steps[s.key].s === "run" ? { s: "stop" } : l.steps[s.key]])) as Record<StepKey, Step> })) }));
    if (current.current) save(current.current);
  };

  const sign = (market: Market) => {
    const by = signer ?? tr(locale, "dt_reviewer");
    const at = stamp(locale);
    if (!current.current) return;
    patchLane(current.current.id, market, (l) => ({ ...step(l, "sign", "done"), sign: { by, at }, fresh: { ...l.fresh, sign: clock() } }));
    announce(market, "sign", tr(locale, "cell_sign_done", { name: by }));
    if (current.current) save(current.current);
  };
  const unsign = (market: Market) => {
    if (!current.current) return;
    patchLane(current.current.id, market, (l) => ({ ...step(l, "sign", "wait"), sign: null }));
    if (current.current) save(current.current);
  };

  const edit = () => {
    seq.current++;
    abort.current?.abort();
    if (run) { setText(run.input.text); setMarkets(run.input.markets); setCategory(run.input.category); setTone(run.input.tone); setPin(run.input.pin); }
    commit(null);
  };
  const restore = (r: Run) => {
    seq.current++;
    abort.current?.abort();
    const fixed: Run = { ...r, restored: true, phase: r.phase === "reading" || r.phase === "running" ? "stopped" : r.phase,
      lanes: r.lanes.map((l) => ({ ...l, steps: Object.fromEntries(STEPS.map((s) => [s.key, l.steps[s.key].s === "run" ? { s: "stop" } : l.steps[s.key]])) as Record<StepKey, Step> })) };
    follow.current = false;
    commit(fixed);
    setSel(fixed.lanes.find((l) => l.pick)?.market ?? fixed.lanes[0]?.market ?? null);
    requestAnimationFrame(() => {
      head.current?.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  };

  const ready = markets.length > 0 && (text.trim().length > 0 || !!photo);
  const lanesView: LaneView[] = run
    ? run.lanes.map((l) => ({ market: l.market, steps: l.steps, cells: cellsOf(l, run.rec, locale), sub: l.sign ? tr(locale, "dt_signed", { name: l.sign.by }) : tr(locale, `market_${l.market}_lang`) }))
    : ghostLanes(markets, locale);
  const lane = run?.lanes.find((l) => l.market === sel) ?? null;
  const signed = run?.lanes.filter((l) => l.sign).length ?? 0;
  const busy = run?.phase === "reading" || run?.phase === "running";

  return (
    <LayoutGroup>
      <p className="rf-sr" aria-live="polite">{live}</p>
      <AnimatePresence mode="popLayout" initial={false}>
        {!run ? (
          <motion.div key="compose" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10, transition: { duration: 0.16 } }} transition={{ duration: 0.24, ease: [0.2, 0, 0, 1] }}>
            <div className="rf-head">
              <div>
                <h1 className="rf-title">{tr(locale, "mk_title")}</h1>
                <p className="rf-lead" id="rf-mk-lead">{tr(locale, "mk_lead")}</p>
              </div>
            </div>
            <form className="rf-composer" aria-describedby="rf-mk-lead" onSubmit={(e) => { e.preventDefault(); void start(); }}>
              <div className="rf-composer-body">
                <label className="rf-photo" data-has={!!photo}>
                  <input key={inputKey} type="file" accept="image/jpeg,image/png,image/webp" aria-label={tr(locale, "mk_photo")} onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
                  {photo
                    // eslint-disable-next-line @next/next/no-img-element
                    ? <img src={photo.url} alt={tr(locale, "mk_photo_alt")} />
                    : <><ImagePlus size={20} strokeWidth={1.5} aria-hidden="true" /><span className="rf-sr">{tr(locale, "mk_photo_hint")}</span></>}
                </label>
                <textarea
                  id="rf-pitch" value={text} rows={3} maxLength={500} placeholder={tr(locale, "mk_pitch_ph")} aria-label={tr(locale, "mk_pitch")}
                  onChange={(e) => { setText(e.target.value); if (msg === "mk_need_input") setMsg(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void start(); } }}
                />
              </div>
              {(photo || pin) && (
                <div className="rf-pin">
                  {photo && <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={() => pickPhoto(null)}><X size={13} aria-hidden="true" />{tr(locale, "mk_photo_remove")}</button>}
                  {pin && (
                    <>
                      <span>{tr(locale, "mk_pinned")}</span><b lang={langTag(pin.lang)}>{pin.name}</b>
                      <span className="rf-muted">{tr(locale, "mk_pinned_note")}</span>
                      <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={() => setPin(null)}>{tr(locale, "mk_unpin")}</button>
                    </>
                  )}
                </div>
              )}
              <div className="rf-props">
                <div className="rf-prop" role="group" aria-labelledby="rf-k-markets">
                  <span className="rf-prop-k" id="rf-k-markets">{tr(locale, "mk_markets")}</span>
                  <div className="rf-toggles">
                    {MARKETS.map((m) => (
                      <button key={m} type="button" className="rf-toggle" aria-pressed={markets.includes(m)} onClick={() => toggle(m)}>
                        <Check size={13} strokeWidth={2.25} aria-hidden="true" />{marketName(locale, m)}{counts?.[m] != null && <small>{num(counts[m])}</small>}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="rf-prop">
                  <label className="rf-prop-k" htmlFor="rf-cat">{tr(locale, "mk_category")}</label>
                  <span className="rf-select">
                    <select id="rf-cat" value={category} onChange={(e) => setCategory(e.target.value as FitCategory | "")}>
                      <option value="">{tr(locale, "mk_auto")}</option>
                      {categories.map((c) => <option key={c} value={c}>{labels.fitCategory[c]}</option>)}
                    </select>
                    <ChevronDown size={14} strokeWidth={2} aria-hidden="true" />
                  </span>
                </div>
                <div className="rf-prop" role="radiogroup" aria-labelledby="rf-k-tone">
                  <span className="rf-prop-k" id="rf-k-tone">{tr(locale, "mk_tone")}</span>
                  <span className="rf-seg">
                    {TONES.map((tn) => (
                      <button key={tn} type="button" role="radio" aria-checked={tone === tn} title={tr(locale, TONE_HINT[tn])} onClick={() => setTone(tn)}>
                        {tone === tn && <motion.span layoutId="rf-tone-thumb" className="rf-seg-thumb" transition={{ type: "spring", duration: 0.32, bounce: 0 }} />}
                        {labels.campaignTone[tn]}
                      </button>
                    ))}
                  </span>
                </div>
                <div className="rf-submit">
                  <button type="submit" className="rf-btn" disabled={!ready}>{tr(locale, "mk_submit")}<span className="rf-kbd" aria-hidden="true">⌘↵</span></button>
                </div>
              </div>
            </form>
            <p className="rf-form-msg" role={msg ? "alert" : undefined}>
              {msg ? <span className="rf-error">{tr(locale, msg)}</span> : !ready ? tr(locale, markets.length ? "mk_need_input" : "mk_need_market") : tr(locale, "mk_markets_hint", { n: markets.length })}
            </p>
          </motion.div>
        ) : (
          <motion.div key="run" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, transition: { duration: 0.12 } }} transition={{ duration: 0.26, ease: [0.2, 0, 0, 1] }}>
            <section className="rf-runbar" aria-labelledby="rf-run-h">
              <div className="rf-runbar-top">
                <h1 className="rf-runbar-title" id="rf-run-h" ref={head} tabIndex={-1}>{run.rec?.brief?.product ?? run.input.text}</h1>
                {run.restored && <span className="rf-chip">{tr(locale, "run_restored", { at: stamp(locale, run.at) })}</span>}
                <div className="rf-runbar-tools">
                  <span className="rf-tally" data-on={signed > 0} aria-live="polite"><Mark actor="person" filled={signed > 0} />{tr(locale, "run_approved", { a: signed, n: run.lanes.filter((l) => l.pick).length })}</span>
                  <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={edit}><Pencil size={13} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "run_edit")}</button>
                  {busy
                    ? <button type="button" className="rf-btn" data-kind="line" data-size="s" onClick={stop}><Square size={11} strokeWidth={2.5} aria-hidden="true" />{tr(locale, "run_stop")}</button>
                    : <button type="button" className="rf-btn" data-kind="line" data-size="s" onClick={() => void start(run.input)} disabled={run.input.photo && !photo}><RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "run_again")}</button>}
                </div>
              </div>
              {run.rec?.brief ? (
                <div className="rf-runbar-meta">
                <span className="rf-who" data-actor="ai"><Mark actor="ai" />{tr(locale, run.rec.brief_source === "sample" ? "run_brief_sample" : "run_brief")}</span>
                <dl className="rf-runbar-props">
                  <div><dt>{tr(locale, "run_category")}</dt><dd>{labels.fitCategory[run.rec.brief.category]}{!run.input.category && <span className="rf-muted" style={{ fontWeight: 400 }}> ({tr(locale, "run_auto")})</span>}</dd></div>
                  {run.rec.brief.feelings.length > 0 && <div><dt>{tr(locale, "run_feelings")}</dt><dd>{run.rec.brief.feelings.map((f) => labels.feeling[f]).join(", ")}</dd></div>}
                  <div><dt>{tr(locale, "run_tone")}</dt><dd>{labels.campaignTone[run.rec.tone]}</dd></div>
                  <div><dt>{tr(locale, "run_markets")}</dt><dd>{run.lanes.map((l) => marketName(locale, l.market)).join(", ")}</dd></div>
                </dl>
                </div>
              ) : null}
              <Status run={run} locale={locale} />
            </section>
            {run.phase === "error" && run.error && (
              <div className="rf-banner" data-tone="error" role="alert">
                {tr(locale, run.error)}
                <button type="button" className="rf-btn" data-kind="line" data-size="s" onClick={edit}>{tr(locale, "run_edit")}</button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.section layout="position" className="rf-howto" style={run ? { marginTop: 0 } : undefined} aria-labelledby="rf-how-h" transition={{ layout: { type: "spring", duration: 0.5, bounce: 0 } }}>
        <div className="rf-howto-head">
          <h2 className="rf-h2" id="rf-how-h">{run ? tr(locale, "run_lanes") : tr(locale, "mk_how")}</h2>
          <div className="rf-legend" aria-label={tr(locale, "actor_legend")}>
            <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "actor_rule")}</span>
            <span className="rf-who" data-actor="ai"><Mark actor="ai" />{tr(locale, "actor_ai")}</span>
            <span className="rf-who" data-actor="person"><Mark actor="person" />{tr(locale, "actor_person")}</span>
            {run && run.lanes.length > 1 && <span className="rf-muted" style={{ fontWeight: 500 }}>{tr(locale, "run_keys")}</span>}
          </div>
        </div>
        {!run && <p className="rf-note" style={{ margin: "-4px 0 12px" }}>{tr(locale, "mk_how_note")}</p>}
        <Matrix lanes={lanesView} locale={locale} ghost={!run} selected={sel} counts={counts} quiet={!!run?.restored}
          onSelect={run ? (m) => { follow.current = false; setSel(m); } : undefined} />
      </motion.section>

      {run?.rec && lane && (
        <motion.section key={lane.market} className="rf-detail-wrap" aria-labelledby={`rf-lane-h-${lane.market}`}
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}>
          <div className="rf-detail-head">
            <h2 id={`rf-lane-h-${lane.market}`}>{tr(locale, "dt_region", { market: marketName(locale, lane.market) })}</h2>
            <span className="rf-note">{tr(locale, `market_${lane.market}_lang`)}</span>
            {lane.pick && <Link className="rf-btn" data-kind="quiet" data-size="s" style={{ marginLeft: "auto" }} href={`/lab/r-flow/term/${encodeURIComponent(lane.pick.term_id)}?m=${lane.market}`} scroll={false}>{tr(locale, "dt_open_meme")}</Link>}
          </div>
          <LaneDetail lane={lane} rec={run.rec} locale={locale} signer={signer}
            onSwap={(id) => void redo(lane.market, id)} onRedo={() => void redo(lane.market)}
            onSign={() => sign(lane.market)} onUnsign={() => unsign(lane.market)} />
        </motion.section>
      )}

      {!run && saved.length > 0 && (
        <section className="rf-recent" aria-labelledby="rf-recent-h">
          <div className="rf-howto-head">
            <h2 className="rf-h2" id="rf-recent-h">{tr(locale, "recent_title")}</h2>
            <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={() => runs.write(null)}>{tr(locale, "recent_clear")}</button>
          </div>
          <p className="rf-note" style={{ margin: 0 }}>{tr(locale, "recent_note")}</p>
          <ul>
            {saved.map((r) => (
              <li key={r.id}>
                <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                  <b>{r.rec?.brief?.product ?? r.input.text}</b>
                  <span>{stamp(locale, r.at)}, {r.lanes.map((l) => marketName(locale, l.market)).join(", ")}{r.input.photo ? `, ${tr(locale, "recent_photo")}` : ""}, {tr(locale, "recent_approved", { a: r.lanes.filter((l) => l.sign).length, n: r.lanes.filter((l) => l.pick).length })}</span>
                </div>
                <button type="button" className="rf-btn" data-kind="line" data-size="s" onClick={() => restore(r)}>{tr(locale, "recent_open")}</button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {sample && <p className="rf-note" style={{ marginTop: 24 }}>{tr(locale, "run_brief_sample")}</p>}
    </LayoutGroup>
  );
}
