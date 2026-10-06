import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RiskText, Spark, StageMark, Who } from "@/components/lab/n-redesign/bits";
import { DETAILS, MARKETS, SPREAD, day, market, wordById } from "@/lib/lab/n-redesign/data";

/* 표제어 — 원문은 크게, 번역하지 않는다. 판정(단계·리스크)은 규칙, 설명은 모델이 쓰고 검수자가 승인. */
type Props = { params: Promise<{ id: string }> };

export function generateStaticParams() {
  return Object.keys(DETAILS).map((id) => ({ id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const w = wordById((await params).id);
  return { title: w?.word ?? "표제어" };
}

const KIND = { wiki: "위키", news: "뉴스", video: "영상" } as const;
const name = (code: string) => MARKETS.find((m) => m.code === code)?.name ?? (code === "US" ? "미국" : code);

export default async function TermPage({ params }: Props) {
  const { id } = await params;
  const w = wordById(id);
  const d = DETAILS[id];
  if (!w || !d) notFound();
  const home = w.markets[0];
  const current = d.versions.find((v) => !v.to);

  return (
    <div className="n-wrap">
      <div className="n-term-head">
        <p className="n-crumb">
          <Link href="/lab/n-redesign/explore">둘러보기</Link><span aria-hidden="true">/</span>
          <Link href={`/lab/n-redesign/explore?m=${home}`}>{market(home).name}</Link><span aria-hidden="true">/</span>
          <span lang={w.lang}>{w.word}</span>
        </p>
        <h1 className="n-term-word" lang={w.lang}>{w.word}</h1>
        {d.reading && <p className="n-term-read" lang={`${w.lang}-Latn`}>{d.reading}</p>}
        <p className="n-term-gloss">{w.gloss}</p>

        <dl className="n-vitals">
          <div><dt>단계</dt><dd><StageMark stage={w.stage} /></dd></div>
          <div><dt>퍼진 정도</dt><dd>{SPREAD[w.spread]}</dd></div>
          <div><dt>브랜드 리스크</dt><dd><RiskText risk={w.risk} /></dd></div>
          <div><dt>4주 언급</dt><dd><span className="n-big">{w.mentions.toLocaleString("ko-KR")}</span><Spark values={w.spark} w={120} h={26} /></dd></div>
          <div><dt>마지막 쓰임</dt><dd className="n-num">{day(w.lastUsed)}</dd></div>
        </dl>
      </div>

      <div className="n-ledger">
        <div>
          <div className="n-row" style={{ borderTop: 0 }}>
            <h2 className="n-row-label">뜻</h2>
            <div><p className="n-prose">{d.meaning}</p></div>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">유래</h2>
            <div><p className="n-prose">{d.origin}</p></div>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">뉘앙스</h2>
            <div><p className="n-prose">{d.nuance}</p></div>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">쓰는 법</h2>
            <div className="n-uses">
              <div><h3>이렇게 씁니다</h3><ul>{d.howTo.ok.map((t) => <li key={t} lang={w.lang}>{t}</li>)}</ul></div>
              <div><h3>이렇게는 쓰지 않습니다</h3><ul>{d.howTo.no.map((t) => <li key={t}>{t}</li>)}</ul></div>
            </div>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">브랜드 리스크<small>규칙이 정함</small></h2>
            <div>
              <p className="n-prose"><RiskText risk={w.risk} /></p>
              {d.riskReasons.length
                ? <ul className="n-facts" style={{ marginTop: 8 }}>{d.riskReasons.map((r, i) => <li key={r}><span className="n-num">이유 {i + 1}</span><span>{r}</span></li>)}</ul>
                : <p className="n-prose n-meta">기사·영상 근거에서 비하·선정·정치 맥락을 찾지 못했습니다. {day("2026-10-05")} 다시 확인.</p>}
            </div>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">나라마다<small>{d.countries.length}개 나라에서 씀</small></h2>
            <ul className="n-countries">
              {d.countries.map((c) => (
                <li key={c.code}>
                  <span className="n-meta">{name(c.code)}</span>
                  <div><span className="n-local" lang={c.lang}>{c.local}</span><p>{c.how}</p></div>
                </li>
              ))}
            </ul>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">출처<small>위키·뉴스·영상만 싣습니다</small></h2>
            <ul className="n-sources">
              {d.sources.map((s) => (
                <li key={s.title}>
                  <span className="n-date">{day(s.date)}<br /><span className="n-meta">{KIND[s.kind]}</span></span>
                  <div>
                    <a className="n-link" href={s.url} target="_blank" rel="noreferrer"><span lang={/[ぁ-ヿ]/.test(s.title) ? "ja" : undefined}>{s.title}</span></a>
                    <span className="n-meta">, {s.outlet}</span>
                    {s.quote && <blockquote>&ldquo;{s.quote}&rdquo;</blockquote>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="n-row">
            <h2 className="n-row-label">뜻 이력<small>지우지 않고 버전을 쌓습니다</small></h2>
            <ol className="n-versions" reversed>
              {d.versions.map((v) => (
                <li key={v.v} data-closed={!!v.to}>
                  <span className="n-num"><span className="n-vh">버전 {v.v}</span><br /><span className="n-meta">{day(v.from)}{v.to ? ` ~ ${day(v.to)}` : "부터"}</span></span>
                  <div>
                    <p>{v.text}</p>
                    {v.to ? <span className="n-meta">{v.by.replace("검수자 ", "")} 승인, {day(v.to)}에 다음 버전으로 바뀜</span> : <Who kind="human">{v.by.replace("검수자 ", "")} 승인, {day(v.from)}</Who>}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <aside className="n-rail" aria-labelledby="n-who-made">
          <h2 id="n-who-made">이 항목은 누가 정했나</h2>
          <ol className="n-steps" style={{ listStyle: "none" }}>
            <li><div><Who kind="rule" /><span>사전 등재. 나무위키·위키백과 같은 참고 문서에 표제어가 있어 통과.</span></div></li>
            <li><div><Who kind="rule" /><span>단계·퍼진 정도·리스크. 출처의 날짜와 언급 수로 매일 다시 계산.</span></div></li>
            <li><div><Who kind="model" /><span>뜻·유래·뉘앙스 초안. 출처 문장을 근거로 씀.</span></div></li>
            <li><div><Who kind="human" /><span>{current ? `${current.by.replace("검수자 ", "")}가 ${day(current.from)}에 지금 뜻을 승인.` : "승인 대기."}</span></div></li>
          </ol>
          <p className="n-meta" style={{ marginTop: 16 }}>커뮤니티 글은 쓰임을 재는 데만 쓰고 여기에 싣지 않습니다.</p>
        </aside>
      </div>
    </div>
  );
}
