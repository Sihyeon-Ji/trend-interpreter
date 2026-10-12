"use client";

/* 시장 하나의 초안 — 왼쪽: 고른 밈과 고른 이유(규칙)·다른 후보·뺀 말, 가운데: AI 가 쓴 문구와 규칙의 재검사·AI 의견,
   오른쪽: 사람이 정하는 칸(승인 전에 볼 것 → 승인)과 포스터 자리. 내용은 요청이 끝나는 대로 차례로 들어온다. */
import Link from "next/link";
import { useState } from "react";
import { ChevronRight, Copy } from "lucide-react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { glossFor } from "@/lib/gloss";
import { langTag } from "@/lib/lang";
import { L } from "@/lib/labels";
import type { CopyCheck, CopyMeme, ExcludedItem, GenerationResult, PosterResult, RecommendItem, RecommendResult, SocialCopy } from "@/lib/types";
import { MARKET_LANG, marketName, num, tr, type CopyKey, type Market } from "./copy";
import { Mark } from "./glyph";
import type { Step, StepKey } from "./matrix";

const BASE = "/lab/r-flow";

export interface LaneState {
  market: Market;
  steps: Record<StepKey, Step>;
  pick: RecommendItem | null;
  alts: RecommendItem[];
  by: "rule" | "swap" | "pin";
  gen: GenerationResult | null;
  check: CopyCheck | null;
  poster: PosterResult | null;
  sign: { by: string; at: string } | null;
  fresh?: { copies?: number; sign?: number };
}

const ISSUE: Record<string, CopyKey> = { avoid: "issue_avoid", caution: "issue_caution", undecided: "issue_undecided", fading: "issue_fading", not_in_region: "issue_not_in_region", no_script: "issue_no_script" };
const DROP: Record<string, CopyKey> = { unsafe: "drop_unsafe", no_meme: "drop_no_meme", x_too_long: "drop_x_too_long", avoid_word: "drop_avoid_word" };
const EX: Record<string, CopyKey> = { avoid: "ex_avoid", crude: "ex_crude", tone: "ex_tone", fading: "ex_fading", sensitive: "ex_sensitive" };
const DIF: Record<string, CopyKey> = { underground: "dif_underground", spreading: "dif_spreading", mainstream: "dif_mainstream", fading: "dif_fading" };

/** 문구 속 낱말 찾기 — 라틴 글자는 대소문자를 가리지 않는다('E-girl' 과 'e-girl' 은 같은 밈) */
const find = (text: string, word: string) => text.toLowerCase().indexOf(word.toLowerCase());

/** 고른 밈과 문구에서 함께 찾은 낱말 — 고른 밈은 굵은 밑줄, 다른 사전 낱말은 점선 */
function Marked({ text, pick, others }: { text: string; pick?: string; others: string[] }) {
  const words = [...(pick ? [{ w: pick, k: "pick" as const }] : []), ...others.filter((o) => o && o !== pick).map((w) => ({ w, k: "other" as const }))];
  if (!words.length) return <>{text}</>;
  const out: React.ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest) {
    let best: { at: number; w: string; k: "pick" | "other" } | null = null;
    for (const x of words) {
      const at = find(rest, x.w);
      if (at >= 0 && (!best || at < best.at || (at === best.at && x.w.length > best.w.length))) best = { at, ...x };
    }
    if (!best) { out.push(rest); break; }
    if (best.at > 0) out.push(rest.slice(0, best.at));
    out.push(<mark key={key++} data-kind={best.k}>{rest.slice(best.at, best.at + best.w.length)}</mark>);
    rest = rest.slice(best.at + best.w.length);
  }
  return <>{out}</>;
}

/** 이 문구에 든 사전 밈들(규칙이 찾은 것) */
const memesIn = (c: SocialCopy, check: CopyCheck | null) => (check?.memes ?? []).filter((m) => find(c.text, m.matched) >= 0);
/** 문구가 걸렸나 — 든 밈에 규칙 문제가 있으면(같은 밈이 든 문구 모두에 붙인다) */
export const flaggedCopy = (c: SocialCopy, check: CopyCheck | null, pickId?: string) =>
  memesIn(c, check).some((m) => m.issues.length > 0 && (m.term_id === pickId || m.fit !== "off"));

