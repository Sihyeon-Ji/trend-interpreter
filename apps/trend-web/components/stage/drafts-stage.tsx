"use client";

import { ArrowUpRight, Copy as CopyIcon, ListChecks, RotateCw, Sparkles, Stamp } from "lucide-react";
import Link from "next/link";
import { ViewTransition, useState } from "react";
import { glossFor } from "@/lib/gloss";
import { koOrEn, type Locale } from "@/lib/i18n";
import { L, gap, sep, sourceLabel, sourceName } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import type { CopyIssue, ExcludedItem, RecommendItem, RecommendResult, SocialCopy } from "@/lib/types";
import { ActorTag, MemeWord, fmtDay, fmtStamp, type VerdictKind, verdictOf, wordVT } from "./bits";
import { Count } from "./count";
import { LANG_NAME, MARKET_LANG, diffusionWord, marketName, tx, type CopyKey, type Market } from "./copy";
import { MiniGlobe } from "./globe";
import { useElapsed, useFirstPlay, useHydrated } from "./play";
import { StepRail, flaggedCount, issuesFor, stepsOf } from "./rail";
import { focusMarket, redo, restart, sign, unsign, useStage, type Column, type Run } from "./store";

/* 시장별 초안 — 같은 무대에서 세 시장이 차례로 조립된다. 고른 말이 셋 나란히 선 한 박자 뒤, 일하는 시장이 앞(가운데 넓은 칸)으로 나오고
   나머지 둘은 옆으로 비켜서서 진행만 보인다. 사람이 시장을 누르면 그 시장을 앞으로 부르고, 그 뒤로는 자동으로 따라가지 않는다. */

const KIND_NOUN: Record<Locale, Record<string, string>> = {
  ko: { wiki: "문서", web: "문서", news: "기사", short: "영상" },
  en: { wiki: "page", web: "page", news: "article", short: "video" },
  ja: { wiki: "記事", web: "ページ", news: "記事", short: "動画" },
};

function statusText(col: Column, run: Run, locale: Locale): string {
  if (run.phase === "reading") return tx(locale, "s_reading");
  if (run.phase === "error") return tx(locale, "s_stopped");
  if (col.sign) return tx(locale, "s_signed", { who: col.sign.by });
  const key: Record<Column["status"], CopyKey> = { wait: "s_wait", writing: "s_writing", checking: "s_checking", poster: "s_poster", done: "s_done", failed: "s_failed", none: "s_none", stopped: "s_stopped" };
  return tx(locale, key[col.status]);
}

/** 문구 안의 고른 밈 — 노래 가사처럼 왼쪽부터 먹으로 차오른다. 무엇이 사전에서 왔는지 보이게 */
function Marked({ text, word, play }: { text: string; word?: string; play: boolean }) {
  if (!word || !text.includes(word)) return <>{text}</>;
  const at = text.indexOf(word);
  return <>{text.slice(0, at)}<mark className="rs-mark" data-play={play}>{text.slice(at, at + word.length)}</mark>{text.slice(at + word.length)}</>;
}

function issueLabel(i: CopyIssue, locale: Locale) {
  return tx(locale, `cp_issue_${i.code}` as CopyKey);
}

