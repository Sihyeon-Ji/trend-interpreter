import Link from "next/link";
import { day, SPREAD, type Word } from "@/lib/lab/n-redesign/data";
import { RiskText, Spark, StageMark } from "./bits";

export function WordTable({ words, caption }: { words: Word[]; caption: string }) {
  return (
    <table className="n-table">
      <caption className="n-sr">{caption}</caption>
      <colgroup>
        <col style={{ width: "32%" }} /><col style={{ width: "13%" }} /><col style={{ width: "10%" }} /><col style={{ width: "17%" }} />
        <col style={{ width: "9%" }} /><col style={{ width: "11%" }} /><col style={{ width: "8%" }} />
      </colgroup>
      <thead>
        <tr>
          <th scope="col">말</th><th scope="col">단계</th><th scope="col">퍼진 정도</th><th scope="col">브랜드 리스크</th>
          <th scope="col" className="n-r">4주 언급</th><th scope="col" style={{ paddingLeft: 16 }}>12주</th><th scope="col">마지막 쓰임</th>
        </tr>
      </thead>
      <tbody>
        {words.map((w) => (
          <tr key={w.id}>
            <td>
              <span className="n-tw" lang={w.lang}>{w.detail ? <Link href={`/lab/n-redesign/term/${w.id}`}>{w.word}</Link> : w.word}</span>
              <span className="n-tg">{w.gloss}</span>
            </td>
            <td data-label="단계"><StageMark stage={w.stage} /></td>
            <td data-label="퍼진 정도">{SPREAD[w.spread]}</td>
            <td data-label="리스크"><span><RiskText risk={w.risk} />{w.riskWhy && <span className="n-tg">{w.riskWhy}</span>}</span></td>
            <td data-label="4주 언급" className="n-r">{w.mentions.toLocaleString("ko-KR")}</td>
            <td data-label="12주" className="n-sparkcell"><Spark values={w.spark} /></td>
            <td data-label="마지막" className="n-num">{day(w.lastUsed)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
