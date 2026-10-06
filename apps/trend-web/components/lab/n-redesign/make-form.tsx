"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { BRIEF, CATEGORIES, MARKETS, TONES } from "@/lib/lab/n-redesign/data";

const MAX = 3;
const DEEPEST = Math.max(...MARKETS.map((m) => m.words));

export function MakeForm() {
  const router = useRouter();
  const [photo, setPhoto] = useState<string | null>(null);
  const [pitch, setPitch] = useState(`${BRIEF.product}. ${BRIEF.pitch}`);
  const [picked, setPicked] = useState<string[]>(BRIEF.markets);
  const [cat, setCat] = useState<string>("auto");
  const [tone, setTone] = useState<string>(BRIEF.tone);

  const full = picked.length >= MAX;
  const toggle = (code: string) =>
    setPicked((p) => (p.includes(code) ? p.filter((c) => c !== code) : p.length < MAX ? [...p, code] : p));
  const ready = picked.length > 0 && (pitch.trim().length > 0 || !!photo);

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (ready) router.push("/lab/n-redesign/drafts"); }} aria-describedby="n-make-lead">
      <div className="n-row">
        <div className="n-row-label">제품<small>사진이나 한 줄 설명, 둘 중 하나면 됩니다</small></div>
        <div className="n-product">
          <label className="n-drop">
            <input type="file" accept="image/*" aria-label="제품 사진 올리기"
              onChange={(e) => setPhoto(e.target.files?.[0]?.name ?? null)} />
            <span>{photo ? <><strong>올렸습니다</strong>{photo}</> : <><strong>사진 올리기</strong>끌어다 놓거나 눌러서 고르기</>}</span>
          </label>
          <div className="n-field">
            <label htmlFor="n-pitch">한 줄 설명</label>
            <textarea id="n-pitch" className="n-input" rows={4} maxLength={200} value={pitch} onChange={(e) => setPitch(e.target.value)} />
            <p className="n-hint">무엇을 파는지, 무엇이 다른지만 적어 주세요. 사진은 저장하지 않습니다.</p>
          </div>
        </div>
      </div>

      <div className="n-row">
        <div className="n-row-label" id="n-mk-label">시장<small>최대 3곳. 숫자는 그 나라 사전에서 확인된 말의 수</small></div>
        <div>
          <div className="n-markets" role="group" aria-labelledby="n-mk-label">
            {MARKETS.map((m) => {
              const on = picked.includes(m.code);
              return (
                <button key={m.code} type="button" className="n-mkt" aria-pressed={on} disabled={!on && full} onClick={() => toggle(m.code)}>
                  <b>{m.name}</b>
                  <span className="n-meta">{m.en}</span>
                  <span className="n-wc">확인된 말 {m.words.toLocaleString("ko-KR")}</span>
                  <span className="n-depth" aria-hidden="true"><i style={{ width: `${(m.words / DEEPEST) * 100}%` }} /></span>
                </button>
              );
            })}
          </div>
          <p className="n-hint" style={{ marginTop: 12 }} aria-live="polite">
            {full ? "3곳을 골랐습니다. 바꾸려면 고른 시장을 한 번 더 눌러 빼세요." : `${picked.length}곳을 골랐습니다.`}
            {" "}확인된 말이 적은 시장은 밈 없이 쓴 초안이 나올 수 있습니다.
          </p>
        </div>
      </div>

      <div className="n-row">
        <div className="n-row-label" id="n-cat-label">분야<small>모르면 자동으로 두세요</small></div>
        <div className="n-choices" role="radiogroup" aria-labelledby="n-cat-label">
          {["auto", ...CATEGORIES].map((c) => (
            <button key={c} type="button" role="radio" aria-checked={cat === c} className="n-choice" onClick={() => setCat(c)}>
              {c === "auto" ? "자동으로" : c}
            </button>
          ))}
        </div>
      </div>

      <div className="n-row">
        <div className="n-row-label" id="n-tone-label">말투</div>
        <div className="n-tones" role="radiogroup" aria-labelledby="n-tone-label">
          {TONES.map((t) => (
            <button key={t.id} type="button" role="radio" aria-checked={tone === t.id} className="n-tone" onClick={() => setTone(t.id)}>
              <b>{t.name}</b><span>{t.hint}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="n-submit">
        <button type="submit" className="n-btn" disabled={!ready}>시장별 초안 만들기</button>
        <span className="n-hint">
          {ready ? `${picked.length}개 시장, 시장마다 카피 4개와 포스터 배치. 1분쯤 걸립니다.` : picked.length ? "제품 사진이나 설명을 넣어 주세요." : "시장을 하나 이상 고르세요."}
        </span>
      </div>
    </form>
  );
}
