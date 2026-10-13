"use client";

import { Camera, ChevronDown, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ViewTransition, useEffect, useId, useRef, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { L } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { CampaignTone, FitCategory } from "@/lib/types";
import { ActorTag, MemeWord, Reading, RiskMark, fmtN, fmtStamp, wordVT } from "./bits";
import { tx, marketName, type CopyKey, type Market } from "./copy";
import { MiniGlobe } from "./globe";
import { seedInput, setInput, setPhoto, startRun, toggleMarket, useStage, type MarketLive, type Pin } from "./store";

const TONES: CampaignTone[] = ["friendly", "witty", "premium"];

/** 무대 위 시장 하나 — 머리(지구·이름)를 누르면 이 시장을 넣고 뺀다. 아래는 그 나라 글자로 된 지금 쓰이는 말 */
function MarketColumn({ live, on, locale }: { live: MarketLive; on: boolean; locale: Locale }) {
  const m = live.market;
  const name = marketName(locale, m);
  return (
    <ViewTransition name={`rs-col-${m}`} share="rs-morph" default="none">
      <div className="rs-col" data-on={on}>
        <button type="button" className="rs-col-head" aria-pressed={on} aria-label={tx(locale, "m_include", { market: name })} onClick={() => toggleMarket(m)}>
          <MiniGlobe market={m} size={40} tone={on ? "blue" : "mute"} />
          <span className="rs-col-id">
            <span className="rs-col-name">{name}</span>
            <span className="rs-col-meta">{tx(locale, `m_${m}_lang` as CopyKey)}</span>
          </span>
          <span className="rs-switch" aria-hidden="true"><i /></span>
        </button>
        <p className="rs-col-count">{live.failed ? "" : tx(locale, "m_count", { n: fmtN(live.count) })}</p>
        {live.words.length ? (
          <ol className="rs-live" aria-label={`${name}, ${tx(locale, "m_live")}`}>
            {live.words.map((w, i) => (
              <li key={w.id} data-rank={i === 0 ? 1 : i < 3 ? 2 : 3} style={{ "--i": i } as React.CSSProperties}>
                <Link href={`/dictionary/${encodeURIComponent(w.id)}?m=${m}`} className="rs-live-link" aria-describedby={`tip-${m}-${i}`}>
                  <ViewTransition name={wordVT(w.id, m)} share="rs-morph" default="none">
                    <MemeWord text={w.word} lang={w.lang} max={i === 0 ? 60 : i < 3 ? 34 : 22} min={i === 0 ? 30 : 18} />
                  </ViewTransition>
                  <Reading readings={w.readings} locale={locale} />
                </Link>
                <RiskMark kind={w.verdict} locale={locale} />
                <span className="rs-tip" role="tooltip" id={`tip-${m}-${i}`}>{w.gloss}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="rs-col-empty">{tx(locale, "m_live_none")}</p>
        )}
        <p className="rs-col-foot">
          <span>{tx(locale, "m_live")}</span>
          <Link href={`/trends?m=${m}`} className="rs-link">{tx(locale, "m_all", { market: name })}</Link>
        </p>
      </div>
    </ViewTransition>
  );
}

export function StartStage({ locale, live, seedMarkets, pin }: { locale: Locale; live: MarketLive[]; seedMarkets: Market[] | null; pin: Pin | null }) {
  const { input, photo, run } = useStage();
  const router = useRouter();
  const labels = L(locale);
  const categories = Object.keys(labels.fitCategory) as FitCategory[];
  const [error, setError] = useState<CopyKey | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const textId = useId();
  const seedKey = JSON.stringify([seedMarkets, pin?.id ?? null]);
  const seeded = useRef<string | null>(null);

  // 주소로 넘어온 시장·밈을 한 번만 넣는다(언어를 바꿔 다시 그려도 사람이 고친 것을 덮지 않게)
  useEffect(() => {
    if (seeded.current === seedKey) return;
    seeded.current = seedKey;
    seedInput(seedMarkets, pin);
  }, [seedKey, seedMarkets, pin]);

  const pickPhoto = (f: File | null) => {
    const e = setPhoto(f);
    setError(e === "too_big" ? "st_too_big" : e === "bad_type" ? "st_bad_type" : null);
    if (e || !f) setFileKey((k) => k + 1);
  };

  const submit = () => {
    const e = startRun({ locale, live });
    if (e) {
      setError(e === "need_market" ? "st_need_market" : "st_need_input");
      return;
    }
    setError(null);
    router.push(`/drafts`);
  };

  const n = input.markets.length;
  // 자료를 마지막으로 모은 때 — 세 시장 가운데 가장 최근(무대 위 말이 언제 것인지)
  const dataAt = live.map((l) => l.at).filter((x): x is string => !!x).sort().at(-1) ?? null;
  return (
    <ViewTransition name="rs-stage" share="rs-stage-swap" default="none">
      <section className="rs-stage" data-scene="compose" aria-labelledby="rs-start-h">
        <div className="rs-stage-head">
          {dataAt ? <p className="rs-stage-at">{tx(locale, "xp_updated")} <span>{fmtStamp(dataAt, locale)}</span></p> : null}
          <h1 id="rs-start-h" className="rs-lede">{tx(locale, "st_lede")}</h1>
          <ol className="rs-flow" aria-label={tx(locale, "st_flow")}>
            <li><ActorTag who="rule" locale={locale}>{tx(locale, "st_flow1")}</ActorTag></li>
            <li><ActorTag who="ai" locale={locale}>{tx(locale, "st_flow2")}</ActorTag></li>
            <li><ActorTag who="rule" locale={locale}>{tx(locale, "st_flow3")}</ActorTag></li>
            <li><ActorTag who="human" locale={locale}>{tx(locale, "st_flow4")}</ActorTag></li>
          </ol>
        </div>

        <div className="rs-cols">
          {live.map((l) => <MarketColumn key={l.market} live={l} on={input.markets.includes(l.market)} locale={locale} />)}
        </div>

        <ViewTransition name="rs-brief" share="rs-morph" default="none">
          <form className="rs-desk" aria-labelledby="rs-start-h" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            {run && (
              <Link className="rs-resume" href="/drafts">{tx(locale, "st_resume")}</Link>
            )}
            <div className="rs-desk-main">
              <label className="rs-photo" data-has={!!photo}>
                <input key={fileKey} type="file" accept="image/jpeg,image/png,image/webp" aria-label={photo ? tx(locale, "st_photo_change") : tx(locale, "st_photo")}
                  onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
                {photo
                  // 올린 사진은 브라우저 메모리의 주소라 next/image 최적화를 쓰지 않는다
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={photo.url} alt="" />
                  : <Camera aria-hidden="true" size={22} strokeWidth={1.8} />}
              </label>
              <div className="rs-field">
                <label htmlFor={textId} className="rs-sr">{tx(locale, "st_product")}</label>
                {input.pin && (
                  <span className="rs-pin">
                    <span className="rs-pin-k">{tx(locale, "st_pinned")}</span>
                    <b lang={langTag(input.pin.lang)}>{input.pin.word}</b>
                    <button type="button" aria-label={tx(locale, "st_pinned_remove")} onClick={() => setInput({ pin: null })}><X aria-hidden="true" size={14} /></button>
                  </span>
                )}
                <textarea id={textId} rows={2} maxLength={500} value={input.text} placeholder={tx(locale, "st_product_ph")}
                  onChange={(e) => { setInput({ text: e.target.value }); if (error === "st_need_input") setError(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } }} />
                <p className="rs-field-note">
                  {photo ? (
                    <button type="button" className="rs-link" onClick={() => pickPhoto(null)}>{tx(locale, "st_photo_remove")}</button>
                  ) : null}
                  <span>{tx(locale, "st_photo_note")}</span>
                </p>
              </div>
            </div>
            <div className="rs-desk-bar">
              <label className="rs-select">
                <span>{tx(locale, "st_category")}</span>
                <select value={input.category} onChange={(e) => setInput({ category: e.target.value as FitCategory | "" })}>
                  <option value="">{tx(locale, "st_auto")}</option>
                  {categories.map((c) => <option key={c} value={c}>{labels.fitCategory[c]}</option>)}
                </select>
                <ChevronDown aria-hidden="true" size={16} />
              </label>
              <div className="rs-seg" role="radiogroup" aria-label={tx(locale, "st_tone")}
                onKeyDown={(e) => {
                  // 라디오 묶음 — 화살표로 옮기며 고른다(탭 한 번으로 묶음 안팎을 오간다)
                  if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
                  e.preventDefault();
                  const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
                  const next = TONES[(TONES.indexOf(input.tone) + step + TONES.length) % TONES.length];
                  setInput({ tone: next });
                  e.currentTarget.querySelector<HTMLButtonElement>(`[data-tone="${next}"]`)?.focus();
                }}>
                {TONES.map((tn) => (
                  <button key={tn} type="button" role="radio" data-tone={tn} aria-checked={input.tone === tn} tabIndex={input.tone === tn ? 0 : -1} onClick={() => setInput({ tone: tn })}>{labels.campaignTone[tn]}</button>
                ))}
              </div>
              <span className="rs-desk-sum" aria-live="polite">
                {n ? tx(locale, "st_markets_n", { n }) : tx(locale, "st_markets_none")}
                <span className="rs-desk-time">{tx(locale, "st_time")}</span>
              </span>
              <button type="submit" className="rs-btn" data-kind="primary">{tx(locale, "st_submit")}</button>
            </div>
            <p className="rs-desk-error" role="alert">{error ? tx(locale, error) : ""}</p>
          </form>
        </ViewTransition>
      </section>
    </ViewTransition>
  );
}
