"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Who } from "@/components/who";
import { glossFor } from "@/lib/gloss";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L } from "@/lib/labels";
import { MAKE_MARKETS } from "@/lib/reader";
import type { CampaignTone, CopyCheck, ExcludedItem, FitCategory, GenerationResult, PosterResult, RecommendItem, RecommendResult, SocialCopy } from "@/lib/types";

/* 만들기 (Plan 20, 시안 n-redesign '누가 정했나' 원장). 제품·시장·분야·말투 → 시장마다 초안.
   순위는 백엔드 규칙(/recommend), 카피는 모델(/generate)이 쓰고 규칙 검사를 두 번 거친다(/generate 안에서, /copy-check 로 한 번 더).
   포스터는 구성안만 규칙이 만들고 그림 생성이 켜져 있을 때만 그림이 온다. 화면의 판단마다 누가 정했는지(규칙·모델·사람) 표지를 붙인다.
   백엔드는 모델 요청을 한 인스턴스에 둘까지만 받으므로 시장은 차례로 만든다. */

const MARKET_LANG: Record<string, "ko" | "ja" | "en"> = { KR: "ko", JP: "ja", GLOBAL: "en" };
const MAX_IMAGE = 5 * 1024 * 1024;
const TONES: CampaignTone[] = ["friendly", "witty", "premium"];
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);
const marketName = (locale: Locale, m: string) => t(locale, `mk_market_${m}` as StringKey);

type Status = "wait" | "writing" | "checking" | "poster" | "done" | "failed" | "none";
interface Column {
  market: string;
  status: Status;
  failedAt?: "copy" | "check";
  pick: RecommendItem | null;
  alts: RecommendItem[];
  gen: GenerationResult | null;
  check: CopyCheck | null;
  poster: PosterResult | null;
  sign: { by: string; at: string } | null;
}

async function post<T>(url: string, body: unknown, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

/** 문장 속 {word} 자리에 원문 낱말(굵게, lang)을 끼운다 */
function withWord(text: string, word: React.ReactNode) {
  const [a, b] = text.split("{word}");
  return <>{a}{word}{b}</>;
}

/** 카피 안의 밈을 밑줄로 — 무엇이 사전에서 왔는지 보이게 */
function Marked({ text, word }: { text: string; word?: string }) {
  if (!word || !text.includes(word)) return <>{text}</>;
  const at = text.indexOf(word);
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + word.length)}</mark>{text.slice(at + word.length)}</>;
}

