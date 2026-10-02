/* 틀의 찾기 칸이 쓰는 색인 — 확인된 밈의 이름·다른 표기·뜻 한 줄만(사전 전체 2.7MB 대신 수십 KB). 칸을 처음 쓸 때 한 번 받는다. */

export interface SearchHit { id: string; name: string; lang: string; aliases: string[]; gloss: string; risk: string | null }

/** 이름·다른 표기·뜻에 그대로 들어 있는 것만, 이름이 그 말로 시작하는 것부터 */
export function searchHits(index: SearchHit[], q: string, max = 8): SearchHit[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return [];
  const score = (h: SearchHit) => {
    const name = h.name.toLowerCase();
    if (name === needle) return 0;
    if (name.startsWith(needle)) return 1;
    if (name.includes(needle)) return 2;
    if (h.aliases.some((a) => a.toLowerCase().includes(needle))) return 3;
    if (h.gloss.toLowerCase().includes(needle)) return 4;
    return -1;
  };
  return index.map((h) => ({ h, s: score(h) })).filter((x) => x.s >= 0).sort((a, b) => a.s - b.s || a.h.name.length - b.h.name.length).slice(0, max).map((x) => x.h);
}
