/* 지도 위 이동 경로 — 날짜를 대는 출처가 있는 나라끼리만 긋는다.

   예전에는 variants[0] 을 '처음 나온 곳'으로 그렸다. 그런데 실데이터에서는 그 순서가 관심도였고, 조사 단계가 관심도를
   균등하게 넣어서 사실상 나라 코드의 알파벳순이었다. 인기 순서가 이동 경로처럼 보였던 것이다.
   그래서 경로는 날짜가 확인된 나라가 둘 이상일 때만 만들고, 아니면 빈 배열이다 — 선을 긋지 않는다. */
import type { Topic, TopicVariant } from "./types";

/** 날짜가 확인된 나라를 날짜순으로. 둘 미만이거나 가장 이른 날이 겹치면 [] — 경로가 아니다.
 *  같은 날 여러 나라에서 처음 보도됐다면 어디서 시작했는지는 날짜로 가릴 수 없다. 정렬 순서가 출발점이 되게 두지 않는다
 *  (2026-09-26 실측: 무뎅은 태국·한국·일본·인도네시아 모두 같은 날 세 번째 언론사가 보도했다). */
export function pathOf(topic: Topic): TopicVariant[] {
  const dated = topic.variants.filter((v) => v.dated && v.since).sort((a, b) => a.since.localeCompare(b.since));
  if (dated.length < 2 || dated[0].since === dated[1].since) return [];
  return dated;
}

/** 날짜로 정해진 출발 나라. 정해지지 않으면 null. */
export function originOf(topic: Topic): string | null {
  return pathOf(topic)[0]?.region ?? null;
}

/** 화면에 늘어놓는 순서: 경로(날짜순) 다음에 날짜가 확인되지 않은 나라(관심도순). */
export function displayOrder(topic: Topic): TopicVariant[] {
  const path = pathOf(topic);
  const onPath = new Set(path.map((v) => v.region));
  const rest = topic.variants.filter((v) => !onPath.has(v.region)).sort((a, b) => b.heat - a.heat);
  return [...path, ...rest];
}
