"use client";

import Link from "next/link";
import { useState } from "react";
import { DRAFTS, ISSUE, market, type Copy, type Draft } from "@/lib/lab/n-redesign/data";
import { Who } from "./bits";

type Sign = { by: string; at: string; fresh?: boolean };

const ME = "김태우";
const now = () => {
  const d = new Date();
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

/** 카피 안의 밈을 굵게 밑줄 — 무엇이 사전에서 왔는지 보이게 */
function Marked({ text, word }: { text: string; word?: string }) {
  const stem = word && !text.includes(word) && word.endsWith(" 같다") ? word.replace(/ 같다$/, "") : word;
  if (!stem || !text.includes(stem)) return <>{text}</>;
  const at = text.indexOf(stem);
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + stem.length)}</mark>{text.slice(at + stem.length)}</>;
}

function CopyRow({ c, n, d, signed, onCopy }: { c: Copy; n: number; d: Draft; signed: boolean; onCopy: (t: string) => void }) {
  const flagged = c.issues.length > 0 || c.fit === "drift";
  return (
    <li className="n-copy" data-flag={flagged}>
      <div>
        <p className="n-copy-p">{c.platform} {n}</p>
        <p className="n-copy-t" lang={d.lang}><Marked text={c.text} word={c.mark ?? d.meme?.word} /></p>
        {c.tags?.length ? <p className="n-tags" lang={d.lang}>{c.tags.map((t) => <span key={t}>#{t}</span>)}</p> : null}
        {signed && <button type="button" className="n-btn" data-kind="quiet" data-size="s" style={{ marginTop: 6, paddingInline: 0 }} onClick={() => onCopy(c.text + (c.tags?.length ? " " + c.tags.map((t) => "#" + t).join(" ") : ""))}>이 카피 복사</button>}
      </div>
      <div className="n-check">
        <div>
          <Who kind="rule">규칙 확인</Who>
          {c.issues.length === 0
            ? <p className="n-ok">문제 없음</p>
            : c.issues.map((i) => (
              <p key={i.code}><span className="n-flag" data-tone={i.code === "avoid" ? "avoid" : "caution"}>{ISSUE[i.code]}</span>{i.note ? `. ${i.note}` : ""}</p>
            ))}
        </div>
        {c.fit && (
          <div>
            <Who kind="model">모델 의견</Who>
            <p>{c.fit === "ok" ? <span className="n-ok">뜻에 맞게 씀</span> : <span className="n-flag" data-tone="caution">뜻이 조금 넓어짐</span>}{c.fitNote ? `. ${c.fitNote}` : ""}</p>
          </div>
        )}
      </div>
    </li>
  );
}

function MarketDraft({ d, sign, onSign, onUnsign }: { d: Draft; sign?: Sign; onSign: () => void; onUnsign: () => void }) {
  const m = market(d.market);
  const [toast, setToast] = useState("");
  const copy = async (text: string, what: string) => {
    try { await navigator.clipboard.writeText(text); setToast(`${what} 복사했습니다.`); } catch { setToast("복사하지 못했습니다. 브라우저의 클립보드 권한을 확인하세요."); }
  };
  const flagged = d.copies.filter((c) => c.issues.length || c.fit === "drift").length;
  const passed = d.copies.length - flagged;
  let ig = 0, x = 0;

  return (
    <section className="n-market" id={`m-${d.market}`} aria-labelledby={`h-${d.market}`}>
      <div className="n-market-head">
        <h2 className="n-h2" id={`h-${d.market}`}>{m.name}</h2>
        <span className="n-meta">{m.en}, {d.lang === "ko" ? "한국어" : d.lang === "ja" ? "일본어" : "태국어"}로 씀</span>
      </div>

      <ol className="n-trail" aria-label={`${m.name} 초안이 만들어진 순서`}>
        <li>
          <span className="n-trail-top"><Who kind="rule" /></span>
          <span>{d.meme
            ? <>확인된 말 <strong className="n-num">{d.candidates.toLocaleString("ko-KR")}</strong>개 중 <strong className="n-num">{d.considered}</strong>개를 견주어 <strong lang={d.meme.lang}>{d.meme.word}</strong>를 골랐습니다.</>
            : <>확인된 말 <strong className="n-num">{d.candidates}</strong>개를 모두 견주었지만 맞는 말이 없었습니다.</>}</span>
        </li>
        <li>
          <span className="n-trail-top"><Who kind="model" /></span>
          <span>카피 <strong>{d.copies.length}</strong>개{d.script ? ", 영상 대본, 썸네일 계획" : ""}을 썼습니다. {d.model}, 호출 {d.modelCalls}번.</span>
        </li>
        <li>
          <span className="n-trail-top"><Who kind="rule" /></span>
          <span>{flagged ? <>카피 <strong>{passed}</strong>개 통과, <strong>{flagged}</strong>개 표시.</> : <>카피 <strong>{d.copies.length}</strong>개 모두 통과.</>}</span>
        </li>
        <li>
          <span className="n-trail-top">{sign ? <Who kind="human">{sign.by}</Who> : <Who kind="wait" />}</span>
          <span>{sign ? <>{sign.at}에 승인했습니다.</> : <>검수자의 승인을 기다립니다.</>}</span>
        </li>
      </ol>

      <div className="n-draft">
        <div>
          <span className="n-specimen-k">고른 말</span>
          {d.meme ? (
            <>
              <p className="n-specimen" lang={d.meme.lang}>
                <Link href={`/lab/n-redesign/term/${d.meme.id}`}>{d.meme.word}</Link>
              </p>
              <p className="n-gloss">{d.meme.gloss}</p>
            </>
          ) : (
            <>
              <p className="n-specimen" data-none="true">밈 없이 씀</p>
              <p className="n-thin">{d.thin}</p>
            </>
          )}
          {d.picks.length > 0 && (
            <div className="n-sub">
              <h3>고른 이유 <Who kind="rule" /></h3>
              <ul className="n-facts">
                {d.picks.map((p) => <li key={p.rule}><span>{p.rule}</span><span>{p.effect}</span></li>)}
              </ul>
            </div>
          )}
          <div className="n-sub">
            <h3>뺀 말 <Who kind="rule" /></h3>
            <ul className="n-out">
              {d.excluded.map((e) => (
                <li key={e.word}>
                  <span className="n-out-w">
                    {e.id ? <Link className="n-link" href={`/lab/n-redesign/term/${e.id}`} lang={e.lang}>{e.word}</Link> : <span lang={e.lang}>{e.word}</span>}
                    <span className={e.kind === "avoid" || e.kind === "caution" ? "n-flag" : "n-meta"} data-tone={e.kind === "avoid" ? "avoid" : e.kind === "caution" ? "caution" : undefined}>
                      {{ avoid: "쓰지 않음", caution: "조심해서", fading: "식는 중", mismatch: "제품과 안 맞음", unknown: "근거 부족", none: "" }[e.kind]}
                    </span>
                  </span>
                  <span className="n-why">{e.why}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div>
          <ul className="n-copies" aria-label={`${m.name} 카피`}>
            {d.copies.map((c, i) => <CopyRow key={i} c={c} n={c.platform === "X" ? ++x : ++ig} d={d} signed={!!sign} onCopy={(t) => copy(t, "카피를")} />)}
          </ul>
          {d.script && (
            <details className="n-more">
              <summary>{d.script.seconds}초 영상 대본 <span className="n-meta">({d.script.scenes.length}장면)</span></summary>
              <table className="n-scenes">
                <thead><tr><th scope="col">시간</th><th scope="col">화면</th><th scope="col">자막</th></tr></thead>
                <tbody>
                  {d.script.scenes.map((s) => <tr key={s.t}><td className="n-num">{s.t}</td><td>{s.visual}</td><td lang={d.lang}>{s.caption}</td></tr>)}
                </tbody>
              </table>
            </details>
          )}
          {d.thumb && (
            <details className="n-more">
              <summary>썸네일 계획</summary>
              <p style={{ margin: "0 0 14px", fontSize: 14 }}><span lang={d.lang}><b>{d.thumb.headline}</b></span>. {d.thumb.layout}.</p>
            </details>
          )}
        </div>

        <div className="n-poster-col">
          <figure style={{ margin: 0 }}>
            <div className="n-poster" role="img" aria-label={`4:5 포스터 배치. 문구: ${d.poster.headline}`}>
              <div className="n-poster-img">제품 사진 자리<br />이미지 만들기는 꺼 두었습니다.<br />켜도 글자와 사람은 넣지 않습니다.</div>
              <div className="n-poster-copy" lang={d.lang}><b>{d.poster.headline}</b><span>{d.poster.sub}</span></div>
            </div>
            <figcaption className="n-poster-cap">포스터 4:5. 문구는 확인을 마친 카피를 화면이 얹습니다.</figcaption>
          </figure>

          <div className="n-approve">
            {sign ? (
              <>
                <div className="n-signed" data-fresh={sign.fresh}><Who kind="human">{sign.by} 승인</Who><span>{sign.at}</span></div>
                <div className="n-btns">
                  <button type="button" className="n-btn" data-size="s" onClick={() => copy(d.copies.map((c) => `[${c.platform}] ${c.text}`).join("\n\n"), `${m.name} 카피 ${d.copies.length}개를`)}>카피 모두 복사</button>
                  <button type="button" className="n-btn" data-kind="line" data-size="s" onClick={() => copy(`https://trend-interpreter.app/share/${d.market.toLowerCase()}-20261006`, "공유 링크를")}>공유 링크 복사</button>
                  <button type="button" className="n-btn" data-kind="quiet" data-size="s" onClick={onUnsign}>승인 취소</button>
                </div>
              </>
            ) : (
              <>
                <p>{flagged ? `표시된 카피 ${flagged}개를 읽고 판단하세요. ` : ""}승인하면 이 시장의 카피를 복사하고 공유할 수 있습니다.</p>
                <div className="n-btns">
                  <button type="button" className="n-btn" onClick={onSign}>{m.name} 초안 승인</button>
                  <button type="button" className="n-btn" data-kind="line">다시 쓰기</button>
                </div>
              </>
            )}
            <p className="n-toast" role="status">{toast}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function DraftsBoard() {
  const [signs, setSigns] = useState<Record<string, Sign | undefined>>(() =>
    Object.fromEntries(DRAFTS.filter((d) => d.approval.state === "approved").map((d) => [d.market, { by: d.approval.by!, at: d.approval.at! }])));
  const done = DRAFTS.filter((d) => signs[d.market]).length;

  return (
    <>
      <div className="n-tally">
        <nav aria-label="시장으로 가기">
          {DRAFTS.map((d) => (
            <a key={d.market} href={`#m-${d.market}`}>
              <b>{market(d.market).name}</b>
              <span className="n-state" data-on={!!signs[d.market]}>{signs[d.market] ? "승인됨" : "검토 대기"}</span>
            </a>
          ))}
        </nav>
        <span className="n-meta n-num" aria-live="polite">{DRAFTS.length}개 시장 중 {done}개 승인</span>
      </div>
      {DRAFTS.map((d) => (
        <MarketDraft key={d.market} d={d} sign={signs[d.market]}
          onSign={() => setSigns((s) => ({ ...s, [d.market]: { by: ME, at: now(), fresh: true } }))}
          onUnsign={() => setSigns((s) => ({ ...s, [d.market]: undefined }))} />
      ))}
    </>
  );
}