/** 규칙의 다시 보기 결과 — 결과가 오면 위에서부터 차례로 찍힌다(처음 한 번) */
function Checks({ c, i, n, col, run, locale }: { c: SocialCopy; i: number; n: number; col: Column; run: Run; locale: Locale }) {
  const play = useFirstPlay(`${run.id}-${col.market}-${col.rev}-check-${i}`);
  const issues = issuesFor(c.text, col.check);
  // 뜻 검사(AI 의견)는 다시 검사한 첫 Instagram 문구에만 있다
  const fit = col.check && c.platform === "instagram" && n === 1 ? col.check.memes.find((m) => m.fit) : undefined;
  return (
    <div className="rs-copy-checks" data-play={play}>
      <span className="rs-check" data-state={issues.length ? "flag" : "ok"} data-avoid={issues.some((x) => x.code === "avoid")}>
        <ListChecks aria-hidden="true" size={14} />
        <span className="rs-sr">{tx(locale, "cp_rule")}: </span>
        {issues.length ? [...new Set(issues.map((x) => issueLabel(x, locale)))].join(sep(locale)) : col.checkFailed && i === 0 ? tx(locale, "cp_check_missing") : tx(locale, "cp_rule_ok")}
      </span>
      {fit?.fit ? (
        <span className="rs-check" data-who="ai" data-state={fit.fit === "ok" ? "ok" : "flag"}>
          <Sparkles aria-hidden="true" size={14} />
          <span className="rs-sr">{tx(locale, "cp_ai")}: </span>
          {tx(locale, fit.fit === "ok" ? "cp_fit_ok" : fit.fit === "off" ? "cp_fit_off" : "cp_fit_unsure")}
        </span>
      ) : null}
    </div>
  );
}