/** 포스터 구성안의 색 낱말 → 견본 색(못 알아들으면 회색) */
const SWATCH: [RegExp, string][] = [
  [/핑크|분홍|pink/i, "#f4bccb"], [/피치|복숭아|살구|peach|apricot/i, "#f7c8a9"], [/노랑|노란|레몬|yellow|lemon/i, "#f5dd7d"],
  [/주황|오렌지|orange/i, "#f3a75d"], [/빨강|빨간|레드|red/i, "#e3735f"], [/민트|mint/i, "#a8e2cf"], [/초록|녹색|그린|green/i, "#97cda3"],
  [/하늘|스카이|sky|light blue|파스텔 블루/i, "#acd2f2"], [/파랑|파란|블루|blue|navy|네이비/i, "#7299df"], [/보라|라벤더|purple|lavender|violet/i, "#c5b6e8"],
  [/베이지|크림|beige|cream|ivory|아이보리/i, "#ece0c8"], [/갈색|브라운|커피|brown|coffee/i, "#b98b65"], [/흰|화이트|white/i, "#ffffff"],
  [/검정|검은|블랙|black/i, "#27292d"], [/회색|그레이|실버|gray|grey|silver/i, "#c4c8ce"], [/금색|골드|gold/i, "#dab95f"],
];
const swatch = (name: string) => SWATCH.find(([re]) => re.test(name))?.[1] ?? null;
function dark(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 140;
}

function Poster({ poster, headline, product, lang, locale }: { poster: PosterResult | null; headline: string; product?: string; lang: string; locale: Locale }) {
  const colors = (poster?.plan.colors ?? []).map((c) => ({ c, hex: swatch(c) }));
  const known = colors.filter((x) => x.hex).map((x) => x.hex as string);
  const bg = known[0] ?? "#eef0f2";
  const orb = known[1] ?? (bg === "#ffffff" ? "#eef0f2" : "#ffffff");
  const ink = dark(bg) ? "#ffffff" : "#17191e";
  const img = poster?.images?.[0];
  return (
    <figure style={{ margin: 0 }}>
      <div className="rf-poster" role="img" aria-label={`${tr(locale, "dt_poster")}: ${headline}`} style={{ background: bg, color: ink }}>
        {img
          // 생성 그림은 data URL 이라 next/image 를 쓰지 않는다
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={img} alt="" />
          : <span className="rf-poster-orb" style={{ background: orb, opacity: 0.9 }} />}
        <div className="rf-poster-copy" lang={langTag(lang)}>
          <b>{headline || "…"}</b>
          {product && <span lang={undefined}>{product}</span>}
        </div>
      </div>
      <figcaption className="rf-poster-cap">
        {!img && tr(locale, "dt_poster_off")}
        {poster && (
          <span className="rf-swatches" aria-label={tr(locale, "dt_poster_colors")}>
            {colors.map((x) => <span key={x.c} className="rf-swatch"><i style={{ background: x.hex ?? "#eef0f2" }} />{x.c}</span>)}
          </span>
        )}
        {!!poster?.plan.mood.length && <span style={{ display: "block", marginTop: 6 }}>{tr(locale, "dt_poster_mood")}: <span lang="en">{poster.plan.mood.join(", ")}</span></span>}
      </figcaption>
    </figure>
  );
}

function issueText(locale: Locale, code: string) {
  return ISSUE[code] ? tr(locale, ISSUE[code]) : code;
}
function fitText(locale: Locale, fit: CopyMeme["fit"], incidental: boolean) {
  if (incidental && fit === "off") return tr(locale, "fit_incidental");
  return fit === "ok" ? tr(locale, "fit_ok") : fit === "off" ? tr(locale, "fit_off") : tr(locale, "fit_unsure");
}