function CopyRow({ c, n, lang, word, check, signed, locale, onCopy }: {
  c: SocialCopy; n: number; lang: string; word?: string; check: CopyCheck | null; signed: boolean; locale: Locale; onCopy: (text: string) => void;
}) {
  // 규칙 확인: 생성 단계의 규칙 검사(욕설·밈 들어감·글자 수·피할 표현)를 통과한 안만 여기 온다. 다시 검사(copy-check)는 첫 카피로 하고,
  // 같은 밈의 쓰임 판정(조심·식어 감·이 시장에서 안 쓰임)은 그 밈이 든 카피 모두에 붙인다
  const memes = check?.memes.filter((m) => c.text.includes(m.matched)) ?? [];
  const issues = memes.flatMap((m) => m.issues);
  const fit = n === 1 && c.platform === "instagram" ? check?.memes.find((m) => m.fit) : undefined;
  const flagged = issues.length > 0 || (fit?.fit && fit.fit !== "ok");
  const text = c.text + (c.hashtags?.length ? ` ${c.hashtags.map((h) => `#${h}`).join(" ")}` : "");
  return (
    <li className="n-copy" data-flag={!!flagged}>
      <div>
        <p className="n-copy-p">{c.platform === "x" ? "X" : "Instagram"} {n}</p>
        <p className="n-copy-t" lang={lang}><Marked text={c.text} word={word} /></p>
        {c.hashtags?.length ? <p className="n-tags" lang={lang}>{c.hashtags.map((h) => <span key={h}>#{h}</span>)}</p> : null}
        {signed && <button type="button" className="n-btn" data-kind="quiet" data-size="s" style={{ marginTop: 6, paddingInline: 0 }} onClick={() => onCopy(text)}>{t(locale, "dr_copy_this")}</button>}
      </div>
      <div className="n-check">
        <div>
          <Who kind="rule" locale={locale}>{t(locale, "dr_rule_check")}</Who>
          {issues.length === 0 ? <p className="n-ok">{t(locale, "dr_ok")}</p> : issues.map((i, k) => (
            <p key={`${i.code}-${k}`}><span className="n-flag" data-tone={i.code === "avoid" ? "avoid" : "caution"}>{fill(t(locale, `issue_${i.code}` as StringKey), { region: "" }).split(/[.。]/)[0]}</span></p>
          ))}
        </div>
        {fit?.fit && (
          <div>
            <Who kind="model" locale={locale}>{t(locale, "dr_model_opinion")}</Who>
            <p>{fit.fit === "ok" ? <span className="n-ok">{t(locale, "fit_ok")}</span> : <span className="n-flag" data-tone="caution">{t(locale, `fit_${fit.fit}` as StringKey)}</span>}{fit.fit_note ? `. ${fit.fit_note}` : ""}</p>
          </div>
        )}
      </div>
    </li>
  );
}

function MarketDraft({ col, rec, locale, onSign, onUnsign, onSwap, onRedo }: {
  col: Column; rec: RecommendResult; locale: Locale;
  onSign: () => void; onUnsign: () => void; onSwap: (id: string) => void; onRedo: () => void;
}) {
  const labels = L(locale);
  const [toast, setToast] = useState("");
  const m = col.market;
  const name = marketName(locale, m);
  const lang = col.gen?.language ?? MARKET_LANG[m];
  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setToast(t(locale, "dr_copied")); } catch { setToast(t(locale, "dr_copy_fail")); }
  };
  const busy = col.status === "wait" || col.status === "writing" || col.status === "checking" || col.status === "poster";
  const copies = col.gen?.copies ?? [];
  const flaggedOf = (c: SocialCopy) => (col.check?.memes.filter((x) => c.text.includes(x.matched)).some((x) => x.issues.length > 0) ?? false);
  const flagged = copies.filter(flaggedOf).length;
  const pool = rec.pool?.[m] ?? 0;
  const considered = rec.considered_by_region?.[m] ?? rec.items.filter((i) => i.write_regions.includes(m)).length;
  const excluded: ExcludedItem[] = (rec.excluded ?? []).filter((e) => e.regions.includes(m)).slice(0, 4);
  const word = col.pick?.canonical;
  const headline = col.gen?.thumbnail?.headline ?? copies[0]?.text.split(/[.!?。！？\n]/)[0] ?? "";
  let ig = 0, x = 0;

  return (
    <section className="n-market" id={`m-${m}`} aria-labelledby={`h-${m}`} aria-busy={busy}>
      <div className="n-market-head">
        <h2 className="n-h2" id={`h-${m}`}>{name}</h2>
        <span className="n-meta">{t(locale, `mk_market_${m}_en` as StringKey)}, {fill(t(locale, "dr_writes_in"), { lang: t(locale, `lang_${MARKET_LANG[m]}` as StringKey) })}</span>
      </div>

      <ol className="n-trail" aria-label={fill(t(locale, "dr_trail"), { market: name })}>
        <li>
          <span className="n-trail-top"><Who kind="rule" locale={locale} /></span>
          <span>{col.pick
            ? withWord(fill(t(locale, "dr_trail1"), { pool: pool.toLocaleString(), n: considered }), <strong lang={langTag(col.pick.lang)}>{col.pick.canonical}</strong>)
            : fill(t(locale, "dr_trail1_none"), { pool: pool.toLocaleString() })}</span>
        </li>
        <li>
          <span className="n-trail-top"><Who kind="model" locale={locale} /></span>
          <span>{col.status === "none" ? "–" : col.gen ? fill(t(locale, col.gen.script ? "dr_trail2_more" : "dr_trail2"), { n: copies.length })
            : col.failedAt === "copy" ? <span className="n-error">{t(locale, "dr_trail_failed")}</span> : <span className="n-busy">{t(locale, "dr_trail2_wait")}</span>}</span>
        </li>
        <li>
          <span className="n-trail-top"><Who kind="rule" locale={locale} /></span>
          <span>{col.status === "none" ? "–" : col.check || col.status === "poster" || col.status === "done"
            ? <>{flagged ? fill(t(locale, "dr_trail3_flag"), { p: copies.length - flagged, f: flagged }) : fill(t(locale, "dr_trail3_ok"), { n: copies.length })}
              {col.gen?.dropped.length ? <> {fill(t(locale, "dr_trail3_dropped"), { n: col.gen.dropped.length })}</> : null}</>
            : col.gen ? <span className="n-busy">{t(locale, "dr_trail3_wait")}</span> : "–"}</span>
        </li>
        <li>
          <span className="n-trail-top">{col.sign ? <Who kind="human" locale={locale}>{col.sign.by}</Who> : <Who kind="wait" locale={locale} />}</span>
          <span>{col.sign ? fill(t(locale, "dr_trail4_signed"), { at: col.sign.at }) : col.status === "none" ? "–" : t(locale, "dr_trail4_wait")}</span>
        </li>
      </ol>

      <div className="n-draft">
        <div>
          <span className="n-specimen-k">{t(locale, "dr_picked")}</span>
          {col.pick ? (
            <>
              <p className="n-specimen" lang={langTag(col.pick.lang)}>
                <Link href={`/dictionary/${encodeURIComponent(col.pick.term_id)}?regions=${m}&from=recommend`} target="_blank" rel="noopener">{col.pick.canonical}</Link>
              </p>
              <p className="n-gloss">{glossFor(col.pick, locale)}</p>
              <div className="n-sub">
                <h3>{t(locale, "dr_why")} <Who kind="rule" locale={locale} /></h3>
                <ul className="n-facts">
                  {(col.pick.matched_category || col.pick.any_category) && (
                    <li><span>{t(locale, "dr_why_category")}</span><span>{col.pick.matched_category && rec.brief ? labels.fitCategory[rec.brief.category] : t(locale, "dr_why_any")}</span></li>
                  )}
                  {col.pick.matched_feelings.length > 0 && <li><span>{t(locale, "dr_why_feeling")}</span><span>{col.pick.matched_feelings.map((f) => labels.feeling[f]).join(", ")}</span></li>}
                  {col.pick.diffusion && <li><span>{t(locale, "dr_why_spread")}</span><span>{t(locale, `diffusion_${col.pick.diffusion}` as StringKey)}</span></li>}
                  <li><span>{t(locale, "dr_why_stage")}</span><span>{labels.lifecycle[col.pick.lifecycle]}</span></li>
                  <li><span>{t(locale, "dr_why_risk")}</span><span>{col.pick.risk_level === "caution" ? t(locale, "risk_caution") : col.pick.risk_level === "none" ? t(locale, "dr_ok") : t(locale, "risk_unknown")}</span></li>
                  {col.pick.local_note && <li><span>{t(locale, "dr_why_local")}</span><span>{locale === "ko" ? col.pick.local_note.ko : col.pick.local_note.en}</span></li>}
                </ul>
              </div>
              {col.alts.length > 0 && (
                <div className="n-sub">
                  <h3>{t(locale, "dr_alt")}</h3>
                  <ul className="n-out">
                    {col.alts.map((a) => (
                      <li key={a.term_id}>
                        <span className="n-out-w"><span lang={langTag(a.lang)}>{a.canonical}</span>
                          <button type="button" className="n-btn" data-kind="quiet" data-size="s" disabled={busy} onClick={() => onSwap(a.term_id)}>{t(locale, "dr_use")}</button></span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <>
              <p className="n-specimen" data-none="true">{t(locale, "dr_none")}</p>
              <p className="n-thin">{t(locale, "dr_thin")}</p>
              <p><Link className="n-link" href={`/trends?regions=${m}`}>{fill(t(locale, "dr_browse"), { market: name })}</Link></p>
            </>
          )}
          <div className="n-sub">
            <h3>{t(locale, "dr_excluded")} <Who kind="rule" locale={locale} /></h3>
            {excluded.length ? (
              <ul className="n-out">
                {excluded.map((e) => (
                  <li key={e.term_id}>
                    <span className="n-out-w">
                      <Link className="n-link" href={`/dictionary/${encodeURIComponent(e.term_id)}?regions=${m}`} lang={langTag(e.lang)}>{e.canonical}</Link>
                      <span className={e.code === "avoid" || e.code === "crude" ? "n-flag" : "n-meta"} data-tone={e.code === "avoid" || e.code === "crude" ? "avoid" : undefined}>{t(locale, `ex_${e.code}` as StringKey)}</span>
                    </span>
                    <span className="n-why">{t(locale, `ex_${e.code}_why` as StringKey)}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="n-meta">{t(locale, "dr_excluded_none")}</p>}
          </div>
        </div>

        <div>
          {copies.length > 0 ? (
            <ul className="n-copies" aria-label={`${name} ${t(locale, "col_copy")}`}>
              {copies.map((c, i) => (
                <CopyRow key={i} c={c} n={c.platform === "x" ? ++x : ++ig} lang={langTag(lang) ?? lang} word={word} check={col.check}
                  signed={!!col.sign} locale={locale} onCopy={(text) => void copy(text)} />
              ))}
            </ul>
          ) : col.status !== "none" && (
            <p className={col.status === "failed" ? "n-error" : "n-busy"}>{col.status === "failed" ? t(locale, "col_failed") : t(locale, "dr_trail2_wait")}</p>
          )}
          {col.gen?.script && (
            <details className="n-more">
              <summary>{fill(t(locale, "dr_script"), { n: col.gen.script.duration_s })} <span className="n-meta">({fill(t(locale, "dr_scenes"), { n: col.gen.script.scenes.length })})</span></summary>
              <table className="n-scenes">
                <thead><tr><th scope="col">{t(locale, "dr_time")}</th><th scope="col">{t(locale, "dr_visual")}</th><th scope="col">{t(locale, "dr_caption")}</th></tr></thead>
                <tbody>
                  {col.gen.script.scenes.map((s) => <tr key={s.start_s}><td className="n-num">{s.start_s}–{s.end_s}s</td><td>{s.visual}</td><td lang={langTag(lang)}>{s.caption}</td></tr>)}
                </tbody>
              </table>
            </details>
          )}
          {col.gen?.thumbnail && (
            <details className="n-more">
              <summary>{t(locale, "dr_thumb")}</summary>
              <p style={{ margin: "0 0 14px", fontSize: 14 }}><span lang={langTag(lang)}><b>{col.gen.thumbnail.headline}</b></span>. {col.gen.thumbnail.layout}.</p>
            </details>
          )}
        </div>

        <div className="n-poster-col">
          {col.pick && (
            <figure style={{ margin: 0 }}>
              <div className="n-poster" role="img" aria-label={fill(t(locale, "dr_poster_alt"), { text: headline })}>
                {col.poster?.images[0]
                  // 생성 그림은 data URL 이라 next/image 최적화를 쓰지 않는다
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={col.poster.images[0]} alt="" className="n-poster-img" style={{ objectFit: "cover", padding: 0 }} />
                  : <div className="n-poster-img">{t(locale, "dr_poster_img")}</div>}
                <div className="n-poster-copy" lang={langTag(lang)}><b>{headline || "…"}</b><span>{rec.brief?.product}</span></div>
              </div>
              <figcaption className="n-poster-cap">{t(locale, "dr_poster_cap")}</figcaption>
            </figure>
          )}

          <div className="n-approve">
            {col.sign ? (
              <>
                <div className="n-signed" data-fresh="true"><Who kind="human" locale={locale}>{fill(t(locale, "dr_signed"), { who: col.sign.by })}</Who><span>{col.sign.at}</span></div>
                <div className="n-btns">
                  <button type="button" className="n-btn" data-size="s" onClick={() => void copy(copies.map((c) => `[${c.platform === "x" ? "X" : "Instagram"}] ${c.text}`).join("\n\n"))}>{t(locale, "dr_copy_all")}</button>
                  <button type="button" className="n-btn" data-kind="quiet" data-size="s" onClick={onUnsign}>{t(locale, "dr_unsign")}</button>
                </div>
              </>
            ) : col.status === "done" ? (
              <>
                <p>{flagged ? `${fill(t(locale, "dr_approve_flag"), { n: flagged })} ` : ""}{t(locale, "dr_approve_note")}</p>
                <div className="n-btns">
                  <button type="button" className="n-btn" onClick={onSign}>{fill(t(locale, "dr_approve"), { market: name })}</button>
                  <button type="button" className="n-btn" data-kind="line" onClick={onRedo}>{t(locale, "dr_redo")}</button>
                </div>
              </>
            ) : col.status === "failed" ? (
              <div className="n-btns"><button type="button" className="n-btn" data-kind="line" onClick={onRedo}>{t(locale, "col_retry")}</button></div>
            ) : null}
            <p className="n-toast" role="status">{toast}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function MakeFlow({ locale, counts, initialMarkets, reviewer, sample }: {
  locale: Locale; counts: Record<string, number>; initialMarkets: string[]; reviewer: string | null; sample: boolean;
}) {
  const labels = L(locale);
  const categories = Object.keys(labels.fitCategory) as FitCategory[];
  const [markets, setMarkets] = useState<string[]>(initialMarkets);
  const [category, setCategory] = useState<FitCategory | "">("");
  const [tone, setTone] = useState<CampaignTone>("friendly");
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [error, setError] = useState<StringKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState<RecommendResult | null>(null);
  const [cols, setCols] = useState<Column[]>([]);
  const [runAt, setRunAt] = useState("");
  const run = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const top = useRef<HTMLHeadingElement>(null);

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => () => abort.current?.abort(), []);

  const deepest = Math.max(1, ...MAKE_MARKETS.map((m) => counts[m] ?? 0));
  const ready = markets.length > 0 && (text.trim().length > 0 || !!photo);
  const toggle = (m: string) => { setError(null); setMarkets((cur) => (cur.includes(m) ? cur.filter((x) => x !== m) : MAKE_MARKETS.filter((x) => x === m || cur.includes(x)))); };
  const pickPhoto = (f: File | null) => {
    setError(null);
    if (f && (f.size > MAX_IMAGE || !["image/jpeg", "image/png", "image/webp"].includes(f.type))) {
      setError(f.size > MAX_IMAGE ? "rec_too_big" : "rec_bad_type");
      setInputKey((k) => k + 1);
      return;
    }
    if (!f) setInputKey((k) => k + 1);
    setPhoto(f ? { file: f, url: URL.createObjectURL(f) } : null);
  };
  const patch = (market: string, p: Partial<Column>) => setCols((cur) => cur.map((c) => (c.market === market ? { ...c, ...p } : c)));
  const stamp = () => new Date().toLocaleString(locale === "ko" ? "ko-KR" : "en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  /** 시장 하나의 초안: 카피 → 다시 검사 → 포스터. 앞 단계가 실패하면 그 시장만 실패로 둔다. */
  const draft = async (market: string, item: RecommendItem, r: RecommendResult, seq: number, signal: AbortSignal) => {
    const live = () => seq === run.current;
    patch(market, { status: "writing", failedAt: undefined, gen: null, check: null, poster: null, sign: null });
    let gen: GenerationResult;
    try {
      gen = await post<GenerationResult>("/api/generate", { term_ids: [item.term_id], brief: r.brief, region: market, tone: r.tone, lang: locale }, signal);
    } catch {
      if (live() && !signal.aborted) patch(market, { status: "failed", failedAt: "copy" });
      return;
    }
    if (!live()) return;
    patch(market, { gen, status: "checking" });
    const first = gen.copies.find((c) => c.platform === "instagram") ?? gen.copies[0];
    const check = first ? await post<CopyCheck>("/api/copy-check", { text: first.text, region: market, lang: locale }, signal).catch(() => null) : null;
    if (!live()) return;
    patch(market, { check, status: "poster" });
    const poster = await post<PosterResult>("/api/poster", { market, brief: r.brief, term_ids: [item.term_id] }, signal).catch(() => null);
    if (!live()) return;
    patch(market, { poster, status: "done" });
  };

  const submit = async () => {
    if (!markets.length) { setError("mk_need_market"); return; }
    if (!text.trim() && !photo) { setError("mk_need_input"); return; }
    const seq = ++run.current;
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.set("text", text.trim());
    body.set("tone", tone);
    body.set("lang", locale);
    body.set("regions", markets.join(","));
    if (category) body.set("category", category);
    if (photo) body.set("image", photo.file);
    let r: RecommendResult | null = null;
    try {
      const res = await fetch("/api/recommend", { method: "POST", body, signal: ctrl.signal });
      const json = (await res.json().catch(() => ({}))) as RecommendResult & { error?: string };
      if (res.ok) r = json;
      else setError(json.error === "busy" ? "make_busy" : json.error === "too_big" ? "rec_too_big" : json.error === "bad_type" ? "rec_bad_type" : "make_failed");
    } catch {
      if (!ctrl.signal.aborted) setError("make_failed");
    }
    setBusy(false);
    if (!r || seq !== run.current) return;
    // 시장마다 그 나라 말로 쓸 수 있는 밈만(백엔드 generate 의 write_regions) — 규칙 순위 그대로, 첫째가 초안, 다음 둘이 다른 후보
    const next: Column[] = markets.map((m) => {
      const fit = r!.items.filter((i) => i.write_regions.includes(m));
      return { market: m, status: fit.length ? "wait" : "none", pick: fit[0] ?? null, alts: fit.slice(1, 3), gen: null, check: null, poster: null, sign: null };
    });
    setRec(r);
    setCols(next);
    setRunAt(stamp());
    setTimeout(() => { top.current?.focus(); window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }, 0);
    for (const c of next) {
      if (seq !== run.current) return;
      if (c.pick) await draft(c.market, c.pick, r, seq, ctrl.signal);
    }
  };

  const redo = async (market: string, termId?: string) => {
    if (!rec) return;
    const col = cols.find((c) => c.market === market);
    const pool = rec.items.filter((i) => i.write_regions.includes(market));
    const item = termId ? pool.find((i) => i.term_id === termId) : col?.pick;
    if (!item) return;
    patch(market, { pick: item, alts: pool.filter((i) => i.term_id !== item.term_id).slice(0, 2) });
    await draft(market, item, rec, run.current, (abort.current ?? new AbortController()).signal);
  };

  // ---------- 결과: 초안 ----------
  if (rec) {
    const signed = cols.filter((c) => c.sign).length;
    const stateOf = (c: Column): StringKey => c.sign ? "dr_state_approved" : c.status === "none" ? "dr_state_none" : c.status === "failed" ? "dr_state_failed" : c.status === "done" ? "dr_state_wait" : "dr_state_busy";
    return (
      <div className="n-wrap">
        <div className="n-head" style={{ paddingBottom: 24 }}>
          <p className="n-crumb">
            <button type="button" className="n-link" style={{ background: "none", border: 0, padding: 0, font: "inherit", color: "inherit", cursor: "pointer" }}
              onClick={() => { abort.current?.abort(); run.current++; setRec(null); }}>{t(locale, "dr_edit")}</button>
            <span aria-hidden="true">/</span><span>{t(locale, "dr_crumb")}</span>
          </p>
          <h1 className="n-h1" ref={top} tabIndex={-1}>{rec.brief?.product ?? text}</h1>
          {text.trim() && text.trim() !== rec.brief?.product && <p className="n-lead">{text.trim()}</p>}
          <dl className="n-brief">
            <div><dt>{t(locale, "dr_markets")}</dt><dd>{cols.map((c) => marketName(locale, c.market)).join(", ")}</dd></div>
            {rec.brief && <div><dt>{t(locale, "dr_category")}</dt><dd>{labels.fitCategory[rec.brief.category]} {!category && <span className="n-meta">{t(locale, "dr_category_auto")}</span>}</dd></div>}
            <div><dt>{t(locale, "dr_tone")}</dt><dd>{labels.campaignTone[rec.tone]}</dd></div>
            <div><dt>{t(locale, "dr_at")}</dt><dd className="n-num">{runAt}</dd></div>
          </dl>
        </div>
        <div className="n-tally">
          <nav aria-label={t(locale, "dr_go")}>
            {cols.map((c) => (
              <a key={c.market} href={`#m-${c.market}`}>
                <b>{marketName(locale, c.market)}</b>
                <span className="n-state" data-on={!!c.sign}>{t(locale, stateOf(c))}</span>
              </a>
            ))}
          </nav>
          <span className="n-meta n-num" aria-live="polite">{fill(t(locale, "dr_tally"), { m: cols.filter((c) => c.status !== "none").length, n: signed })}</span>
        </div>
        {cols.map((c) => (
          <MarketDraft key={c.market} col={c} rec={rec} locale={locale}
            onSign={() => patch(c.market, { sign: { by: reviewer ?? t(locale, "dr_reviewer"), at: stamp() } })}
            onUnsign={() => patch(c.market, { sign: null })}
            onSwap={(id) => void redo(c.market, id)} onRedo={() => void redo(c.market)} />
        ))}
      </div>
    );
  }

  // ---------- 입력: 만들기 ----------
  return (
    <div className="n-wrap">
      <div className="n-head">
        <h1 className="n-h1">{t(locale, "mk_title")}</h1>
        <p className="n-lead" id="mk-lead">{t(locale, "mk_lead")}</p>
      </div>
      <div className="n-ledger">
        <form aria-describedby="mk-lead" aria-busy={busy} onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <div className="n-row">
            <div className="n-row-label">{t(locale, "mk_product")}<small>{t(locale, "mk_product_hint")}</small></div>
            <div className="n-product">
              <label className="n-drop">
                <input key={inputKey} type="file" accept="image/jpeg,image/png,image/webp" aria-label={t(locale, "mk_photo")} onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
                {photo
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <span><img src={photo.url} alt={t(locale, "rec_photo_alt")} style={{ width: 72, height: 72, objectFit: "cover", margin: "0 auto 8px", display: "block" }} /><strong>{t(locale, "mk_photo_done")}</strong>{photo.file.name}</span>
                  : <span><strong>{t(locale, "mk_photo")}</strong>{t(locale, "mk_photo_hint")}</span>}
              </label>
              <div className="n-field">
                <label htmlFor="make-pitch">{t(locale, "mk_pitch")}</label>
                <textarea id="make-pitch" className="n-input" rows={4} maxLength={500} value={text} placeholder={t(locale, "rec_copy_ph")}
                  onChange={(e) => { setText(e.target.value); if (error === "mk_need_input") setError(null); }} />
                <p className="n-hint">{t(locale, "mk_pitch_hint")}</p>
                {photo && <p className="n-hint"><button type="button" className="n-link" style={{ background: "none", border: 0, padding: 0, font: "inherit", cursor: "pointer" }} onClick={() => pickPhoto(null)}>{t(locale, "mk_photo_remove")}</button></p>}
              </div>
            </div>
          </div>

          <div className="n-row">
            <div className="n-row-label" id="mk-markets">{t(locale, "mk_markets")}<small>{t(locale, "mk_markets_hint")}</small></div>
            <div>
              <div className="n-markets" data-n="3" role="group" aria-labelledby="mk-markets">
                {MAKE_MARKETS.map((m) => {
                  const on = markets.includes(m);
                  const n = counts[m] ?? 0;
                  return (
                    <button key={m} type="button" className="n-mkt" aria-pressed={on} onClick={() => toggle(m)}>
                      <b>{marketName(locale, m)}</b>
                      <span className="n-meta">{t(locale, `mk_market_${m}_en` as StringKey)}</span>
                      <span className="n-wc">{fill(t(locale, "mk_words"), { n: n.toLocaleString() })}</span>
                      <span className="n-depth" aria-hidden="true"><i style={{ width: `${(n / deepest) * 100}%` }} /></span>
                    </button>
                  );
                })}
              </div>
              <p className="n-hint" style={{ marginTop: 12 }} aria-live="polite">{fill(t(locale, "mk_picked"), { n: markets.length })}</p>
              {error === "mk_need_market" && <p role="alert" className="n-error" style={{ marginTop: 6 }}>{t(locale, error)}</p>}
            </div>
          </div>

          <div className="n-row">
            <div className="n-row-label" id="mk-cat">{t(locale, "mk_category")}<small>{t(locale, "mk_category_hint")}</small></div>
            <div className="n-choices" role="radiogroup" aria-labelledby="mk-cat">
              {(["", ...categories] as (FitCategory | "")[]).map((c) => (
                <button key={c || "auto"} type="button" role="radio" aria-checked={category === c} className="n-choice" onClick={() => setCategory(c)}>
                  {c ? labels.fitCategory[c] : t(locale, "mk_auto")}
                </button>
              ))}
            </div>
          </div>

          <div className="n-row">
            <div className="n-row-label" id="mk-tone">{t(locale, "mk_tone")}</div>
            <div className="n-tones" role="radiogroup" aria-labelledby="mk-tone">
              {TONES.map((tn) => (
                <button key={tn} type="button" role="radio" aria-checked={tone === tn} className="n-tone" onClick={() => setTone(tn)}>
                  <b>{labels.campaignTone[tn]}</b><span>{t(locale, `mk_tone_${tn}_hint` as StringKey)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="n-submit">
            <button type="submit" className="n-btn" disabled={busy}>{busy ? t(locale, "mk_reading") : t(locale, "mk_submit")}</button>
            <span className="n-hint">
              {error && error !== "mk_need_market" ? <span role="alert" className="n-error">{t(locale, error)}</span>
                : ready ? fill(t(locale, "mk_ready"), { n: markets.length }) : markets.length ? t(locale, "mk_need_input") : t(locale, "mk_need_market")}
            </span>
          </div>
          {sample && <p className="n-hint" style={{ marginTop: 12 }}>{t(locale, "rec_brief_sample")}</p>}
        </form>
        <aside className="n-rail" aria-labelledby="mk-how">
          <h2 id="mk-how">{t(locale, "mk_how")}</h2>
          <ol className="n-steps">
            <li><div><Who kind="rule" locale={locale} /><span>{t(locale, "mk_how1")}</span></div></li>
            <li><div><Who kind="model" locale={locale} /><span>{t(locale, "mk_how2")}</span></div></li>
            <li><div><Who kind="rule" locale={locale} /><span>{t(locale, "mk_how3")}</span></div></li>
            <li><div><Who kind="human" locale={locale} /><span>{t(locale, "mk_how4")}</span></div></li>
          </ol>
        </aside>
      </div>
    </div>
  );
}