function CopyItem({ c, n, i, lang, word, col, run, locale, onCopy }: {
  c: SocialCopy; n: number; i: number; lang: string; word?: string; col: Column; run: Run; locale: Locale; onCopy: (text: string) => void;
}) {
  const fill = useFirstPlay(`${run.id}-${col.market}-${col.rev}-fill-${i}`);
  const checked = !!col.check || col.checkFailed || col.status === "poster" || col.status === "done";
  const flagged = issuesFor(c.text, col.check).length > 0;
  const text = c.text + (c.hashtags?.length ? ` ${c.hashtags.map((h) => `#${h}`).join(" ")}` : "");
  return (
    <li className="rs-copy" style={{ "--i": i } as React.CSSProperties} data-play={fill} data-flag={flagged}>
      <p className="rs-copy-k">{c.platform === "x" ? "X" : "Instagram"} {n}</p>
      <p className="rs-copy-t" lang={lang}><Marked text={c.text} word={word} play={fill} /></p>
      {c.hashtags?.length ? <p className="rs-copy-tags" lang={lang}>{c.hashtags.map((h) => <span key={h}>#{h}</span>)}</p> : null}
      {c.note_ko ? <p className="rs-copy-note"><span>{tx(locale, "cp_note")}</span>{c.note_ko}</p> : null}
      {checked ? <Checks c={c} i={i} n={n} col={col} run={run} locale={locale} /> : (
        <div className="rs-copy-checks"><span className="rs-check" data-state="pending"><ListChecks aria-hidden="true" size={14} />{tx(locale, "s_checking")}</span></div>
      )}
      {col.sign ? (
        <button type="button" className="rs-btn" data-kind="ghost" data-size="s" onClick={() => onCopy(text)}><CopyIcon aria-hidden="true" size={14} />{tx(locale, "cp_copy")}</button>
      ) : null}
    </li>
  );
}

/** 사람의 승인 — 도장이 찍히듯(처음 한 번) */
function Seal({ playKey }: { playKey: string }) {
  const play = useFirstPlay(playKey);
  return <span className="rs-seal" data-play={play} aria-hidden="true"><Stamp size={22} strokeWidth={2} /></span>;
}

function WhyChips({ item, rec, locale }: { item: RecommendItem; rec: RecommendResult; locale: Locale }) {
  const labels = L(locale);
  const v: VerdictKind = verdictOf(item);
  const chips: { k: string; v: string }[] = [];
  if (item.matched_category && rec.brief) chips.push({ k: tx(locale, "pk_why_cat"), v: labels.fitCategory[rec.brief.category] });
  else if (item.any_category) chips.push({ k: tx(locale, "pk_why_any"), v: "" });
  if (item.matched_feelings.length) chips.push({ k: tx(locale, "pk_why_feel"), v: item.matched_feelings.map((f) => labels.feeling[f]).join(sep(locale)) });
  if (item.diffusion) chips.push({ k: tx(locale, "pk_why_spread"), v: diffusionWord(item.diffusion, locale) });
  chips.push({ k: tx(locale, "pk_why_stage"), v: labels.lifecycle[item.lifecycle] });
  chips.push({ k: v === "caution" ? tx(locale, "pk_why_risk_caution") : v === "ok" ? tx(locale, "pk_why_risk_ok") : tx(locale, "pk_why_risk_unknown"), v: "" });
  return (
    <ul className="rs-chips">
      {chips.map((c, i) => <li key={i} data-risk={i === chips.length - 1 ? v : undefined}>{c.v ? <><span>{c.k}</span><b>{c.v}</b></> : <b>{c.k}</b>}</li>)}
    </ul>
  );
}



function SourceLine({ item, locale }: { item: RecommendItem; locale: Locale }) {
  const docs = item.evidences.filter((e) => e.kind !== "community");
  const ref = docs.find((e) => e.kind === "wiki" || e.kind === "web") ?? docs[0];
  if (!ref) return null;
  return (
    <p className="rs-src">
      <span className="rs-src-k">{tx(locale, "pk_source")}</span>
      <a href={ref.url} target="_blank" rel="noopener noreferrer" className="rs-link">{sourceLabel(locale, sourceName(locale, ref.source_domain), KIND_NOUN[locale][ref.kind] ?? "")}<ArrowUpRight aria-hidden="true" size={13} /></a>
      <span className="rs-src-date">{fmtDay(ref.observed_at, locale, true)}</span>
    </p>
  );
}

function Excluded({ items, market, locale, play }: { items: ExcludedItem[]; market: Market; locale: Locale; play: boolean }) {
  return (
    <div className="rs-sub">
      <h4><ActorTag who="rule" locale={locale}>{tx(locale, "pk_out")}</ActorTag></h4>
      {items.length ? (
        <ul className="rs-out" data-play={play}>
          {items.map((e, i) => (
            <li key={e.term_id} style={{ "--i": i } as React.CSSProperties}>
              <Link href={`/dictionary/${encodeURIComponent(e.term_id)}?m=${market}`} className="rs-out-word" lang={langTag(e.lang)} data-code={e.code}>{e.canonical}</Link>
              <span className="rs-out-code" data-code={e.code}>{tx(locale, `ex_${e.code}` as CopyKey)}</span>
              <span className="rs-out-why">{tx(locale, `ex_${e.code}_why` as CopyKey)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="rs-quiet">{tx(locale, "pk_out_none")}</p>}
    </div>
  );
}

/** 무대 앞 — 고른 말, 문구와 확인, 포스터와 승인 */
function FullView({ col, run, locale, reviewer }: { col: Column; run: Run; locale: Locale; reviewer: string | null }) {
  const rec = run.rec;
  const m = col.market;
  const name = marketName(locale, m);
  const [toast, setToast] = useState("");
  const copies = col.gen?.copies ?? [];
  const lang = langTag(col.gen?.language ?? MARKET_LANG[m]) ?? MARKET_LANG[m];
  const langName = LANG_NAME[locale][MARKET_LANG[m]];
  const pool = rec?.pool?.[m] ?? 0;
  const considered = rec?.considered_by_region?.[m] ?? rec?.items.filter((i) => i.write_regions.includes(m)).length ?? 0;
  const excluded = (rec?.excluded ?? []).filter((e) => e.regions.includes(m)).slice(0, 4);
  const outPlay = useFirstPlay(`${run.id}-${m}-out`);
  const flagged = flaggedCount(col.gen, col.check);
  const busy = ["wait", "writing", "checking", "poster"].includes(col.status);
  const headline = col.gen?.thumbnail?.headline ?? copies[0]?.text.split(/[.!?。！？\n]/)[0] ?? "";
  const image = col.poster?.images[0] ?? run.photoUrl;
  // 'Instagram 1, 2 / X 1, 2' — 플랫폼마다 따로 센다
  const nums = copies.map((c, i) => copies.slice(0, i + 1).filter((d) => d.platform === c.platform).length);
  const waited = useElapsed(col.since, col.status === "writing" || col.status === "checking");

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setToast(tx(locale, "cp_copied")); } catch { setToast(tx(locale, "cp_copy_fail")); }
  };

  return (
    <article className="rs-full" aria-labelledby={`rs-h-${m}`}>
      <header className="rs-full-head">
        <MiniGlobe market={m} size={44} tone="ink" />
        <div className="rs-full-id">
          <h2 id={`rs-h-${m}`}>{name}</h2>
          <p>{tx(locale, `m_${m}_lang` as CopyKey)}</p>
        </div>
        <StepRail steps={stepsOf(col, run)} locale={locale} label={`${name}, ${tx(locale, "st_flow")}`} />
      </header>

      <div className="rs-full-body">
        {/* 1 고르기 — 규칙 */}
        <section className="rs-z rs-z-pick" aria-label={tx(locale, "step_pick")}>
          {col.pick && rec ? (
            <>
              <p className="rs-z-k">
                <ActorTag who="rule" locale={locale} state="done">
                  {tx(locale, "pk_funnel", { pool: "{pool}", n: "{n}" }).split(/(\{pool\}|\{n\})/).map((part, i) =>
                    part === "{pool}" ? <span key={i}>{pool.toLocaleString("en-US")}</span>
                      : part === "{n}" ? <Count key={i} from={pool} to={considered} playKey={`${run.id}-${m}-count`} />
                        : <span key={i}>{part}</span>)}
                </ActorTag>
              </p>
              <Link href={`/dictionary/${encodeURIComponent(col.pick.term_id)}?m=${m}`} className="rs-pick" aria-describedby={`rs-gloss-${m}`}>
                <ViewTransition name={wordVT(col.pick.term_id, m)} share="rs-morph" default="none">
                  <MemeWord text={col.pick.canonical} lang={col.pick.lang} max={96} min={34} />
                </ViewTransition>
                <span className="rs-pick-open">{tx(locale, "pk_open")}<ArrowUpRight aria-hidden="true" size={14} /></span>
              </Link>
              <p className="rs-gloss" id={`rs-gloss-${m}`} lang={scriptLang(glossFor(col.pick, locale))}>{glossFor(col.pick, locale)}</p>
              {col.pick.local_note ? <p className="rs-local"><span>{tx(locale, "pk_why_local")}</span>{col.pick.local_note[koOrEn(locale)]}</p> : null}
              <div className="rs-sub">
                <h4>{tx(locale, "pk_why")}</h4>
                <WhyChips item={col.pick} rec={rec} locale={locale} />
              </div>
              <SourceLine item={col.pick} locale={locale} />
              {col.alts.length > 0 && (
                <div className="rs-sub">
                  <h4>{tx(locale, "pk_alts")}</h4>
                  <ul className="rs-alts">
                    {col.alts.map((a) => (
                      <li key={a.term_id}>
                        <span lang={langTag(a.lang)}>{a.canonical}</span>
                        <button type="button" className="rs-btn" data-kind="ghost" data-size="s" disabled={busy} onClick={() => void redo(m, a.term_id)}>{tx(locale, "pk_swap")}</button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <Excluded items={excluded} market={m} locale={locale} play={outPlay} />
            </>
          ) : (
            <div className="rs-none">
              <p className="rs-z-k"><ActorTag who="rule" locale={locale} state="done">{tx(locale, "s_none")}</ActorTag></p>
              <p className="rs-none-word">{tx(locale, "s_none")}</p>
              <p className="rs-quiet">{tx(locale, "pk_none", { pool: pool.toLocaleString("en-US") })}</p>
              <Link className="rs-link" href={`/trends?m=${m}`}>{tx(locale, "pk_browse", { market: name })}</Link>
              {rec && <Excluded items={excluded} market={m} locale={locale} play={outPlay} />}
            </div>
          )}
        </section>

        {/* 2·3 쓰기와 확인 — AI 가 쓰고 규칙이 다시 본다 */}
        {col.status !== "none" && (
          <section className="rs-z rs-z-copy" aria-label={tx(locale, "step_write")} aria-busy={col.status === "writing" || col.status === "checking"}>
            <p className="rs-z-k">
              <ActorTag who="ai" locale={locale} state={col.status === "writing" ? "working" : col.gen ? "done" : "idle"}>
                {col.gen ? tx(locale, "cp_head", { lang: langName, n: copies.length })
                  : col.status === "writing" ? tx(locale, "cp_writing", { lang: langName })
                    : col.status === "wait" ? tx(locale, "s_wait") : tx(locale, col.status === "failed" ? "s_failed" : "s_stopped")}
              </ActorTag>
              {col.status === "writing" && waited > 0 ? <span className="rs-elapsed rs-num" aria-hidden="true">{tx(locale, "sec", { n: waited })}</span> : null}
            </p>
            {col.gen ? (
              <ol className="rs-copies" data-checking={col.status === "checking"}>
                {copies.map((c, i) => (
                  <CopyItem key={`${col.rev}-${i}`} c={c} i={i} n={nums[i]} lang={lang} word={col.pick?.canonical} col={col} run={run} locale={locale} onCopy={(t) => void copy(t)} />
                ))}
              </ol>
            ) : col.status === "failed" ? (
              <p className="rs-error">{tx(locale, "cp_failed")}</p>
            ) : col.status === "stopped" ? null : (
              <ol className="rs-ghosts" aria-hidden="true" data-still={col.status !== "writing"}>{[0, 1, 2, 3].map((k) => <li key={k} style={{ "--i": k } as React.CSSProperties}><i /><i /><i /></li>)}</ol>
            )}
            {col.gen?.dropped.length ? (
              <details className="rs-more">
                <summary><ListChecks aria-hidden="true" size={14} />{tx(locale, "cp_dropped", { n: col.gen.dropped.length })}</summary>
                <ul>{col.gen.dropped.map((d) => <li key={d.id}>{tx(locale, `cp_drop_${d.code}` as CopyKey)}</li>)}</ul>
              </details>
            ) : null}
            {col.gen?.script ? (
              <details className="rs-more">
                <summary>{tx(locale, "cp_script", { n: col.gen.script.duration_s })} <span className="rs-quiet">{tx(locale, "cp_scenes", { n: col.gen.script.scenes.length })}</span></summary>
                <table className="rs-scenes">
                  <thead><tr><th scope="col">{tx(locale, "cp_time")}</th><th scope="col">{tx(locale, "cp_visual")}</th><th scope="col">{tx(locale, "cp_caption")}</th></tr></thead>
                  <tbody>{col.gen.script.scenes.map((s) => <tr key={s.start_s}><td className="rs-num">{s.start_s}–{s.end_s}s</td><td>{s.visual}</td><td lang={lang}>{s.caption}</td></tr>)}</tbody>
                </table>
              </details>
            ) : null}
            {col.gen?.thumbnail ? (
              <details className="rs-more">
                <summary>{tx(locale, "cp_thumb")}</summary>
                <p><b lang={lang}>{col.gen.thumbnail.headline}</b> {col.gen.thumbnail.layout}</p>
              </details>
            ) : null}
          </section>
        )}

        {/* 포스터와 승인 — 사람 */}
        {col.status !== "none" && (
          <section className="rs-z rs-z-end" aria-label={tx(locale, "step_sign")}>
            <figure className="rs-poster">
              <div className="rs-poster-frame" role="img" aria-label={tx(locale, "po_alt", { text: headline })} data-img={!!image}>
                {image
                  // 생성 그림·올린 사진은 data/blob 주소라 next/image 를 쓰지 않는다
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={image} alt="" />
                  : <span className="rs-poster-blank" aria-hidden="true">{rec?.brief?.product ?? run.input.text}</span>}
                {headline ? <span className="rs-poster-copy" lang={lang}><b>{headline}</b><span>{rec?.brief?.product}</span></span> : null}
              </div>
              <figcaption>{tx(locale, "po_off")}{gap(locale)}{tx(locale, "po_cap")}</figcaption>
              {col.poster?.plan ? (
                <details className="rs-more">
                  <summary>{tx(locale, "po_plan")}</summary>
                  <dl className="rs-plan">
                    {col.poster.plan.scene ? <div><dt>{tx(locale, "po_scene")}</dt><dd lang="en">{col.poster.plan.scene}</dd></div> : null}
                    {col.poster.plan.mood.length ? <div><dt>{tx(locale, "po_mood")}</dt><dd lang="en">{col.poster.plan.mood.join(", ")}</dd></div> : null}
                    {col.poster.plan.colors.length ? <div><dt>{tx(locale, "po_colors")}</dt><dd>{col.poster.plan.colors.join(", ")}</dd></div> : null}
                  </dl>
                </details>
              ) : null}
            </figure>

            <div className="rs-approve">
              {col.sign ? (
                <div className="rs-signed">
                  <Seal key={col.sign.at} playKey={`${run.id}-${m}-seal-${col.sign.at}`} />
                  <p><b>{tx(locale, "s_signed", { who: col.sign.by })}</b><span>{fmtStamp(col.sign.at, locale)}</span></p>
                  <div className="rs-btns">
                    <button type="button" className="rs-btn" data-kind="primary" data-size="s" onClick={() => void copy(copies.map((c) => `[${c.platform === "x" ? "X" : "Instagram"}] ${c.text}`).join("\n\n"))}>
                      <CopyIcon aria-hidden="true" size={15} />{tx(locale, "cp_copy_all")}
                    </button>
                    <button type="button" className="rs-btn" data-kind="ghost" data-size="s" onClick={() => unsign(m)}>{tx(locale, "ap_unsign")}</button>
                  </div>
                  <p className="rs-quiet">{tx(locale, "ap_local")}</p>
                </div>
              ) : col.status === "done" ? (
                <>
                  {flagged ? <p className="rs-approve-flag">{tx(locale, "ap_flag", { n: flagged })}</p> : null}
                  <button type="button" className="rs-btn rs-approve-btn" data-kind="primary" onClick={() => sign(m, reviewer ?? tx(locale, "ap_reviewer"))}>
                    <Stamp aria-hidden="true" size={17} />{tx(locale, "ap_btn", { market: name })}
                  </button>
                  <p className="rs-quiet">{tx(locale, "ap_note")}</p>
                  <button type="button" className="rs-btn" data-kind="ghost" data-size="s" onClick={() => void redo(m)}><RotateCw aria-hidden="true" size={14} />{tx(locale, "ap_redo")}</button>
                </>
              ) : col.status === "failed" || col.status === "stopped" ? (
                <button type="button" className="rs-btn" data-kind="quiet" onClick={() => void redo(m)}><RotateCw aria-hidden="true" size={15} />{tx(locale, "ap_retry")}</button>
              ) : (
                <p className="rs-approve-wait"><Stamp aria-hidden="true" size={15} />{tx(locale, "ap_wait")}</p>
              )}
              <p className="rs-toast" role="status">{toast}</p>
            </div>
          </section>
        )}
      </div>
    </article>
  );
}

/** 옆으로 비켜선 시장 — 진행만 보인다. 누르면 무대 앞으로 */
function WingView({ col, run, locale }: { col: Column; run: Run; locale: Locale }) {
  const m = col.market;
  const name = marketName(locale, m);
  const status = statusText(col, run, locale);
  return (
    <div className="rs-wing" data-status={col.status} data-signed={!!col.sign}>
      <div className="rs-wing-head">
        <MiniGlobe market={m} size={28} tone="ink" />
        <b>{name}</b>
      </div>
      <StepRail steps={stepsOf(col, run)} locale={locale} size="s" label={`${name}, ${tx(locale, "st_flow")}`} />
      <div className="rs-wing-word">
        {col.pick ? <MemeWord text={col.pick.canonical} lang={col.pick.lang} max={36} min={17} /> : <span className="rs-quiet">{tx(locale, "s_none")}</span>}
      </div>
      <p className="rs-wing-status" data-who={col.sign ? "human" : col.status === "writing" ? "ai" : "rule"}>{status}</p>
      {col.gen?.copies[0] ? <p className="rs-wing-peek" lang={langTag(col.gen.language)}>{col.gen.copies[0].text}</p> : null}
      <button type="button" className="rs-wing-hit" aria-label={`${tx(locale, "dr_open", { market: name })}. ${status}`} onClick={() => focusMarket(m)} />
    </div>
  );
}

/** 셋이 나란히 — 읽는 중에는 그 시장의 말이 흐려지고, 고른 말이 오면 한 박자 동안 세 말이 나란히 선다 */
function EqualView({ col, run, locale }: { col: Column; run: Run; locale: Locale }) {
  const m = col.market;
  const name = marketName(locale, m);
  const live = run.live.find((l) => l.market === m);
  const rec = run.rec;
  const pool = rec?.pool?.[m] ?? live?.count ?? 0;
  const considered = rec?.considered_by_region?.[m] ?? 0;
  return (
    <div className="rs-eq" data-phase={run.phase}>
      <div className="rs-eq-head">
        <MiniGlobe market={m} size={36} tone="ink" />
        <span><b>{name}</b><span>{tx(locale, `m_${m}_lang` as CopyKey)}</span></span>
      </div>
      <StepRail steps={stepsOf(col, run)} locale={locale} size="s" label={`${name}, ${tx(locale, "st_flow")}`} />
      {run.phase === "reading" || !rec ? (
        <>
          <p className="rs-eq-status"><ActorTag who="rule" locale={locale} state={run.phase === "reading" ? "working" : "idle"}>{statusText(col, run, locale)}</ActorTag></p>
          <ul className="rs-eq-live" aria-hidden="true">
            {(live?.words ?? []).slice(0, 5).map((w, i) => <li key={w.id} lang={langTag(w.lang)} style={{ "--i": i } as React.CSSProperties}>{w.word}</li>)}
          </ul>
        </>
      ) : col.pick ? (
        <>
          <p className="rs-eq-status">
            <ActorTag who="rule" locale={locale} state="done">
              {tx(locale, "pk_funnel", { pool: "{pool}", n: "{n}" }).split(/(\{pool\}|\{n\})/).map((part, i) =>
                part === "{pool}" ? <span key={i}>{pool.toLocaleString("en-US")}</span>
                  : part === "{n}" ? <Count key={i} from={pool} to={considered} playKey={`${run.id}-${m}-count`} />
                    : <span key={i}>{part}</span>)}
            </ActorTag>
          </p>
          <div className="rs-eq-word"><MemeWord text={col.pick.canonical} lang={col.pick.lang} max={84} min={30} /></div>
          <p className="rs-eq-gloss" lang={scriptLang(glossFor(col.pick, locale))}>{glossFor(col.pick, locale)}</p>
        </>
      ) : (
        <>
          <p className="rs-eq-status"><ActorTag who="rule" locale={locale} state="done">{tx(locale, "s_none")}</ActorTag></p>
          <p className="rs-none-word">{tx(locale, "s_none")}</p>
          <p className="rs-quiet">{tx(locale, "pk_none", { pool: pool.toLocaleString("en-US") })}</p>
        </>
      )}
      {rec ? <button type="button" className="rs-wing-hit" aria-label={tx(locale, "dr_open", { market: name })} onClick={() => focusMarket(m)} /> : null}
    </div>
  );
}

function BriefBar({ run, locale }: { run: Run; locale: Locale }) {
  const labels = L(locale);
  const waited = useElapsed(run.at, run.phase === "reading");
  const rec = run.rec;
  const product = rec?.brief?.product ?? run.input.text.trim();
  const signed = run.cols.filter((c) => c.sign).length;
  return (
    <ViewTransition name="rs-brief" share="rs-morph" default="none">
      <div className="rs-brief" data-phase={run.phase}>
        {run.photoUrl
          // eslint-disable-next-line @next/next/no-img-element
          ? <img className="rs-brief-photo" src={run.photoUrl} alt={tx(locale, "po_photo")} />
          : null}
        <div className="rs-brief-main">
          <h1 className="rs-brief-product" data-reading={run.phase === "reading"}>{product || tx(locale, "po_photo")}</h1>
          {run.input.text.trim() && rec?.brief?.product && run.input.text.trim() !== rec.brief.product ? <p className="rs-brief-text">{run.input.text.trim()}</p> : null}
          <dl className="rs-brief-meta">
            {rec?.brief ? <div><dt>{tx(locale, "dr_category")}</dt><dd>{labels.fitCategory[rec.brief.category]}{run.input.category ? "" : <span className="rs-quiet">{locale === "ja" ? `（${tx(locale, "dr_category_auto")}）` : ` (${tx(locale, "dr_category_auto")})`}</span>}</dd></div> : null}
            <div><dt>{tx(locale, "dr_tone")}</dt><dd>{labels.campaignTone[run.input.tone]}</dd></div>
            <div><dt>{tx(locale, "dr_at")}</dt><dd>{fmtStamp(run.at, locale)}</dd></div>
          </dl>
          {run.phase === "reading" ? (
            <p className="rs-brief-status" role="status">
              <ActorTag who="ai" locale={locale} state="working">{tx(locale, "dr_reading")}</ActorTag>
              {waited > 0 ? <span className="rs-elapsed rs-num" aria-hidden="true">{tx(locale, "sec", { n: waited })}</span> : null}
            </p>
          ) : null}
        </div>
        <div className="rs-brief-end">
          <p className="rs-tally" aria-live="polite">{tx(locale, "dr_tally", { n: run.cols.length, m: signed })}</p>
          <Link href="/" className="rs-btn" data-kind="quiet" data-size="s">{tx(locale, "dr_edit")}</Link>
        </div>
      </div>
    </ViewTransition>
  );
}

export function DraftsStage({ locale, reviewer }: { locale: Locale; reviewer: string | null }) {
  const { run } = useStage();
  const hydrated = useHydrated();
  if (!hydrated) return <section className="rs-stage" data-scene="drafts" aria-busy="true" />;
  if (!run) {
    return (
      <section className="rs-stage rs-stage-empty" data-scene="drafts" aria-labelledby="rs-empty-h">
        <h1 id="rs-empty-h" className="rs-lede">{tx(locale, "dr_empty")}</h1>
        <Link href="/" className="rs-btn" data-kind="primary">{tx(locale, "dr_empty_go")}</Link>
      </section>
    );
  }
  const front = run.active && run.cols.some((c) => c.market === run.active) ? run.active : null;
  return (
    <ViewTransition name="rs-stage" share="rs-stage-swap" default="none">
      <section className="rs-stage" data-scene="drafts" aria-label={tx(locale, "dr_title")}>
        <BriefBar run={run} locale={locale} />
        {run.phase === "error" ? (
          <div className="rs-alert" role="alert">
            <p>{tx(locale, run.error === "busy" ? "dr_busy" : run.error === "too_big" ? "st_too_big" : run.error === "bad_type" ? "st_bad_type" : run.error === "need_input" ? "st_need_input" : run.error === "stopped" ? "s_stopped" : "dr_failed")}</p>
            <div className="rs-btns">
              <button type="button" className="rs-btn" data-kind="primary" data-size="s" onClick={() => restart(locale)}>{tx(locale, "dr_retry_all")}</button>
              <Link href="/" className="rs-btn" data-kind="quiet" data-size="s">{tx(locale, "dr_edit")}</Link>
            </div>
          </div>
        ) : null}
        <div className="rs-track" data-front={front ? "yes" : "no"}>
          {run.cols.map((col) => {
            const role = !front ? "equal" : front === col.market ? "full" : "wing";
            return (
              <ViewTransition key={col.market} name={`rs-col-${col.market}`} share="rs-morph" default="none">
                <div className="rs-panel" data-role={role} data-market={col.market}>
                  {role === "full" ? <FullView col={col} run={run} locale={locale} reviewer={reviewer} />
                    : role === "wing" ? <WingView col={col} run={run} locale={locale} />
                      : <EqualView col={col} run={run} locale={locale} />}
                </div>
              </ViewTransition>
            );
          })}
        </div>
      </section>
    </ViewTransition>
  );
}
