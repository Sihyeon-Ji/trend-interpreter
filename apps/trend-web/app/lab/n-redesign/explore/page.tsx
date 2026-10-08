import type { Metadata } from "next";
import Link from "next/link";
import { WordTable } from "@/components/lab/n-redesign/word-table";
import { MARKETS, market, wordsIn, type Word } from "@/lib/lab/n-redesign/data";

/* 둘러보기 — 시장 하나씩. 낱말 크기는 그 시장 안에서의 4주 언급 순위(다섯 단계), 나라끼리 견주지 않는다. 주소: ?m=KR */
export const metadata: Metadata = { title: "둘러보기" };

const FILLED = ["KR", "JP", "TH", "ID"];
const using = (w: Word) => !["declining", "dormant"].includes(w.stage) && (w.risk === "none" || w.risk === "unknown");
const fading = (w: Word) => ["declining", "dormant"].includes(w.stage) && w.risk !== "avoid" && w.risk !== "caution";
const careful = (w: Word) => w.risk === "caution" || w.risk === "avoid";

/** 그 시장 안의 순위로 1–5 단계 크기 */
function sizes(words: Word[]): Map<string, number> {
  const sorted = [...words].sort((a, b) => b.mentions - a.mentions);
  const n = sorted.length;
  return new Map(sorted.map((w, i) => [w.id, n <= 1 ? 4 : 5 - Math.min(4, Math.floor((i / n) * 5))]));
}

export default async function ExplorePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const raw = (await searchParams).m;
  const code = MARKETS.some((m) => m.code === raw) ? String(raw) : "KR";
  const mk = market(code);
  const words = wordsIn(code);
  const size = sizes(words);
  const field = [...words].sort((a, b) => a.word.localeCompare(b.word, mk.lang));
  const lists = [
    { id: "using", title: "쓰이는 중", note: "지금 써도 되는 말", empty: "지금 써도 되는 말이 없습니다", rows: words.filter(using) },
    { id: "fading", title: "식는 중", note: "쓰임이 줄고 있는 말. 새 캠페인에는 낡아 보일 수 있습니다", empty: "식고 있는 말이 없습니다", rows: words.filter(fading) },
    { id: "careful", title: "조심할 말", note: "쓰지 않거나 조심해서 쓸 말, 이유와 함께", empty: "조심할 말로 판정된 것이 없습니다", rows: words.filter(careful) },
  ];
  const thin = mk.words < 50;

  return (
    <div className="n-wrap">
      <div className="n-head" style={{ paddingBottom: 20 }}>
        <h1 className="n-h1">지금 쓰이는 말</h1>
        <p className="n-lead">나라마다 사전에서 확인된 말만 보여 줍니다. 근거 문서가 없는 말은 싣지 않아서, 나라마다 수가 다릅니다.</p>
      </div>

      <nav className="n-mtabs" aria-label="시장">
        {MARKETS.map((m) => (
          <Link key={m.code} href={`/lab/n-redesign/explore?m=${m.code}`} aria-current={m.code === code ? "page" : undefined}>
            <b>{m.name}</b><span>{m.words.toLocaleString("ko-KR")}개</span>
          </Link>
        ))}
      </nav>

      {!FILLED.includes(code) ? (
        <div className="n-ledger">
          <div className="n-row" style={{ borderTop: 0 }}>
            <div className="n-row-label">{mk.name}</div>
            <div>
              <p className="n-prose">{mk.name}에서 확인된 말 {mk.words}개는 이 시안의 예시 데이터에 넣지 않았습니다.</p>
              <p className="n-prose n-meta">예시가 있는 시장: {FILLED.map((c, i) => <span key={c}>{i ? ", " : ""}<Link className="n-link" href={`/lab/n-redesign/explore?m=${c}`}>{market(c).name}</Link></span>)}</p>
            </div>
          </div>
        </div>
      ) : (
        <section aria-labelledby="n-field-h">
          <h2 className="n-sr" id="n-field-h">{mk.name}에서 쓰이는 말, 많이 쓰일수록 크게</h2>
          <p className="n-field-words">
            {field.map((w) => {
              const others = w.markets.filter((c) => c !== code).length;
              return (
                <span key={w.id} className="n-fw" data-s={size.get(w.id)} data-r={w.risk} lang={w.lang}>
                  {w.detail ? <Link href={`/lab/n-redesign/term/${w.id}`}>{w.word}</Link> : w.word}
                  {w.risk === "avoid" && <span className="n-sr">(쓰지 않음)</span>}
                  {w.risk === "caution" && <span className="n-sr">(조심해서)</span>}
                  {others > 0 && <sup aria-label={`다른 ${others}개 나라에서도 씀`}>+{others}</sup>}
                </span>
              );
            })}
          </p>
          {thin && (
            <p className="n-thin" style={{ margin: "0 0 28px" }}>
              {mk.name}은 확인된 말이 {mk.words}개입니다. 근거 문서가 있는 말만 싣기 때문입니다. 새 말은 위키 문서가 생기거나 검수자가 승인하면 들어옵니다.
            </p>
          )}
          <div className="n-strip">
            <dl className="n-stats" aria-label={`${mk.name}, 지난 4주`}>
              <div><dt>확인된 말</dt><dd>{mk.words.toLocaleString("ko-KR")}</dd></div>
              <div><dt>예시로 보는 말</dt><dd>{words.length}</dd></div>
              {lists.map((l) => <div key={l.id}><dt>{l.title}</dt><dd>{l.rows.length}</dd></div>)}
            </dl>
            <ul className="n-keys" aria-label="읽는 법">
              <li><span className="k-size">크기</span><span>{mk.name} 안에서 4주 언급이 많은 순. 나라끼리 견주지 않음</span></li>
              <li><span className="k-share">+2</span><span>다른 나라 2곳에서도 씀</span></li>
              <li><span className="k-caution">밑줄</span><span>조심해서 쓸 말</span></li>
              <li><span className="k-avoid">취소선</span><span>쓰지 않는 말</span></li>
            </ul>
          </div>
        </section>
      )}

      {FILLED.includes(code) && lists.map((l) => (
        <section key={l.id} className="n-list" aria-labelledby={`l-${l.id}`}>
          <div className="n-list-head">
            <h2 className="n-h2" id={`l-${l.id}`}>{l.title} <span className="n-num" style={{ fontWeight: 400, color: "var(--n-ink-3)" }}>{l.rows.length}</span></h2>
            <span className="n-meta">{l.note}</span>
          </div>
          {l.rows.length ? <WordTable words={l.rows} caption={`${mk.name}, ${l.title}`} /> : <p className="n-empty">{mk.name}에는 {l.empty}.</p>}
        </section>
      ))}
    </div>
  );
}