export function LaneDetail({ lane, rec, locale, signer, onSwap, onRedo, onSign, onUnsign }: {
  lane: LaneState; rec: RecommendResult; locale: Locale; signer: string | null;
  onSwap: (termId: string) => void; onRedo: () => void; onSign: () => void; onUnsign: () => void;
}) {
  const labels = L(locale);
  const [toast, setToast] = useState("");
  const m = lane.market;
  const name = marketName(locale, m);
  const lang = lane.gen?.language ?? MARKET_LANG[m];
  const pick = lane.pick;
  const st = lane.steps;
  const busy = (["write", "check", "poster"] as StepKey[]).some((k) => st[k].s === "run");
  const copies = lane.gen?.copies ?? [];
  const check = lane.check;
  const pickMeme = check?.memes.find((x) => x.term_id === pick?.term_id) ?? null;
  const others = (check?.memes ?? []).filter((x) => x.term_id !== pick?.term_id);
  const pickWord = pickMeme?.matched ?? pick?.canonical;
  const pool = rec.pool?.[m] ?? 0;
  const considered = rec.considered_by_region?.[m] ?? 0;
  const excluded: ExcludedItem[] = (rec.excluded ?? []).filter((e) => e.regions.includes(m)).slice(0, 4);
  const headline = lane.gen?.thumbnail?.headline ?? copies[0]?.text.split(/[.!?。！？\n]/)[0] ?? "";
  const checked = st.check.s === "done" || st.check.s === "warn" || st.check.s === "fail";
  const ready = !busy && st.write.s === "done" && checked && (st.poster.s === "done" || st.poster.s === "fail");

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setToast(tr(locale, "dt_copied")); } catch { setToast(tr(locale, "dt_copy_fail")); }
  };

  // 승인 전에 볼 것 — 규칙이 건 것과 AI 의견. 판정을 새로 하지 않고 받은 결과를 모은다
  const before: { actor: "rule" | "ai"; text: string; note?: string; tone: "caution" | "avoid" }[] = [];
  if (st.check.s === "fail") before.push({ actor: "rule", text: tr(locale, "cell_check_fail"), tone: "caution" });
  if (pickMeme) {
    for (const i of pickMeme.issues) before.push({ actor: "rule", text: tr(locale, "dt_before_rule", { word: pickMeme.matched, issue: issueText(locale, i.code) }), note: i.note || undefined, tone: i.code === "avoid" ? "avoid" : "caution" });
    if (pickMeme.fit && pickMeme.fit !== "ok") before.push({ actor: "ai", text: tr(locale, "dt_before_ai", { word: pickMeme.matched, fit: fitText(locale, pickMeme.fit, false) }), note: pickMeme.fit_note ?? undefined, tone: "caution" });
  }
  for (const o of others) {
    if (o.fit === "off") continue;   // 밈이 아니라 보통 낱말로 쓰였다(AI 의견) — 승인 목록에는 올리지 않고 위 검사 칸에만 적는다
    for (const i of o.issues) before.push({ actor: "rule", text: tr(locale, "dt_before_rule", { word: o.matched, issue: issueText(locale, i.code) }), tone: i.code === "avoid" ? "avoid" : "caution" });
  }

  let ig = 0, x = 0;

  if (!pick && st.pick.s === "none") {
    return (
      <div className="rf-detail" data-none="true" id={`rf-lane-${m}`}>
        <section>
          <div className="rf-empty" style={{ paddingTop: 0 }}>
            <h3>{tr(locale, "dt_none_title")}</h3>
            <p style={{ margin: 0 }}>{tr(locale, "dt_none_body", { pool: num(pool) })}</p>
            <p style={{ marginTop: 10 }}><Link className="rf-link" href={`${BASE}/explore?m=${m}`}>{tr(locale, "dt_none_link", { market: name })}</Link></p>
          </div>
        </section>
        <section>
          <h4 className="rf-sub-h">{tr(locale, "dt_excluded")} <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "actor_rule")}</span></h4>
          {excluded.length ? (
            <ul className="rf-outs">
              {excluded.map((e) => (
                <li key={e.term_id}>
                  <Link className="rf-link" href={`${BASE}/term/${encodeURIComponent(e.term_id)}?m=${m}`} lang={langTag(e.lang)} scroll={false}>{e.canonical}</Link>
                  <span className="rf-ex-code" data-tone={e.code === "avoid" || e.code === "crude" ? "avoid" : undefined}>{tr(locale, EX[e.code] ?? "ex_tone")}</span>
                </li>
              ))}
            </ul>
          ) : <p className="rf-note">{tr(locale, "dt_excluded_none")}</p>}
        </section>
      </div>
    );
  }

  return (
    <div className="rf-detail" id={`rf-lane-${m}`} aria-labelledby={`rf-lane-h-${m}`}>
      {/* 고른 밈 */}
      <section aria-labelledby={`rf-pick-${m}`}>
        <h3 className="rf-sub-h" id={`rf-pick-${m}`} style={{ margin: 0 }}>
          <span>{tr(locale, "dt_picked")}</span>
          <span className="rf-who" data-actor={lane.by === "rule" ? "rule" : "person"}><Mark actor={lane.by === "rule" ? "rule" : "person"} />{lane.by === "rule" ? tr(locale, "actor_rule") : tr(locale, lane.by === "swap" ? "cell_pick_swapped" : "cell_pick_pinned")}</span>
        </h3>
        {pick ? (
          <>
            <p className="rf-specimen" lang={langTag(pick.lang)}>
              <Link href={`${BASE}/term/${encodeURIComponent(pick.term_id)}?m=${m}`} scroll={false}>{pick.canonical}</Link>
            </p>
            <p className="rf-gloss">{glossFor(pick, locale)}</p>
            <div className="rf-sub">
              <h4 className="rf-sub-h">{tr(locale, "dt_why")} <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "actor_rule")}</span></h4>
              <dl className="rf-dl">
                <dt>{tr(locale, "dt_why_category")}</dt>
                <dd>{pick.matched_category && rec.brief ? tr(locale, "dt_why_category_match", { cat: labels.fitCategory[rec.brief.category] }) : pick.any_category ? tr(locale, "dt_why_any") : "–"}</dd>
                {pick.matched_feelings.length > 0 && <><dt>{tr(locale, "dt_why_feel")}</dt><dd>{pick.matched_feelings.map((f) => labels.feeling[f]).join(", ")}</dd></>}
                <dt>{tr(locale, "dt_why_spread")}</dt><dd>{pick.diffusion ? tr(locale, DIF[pick.diffusion]) : "–"}</dd>
                <dt>{tr(locale, "dt_why_stage")}</dt><dd>{labels.lifecycle[pick.lifecycle]}</dd>
                <dt>{tr(locale, "dt_why_risk")}</dt>
                <dd>{pick.risk_level === "caution" ? <span className="rf-flag">{tr(locale, "risk_caution")}</span> : pick.risk_level === "none" ? tr(locale, "risk_none") : pick.risk_checked_at ? <span className="rf-flag">{tr(locale, "risk_unknown")}</span> : tr(locale, "risk_unchecked")}</dd>
                {pick.local_note && <><dt>{tr(locale, "dt_why_local")}</dt><dd>{locale === "ko" ? pick.local_note.ko : pick.local_note.en}</dd></>}
              </dl>
              <p className="rf-note" style={{ marginTop: 8 }}>{tr(locale, "cell_pick_meta", { pool: num(pool), n: num(considered) })}</p>
            </div>
            {lane.alts.length > 0 && (
              <div className="rf-sub">
                <h4 className="rf-sub-h">{tr(locale, "dt_alts")}</h4>
                <ul className="rf-alts">
                  {lane.alts.map((a) => (
                    <li key={a.term_id}>
                      <span className="rf-alt-w" lang={langTag(a.lang)}>{a.canonical}</span>
                      <button type="button" className="rf-btn" data-kind="line" data-size="s" disabled={busy} onClick={() => onSwap(a.term_id)}>{tr(locale, "dt_use")}</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <div className="rf-empty">
            <h3>{tr(locale, "dt_none_title")}</h3>
            <p style={{ margin: 0 }}>{tr(locale, "dt_none_body", { pool: num(pool) })}</p>
            <p style={{ marginTop: 10 }}><Link className="rf-link" href={`${BASE}/explore?m=${m}`}>{tr(locale, "dt_none_link", { market: name })}</Link></p>
          </div>
        )}
        <div className="rf-sub">
          <h4 className="rf-sub-h">{tr(locale, "dt_excluded")} <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "actor_rule")}</span></h4>
          {excluded.length ? (
            <ul className="rf-outs">
              {excluded.map((e) => (
                <li key={e.term_id}>
                  <Link className="rf-link" href={`${BASE}/term/${encodeURIComponent(e.term_id)}?m=${m}`} lang={langTag(e.lang)} scroll={false}>{e.canonical}</Link>
                  <span className="rf-ex-code" data-tone={e.code === "avoid" || e.code === "crude" ? "avoid" : undefined}>{tr(locale, EX[e.code] ?? "ex_tone")}</span>
                </li>
              ))}
            </ul>
          ) : <p className="rf-note">{tr(locale, "dt_excluded_none")}</p>}
        </div>
      </section>

      {/* 문구 */}
      <section aria-labelledby={`rf-copies-${m}`}>
        <h3 className="rf-sub-h" id={`rf-copies-${m}`} style={{ marginTop: 0 }}>
          <span>{tr(locale, "dt_copies")}</span>
          <span className="rf-who" data-actor="ai"><Mark actor="ai" />{tr(locale, "actor_ai")}</span>
        </h3>
        {pick && (
          <div className="rf-checkbox" data-state={checked ? "done" : "wait"} aria-live="polite">
            {st.write.s === "stop" || st.check.s === "stop" ? (
              <div className="rf-check-row"><Mark actor="rule" filled={false} /><p className="rf-muted">{tr(locale, "cell_stop")}</p></div>
            ) : st.write.s === "fail" ? (
              <div className="rf-check-row"><Mark actor="rule" filled={false} /><p className="rf-muted">–</p></div>
            ) : !checked ? (
              <div className="rf-check-row"><Mark actor="rule" filled={false} /><p className="rf-muted">{st.write.s === "done" ? tr(locale, "dt_check_wait") : tr(locale, "dt_copies_wait")}</p></div>
            ) : st.check.s === "fail" || !check ? (
              <div className="rf-check-row"><Mark actor="rule" /><p className="rf-flag">{tr(locale, "dt_check_none")}</p></div>
            ) : (
              <>
                <div className="rf-check-row">
                  <Mark actor="rule" />
                  <p>
                    <b>{tr(locale, "dt_check_pick")}</b>{" "}
                    {pickMeme && pickMeme.issues.length
                      ? pickMeme.issues.map((i, k) => <span key={i.code} className="rf-flag" data-tone={i.code === "avoid" ? "avoid" : undefined}>{k ? ", " : ""}{issueText(locale, i.code)}</span>)
                      : pickMeme ? <span className="rf-ok">{tr(locale, "check_pass")}</span> : <span className="rf-muted">–</span>}
                  </p>
                </div>
                {pickMeme?.fit && (
                  <div className="rf-check-row">
                    <Mark actor="ai" />
                    <p><b className="rf-ai-note">{tr(locale, "dt_ai_opinion")}</b> <span className={pickMeme.fit === "ok" ? "rf-ok" : "rf-flag"}>{fitText(locale, pickMeme.fit, false)}</span></p>
                    {pickMeme.fit_note && <p className="rf-note" lang="ko">{pickMeme.fit_note}</p>}
                  </div>
                )}
                {others.length > 0 && (
                  <div className="rf-check-row">
                    <Mark actor="rule" />
                    <div>
                      <p><b>{tr(locale, "dt_check_other")}</b></p>
                      <ul className="rf-others" style={{ marginTop: 4 }}>
                        {others.map((o) => (
                          <li key={o.term_id}>
                            <span lang={langTag(o.lang)} style={{ color: "var(--rf-ink)", fontWeight: 600 }}>{o.matched}</span>{" "}
                            {o.fit === "off" ? fitText(locale, "off", true) : o.issues.length ? o.issues.map((i) => issueText(locale, i.code)).join(", ") : tr(locale, "check_pass")}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                <p className="rf-note" style={{ margin: "6px 0 0" }}>{tr(locale, "dt_check_scope")}</p>
              </>
            )}
          </div>
        )}

        {copies.length > 0 ? (
          <ul className="rf-copies" data-fresh={lane.fresh?.copies ? "true" : undefined} aria-label={`${name} ${tr(locale, "dt_copies")}`}>
            {copies.map((c, k) => {
              const n = c.platform === "x" ? ++x : ++ig;
              const flagged = checked && check ? flaggedCopy(c, check, pick?.term_id) : false;
              const text = c.text + (c.hashtags?.length ? `\n${c.hashtags.map((h) => `#${h}`).join(" ")}` : "");
              return (
                <li key={`${lane.fresh?.copies ?? 0}-${k}`} className="rf-copy" data-enter={lane.fresh?.copies ? "true" : undefined} style={{ "--k": k } as React.CSSProperties}>
                  <header>
                    <span>{c.platform === "x" ? "X" : "Instagram"} {n}</span>
                    {checked && check && (flagged
                      ? <span className="rf-chip" data-tone="caution">{tr(locale, "check_look")}</span>
                      : <span className="rf-chip" data-tone="ok">{tr(locale, "check_pass")}</span>)}
                  </header>
                  <p className="rf-copy-text" lang={langTag(lang) ?? lang}><Marked text={c.text} pick={pickWord} others={others.map((o) => o.matched)} /></p>
                  {/* 글 안에 이미 든 해시태그는 다시 적지 않는다(X 문구는 본문에 넣어 쓴다) */}
                  {!!c.hashtags?.filter((h) => !c.text.includes(`#${h}`)).length && <p className="rf-tags" lang={langTag(lang) ?? lang}>{c.hashtags.filter((h) => !c.text.includes(`#${h}`)).map((h) => <span key={h}>#{h}</span>)}</p>}
                  {lane.sign && (
                    <footer>
                      <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={() => void copy(text)}><Copy size={13} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "dt_copy")}</button>
                    </footer>
                  )}
                </li>
              );
            })}
          </ul>
        ) : pick && (
          st.write.s === "fail"
            ? <div className="rf-banner" data-tone="error">{tr(locale, "dt_copies_fail")} <button type="button" className="rf-btn" data-kind="line" data-size="s" onClick={onRedo}>{tr(locale, "dt_retry")}</button></div>
            : st.write.s === "stop" ? <p className="rf-note">{tr(locale, "cell_stop")}</p>
              : (
                <div aria-hidden="true">
                  {[0, 1, 2].map((k) => (
                    <div key={k} style={{ padding: "14px 0", borderTop: k ? "1px solid var(--rf-line)" : 0 }}>
                      <span className="rf-skel" style={{ width: 90, height: 10 }} />
                      <span className="rf-skel" style={{ width: "92%", marginTop: 10 }} />
                      <span className="rf-skel" style={{ width: "70%", marginTop: 8 }} />
                    </div>
                  ))}
                </div>
              )
        )}

        {!!lane.gen?.dropped.length && (
          <details className="rf-more">
            <summary><ChevronRight size={14} strokeWidth={2} aria-hidden="true" />{tr(locale, "dt_dropped", { n: lane.gen.dropped.length })} <span className="rf-who" data-actor="rule"><Mark actor="rule" />{tr(locale, "actor_rule")}</span></summary>
            <ul className="rf-others" style={{ paddingBottom: 12 }}>
              {lane.gen.dropped.map((d) => <li key={d.id}>{DROP[d.code] ? tr(locale, DROP[d.code]) : d.code}</li>)}
            </ul>
          </details>
        )}
        {lane.gen?.script && (
          <details className="rf-more">
            <summary><ChevronRight size={14} strokeWidth={2} aria-hidden="true" />{tr(locale, "dt_script", { n: lane.gen.script.duration_s })} <span className="rf-muted" style={{ fontWeight: 500 }}>{tr(locale, "dt_scenes", { n: lane.gen.script.scenes.length })}</span></summary>
            <table className="rf-scenes">
              <tbody>
                {lane.gen.script.scenes.map((s) => (
                  <tr key={s.start_s}>
                    <td className="rf-num" style={{ whiteSpace: "nowrap", color: "var(--rf-ink-3)" }}>{s.start_s}–{s.end_s}s</td>
                    <td lang={/[가-힣]/.test(s.visual) ? "ko" : langTag(lang)}>{s.visual}</td>
                    <td lang={langTag(lang)}>{s.caption ?? s.line ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
        {lane.gen?.thumbnail && (
          <details className="rf-more">
            <summary><ChevronRight size={14} strokeWidth={2} aria-hidden="true" />{tr(locale, "dt_thumb")}</summary>
            <p style={{ margin: "0 0 12px", fontSize: 13, lineHeight: 1.6 }}><b lang={langTag(lang)}>{lane.gen.thumbnail.headline}</b><br /><span lang="ko">{lane.gen.thumbnail.layout}</span></p>
          </details>
        )}
      </section>

      {/* 사람이 정하는 칸 + 포스터 */}
      <section aria-labelledby={`rf-decide-${m}`}>
        <div className="rf-decide">
          <h3 className="rf-sub-h" id={`rf-decide-${m}`} style={{ margin: 0 }}>
            <span>{tr(locale, "st_sign")}</span>
            <span className="rf-who" data-actor="person"><Mark actor="person" filled={!!lane.sign} />{tr(locale, "actor_person")}</span>
          </h3>
          {pick && (lane.sign ? (
            <>
              <div className="rf-stamp" data-fresh={lane.fresh?.sign ? "true" : undefined}>
                <Mark actor="person" size={12} />{tr(locale, "dt_signed", { name: lane.sign.by })}<small>{lane.sign.at}</small>
              </div>
              <div className="rf-btns">
                <button type="button" className="rf-btn" data-size="s" onClick={() => void copy(copies.map((c) => `[${c.platform === "x" ? "X" : "Instagram"}] ${c.text}${c.hashtags?.length ? `\n${c.hashtags.map((h) => `#${h}`).join(" ")}` : ""}`).join("\n\n"))}>
                  <Copy size={14} strokeWidth={1.75} aria-hidden="true" />{tr(locale, "dt_copy_all")}
                </button>
                <button type="button" className="rf-btn" data-kind="quiet" data-size="s" onClick={onUnsign}>{tr(locale, "dt_unapprove")}</button>
              </div>
            </>
          ) : (
            <>
              <p className="rf-sub-h" style={{ margin: "4px 0 0" }}>{tr(locale, "dt_before")}</p>
              {ready ? (
                before.length ? (
                  <ul className="rf-decide-list">
                    {before.map((b, k) => (
                      <li key={k}>
                        <Mark actor={b.actor} />
                        <span><span className="rf-flag" data-tone={b.tone === "avoid" ? "avoid" : undefined} style={{ fontWeight: 550 }}>{b.text}</span>{b.note && <span className="rf-note" style={{ display: "block", marginTop: 2 }} lang="ko">{b.note}</span>}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="rf-note" style={{ margin: 0 }}>{tr(locale, "dt_before_none")}</p>
              ) : <p className="rf-note" style={{ margin: 0 }}>{st.write.s === "run" ? tr(locale, "dt_copies_wait") : busy ? tr(locale, "dt_check_wait") : "–"}</p>}
              <div className="rf-btns" style={{ marginTop: 4 }}>
                <button type="button" className="rf-btn" data-kind="sign" disabled={!ready} onClick={onSign}>{tr(locale, "dt_approve", { market: name })}</button>
                <button type="button" className="rf-btn" data-kind="quiet" data-size="s" disabled={busy || !pick} onClick={onRedo}>{tr(locale, "dt_redo")}</button>
              </div>
              <p className="rf-note" style={{ margin: 0 }}>{tr(locale, "dt_approve_note")}{signer ? "" : ` ${tr(locale, "nav_signed_out")}.`}</p>
            </>
          ))}
          <p className="rf-toast" role="status">{toast}</p>
        </div>
        {pick && (
          <div className="rf-sub">
            <h4 className="rf-sub-h">{tr(locale, "dt_poster")} <span className="rf-who" data-actor="rule"><Mark actor="rule" filled={st.poster.s === "done"} />{tr(locale, "actor_rule")}</span></h4>
            <Poster poster={lane.poster} headline={headline} product={rec.brief?.product} lang={lang} locale={locale} />
          </div>
        )}
      </section>
    </div>
  );
}
