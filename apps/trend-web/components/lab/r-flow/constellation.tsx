/* 이어진 밈 그림 — 가운데 이 밈, 아래 반원에 이어진 밈(관계 낱말을 선 위에), 위에 출처(작품·인물·플랫폼)와 같은 출처의 밈.
   자리는 서버에서 정해 그린다(움직이지 않는다). 그림은 마우스용이고 키보드·화면 읽기는 아래 목록을 쓴다. */
import Link from "next/link";
import { langTag } from "@/lib/lang";

interface Node { id?: string; name: string; lang?: string; rel?: string; kind: "self" | "rel" | "cand" | "source" | "same"; x: number; y: number; w: number }

const W = 600;
const H_MIN = 230;

/** 글자 폭 어림 — 한·중·일 글자는 넓게, 라틴은 좁게 */
function width(s: string): number {
  let w = 0;
  for (const ch of s) w += /[ᄀ-ᇿ぀-ヿ㐀-鿿가-힯＀-￯]/.test(ch) ? 13.2 : 7.4;
  return Math.min(190, Math.max(36, w + 22));
}
const clip = (s: string, n = 16) => ([...s].length > n ? `${[...s].slice(0, n - 1).join("")}…` : s);

export function Constellation({ self, related, candidates, source, same, base }: {
  self: { name: string; lang: string };
  related: { id: string; name: string; lang: string; rel: string }[];
  candidates: { name: string; rel: string }[];
  source: { name: string; type: string } | null;
  same: { id: string; name: string; lang: string }[];
  base: string;
}) {
  const ring = [...related.slice(0, 7).map((r) => ({ ...r, kind: "rel" as const })), ...candidates.slice(0, Math.max(0, 8 - Math.min(7, related.length))).map((c) => ({ ...c, id: undefined, lang: undefined, kind: "cand" as const }))];
  const top = source ? 54 : 0;
  const cx = W / 2;
  const cy = source ? 128 : 92;
  const n = ring.length;
  const nodes: Node[] = [];
  nodes.push({ name: self.name, lang: self.lang, kind: "self", x: cx, y: cy, w: width(clip(self.name, 18)) });
  ring.forEach((r, i) => {
    // 아래 반원에 왼쪽에서 오른쪽으로. 하나면 바로 아래
    const a = n === 1 ? Math.PI / 2 : Math.PI - ((i + 0.5) * Math.PI) / n;
    nodes.push({ id: r.id, name: r.name, lang: r.lang, rel: r.rel, kind: r.kind, x: cx + Math.cos(a) * 214, y: cy + 26 + Math.sin(a) * 76, w: width(clip(r.name)) });
  });
  if (source) {
    nodes.push({ name: source.name, rel: source.type, kind: "source", x: cx, y: top - 26, w: width(clip(source.name, 18)) });
    same.slice(0, 4).forEach((s, i) => {
      const side = i % 2 === 0 ? -1 : 1;
      const step = Math.floor(i / 2);
      nodes.push({ id: s.id, name: s.name, lang: s.lang, kind: "same", x: cx + side * (170 + step * 0), y: top - 26 + step * 40, w: width(clip(s.name)) });
    });
  }
  const lowest = Math.max(...nodes.map((d) => d.y));
  const H = Math.max(H_MIN, lowest + 34);
  const selfNode = nodes[0];
  const src = nodes.find((d) => d.kind === "source");

  return (
    <svg className="rf-graph" viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
      {nodes.filter((d) => d.kind === "rel" || d.kind === "cand").map((d) => (
        <g key={`e-${d.name}`}>
          <line data-k={d.kind} x1={selfNode.x} y1={selfNode.y} x2={d.x} y2={d.y} />
          {d.rel && <text className="rf-g-rel" x={(selfNode.x + d.x) / 2 + (d.x < selfNode.x ? -6 : 6)} y={(selfNode.y + d.y) / 2 - 3} textAnchor={d.x < selfNode.x - 4 ? "end" : d.x > selfNode.x + 4 ? "start" : "middle"}>{d.rel}</text>}
        </g>
      ))}
      {src && (
        <g>
          <line data-k="source" x1={selfNode.x} y1={selfNode.y} x2={src.x} y2={src.y} />
          {src.rel && <text className="rf-g-rel" x={src.x + 8} y={(selfNode.y + src.y) / 2 + 4}>{src.rel}</text>}
        </g>
      )}
      {src && nodes.filter((d) => d.kind === "same").map((d) => <line key={`s-${d.name}`} data-k="cand" x1={src.x} y1={src.y} x2={d.x} y2={d.y} />)}
      {nodes.map((d) => {
        const body = (
          <g className="rf-g-node" data-k={d.kind}>
            <rect x={d.x - d.w / 2} y={d.y - 14} width={d.w} height={28} rx={d.kind === "source" ? 14 : 7} />
            <text x={d.x} y={d.y + 4.5} textAnchor="middle" lang={langTag(d.lang)}>{clip(d.name, d.kind === "self" || d.kind === "source" ? 18 : 16)}</text>
          </g>
        );
        return d.id ? <Link key={`n-${d.kind}-${d.id}`} href={`${base}/term/${encodeURIComponent(d.id)}`} tabIndex={-1} scroll={false}>{body}</Link> : <g key={`n-${d.kind}-${d.name}`}>{body}</g>;
      })}
    </svg>
  );
}
