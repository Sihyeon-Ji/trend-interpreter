/* 사전 항목 '출처' 표의 한 줄 — 수집기가 남긴 제목·발췌를 읽을 수 있게 다듬는다. 판정은 하지 않고 보이는 글만 고친다. */
import type { Locale } from "./i18n";
import { L, sep, sourceLabel, sourceName } from "./labels";
import type { Evidence } from "./types";

export interface SourceRow {
  id: string;
  date: string;          // 관측 시각 (ISO)
  source: string;        // "톱스타뉴스 기사", "나무위키 문서"
  title: string;
  url: string;
  excerpt: string;       // 제목에 없는 내용이 있을 때만
}

/* 출처 칸의 '무엇' — "톱스타뉴스 기사", "나무위키 문서". 커뮤니티 글은 화면에 오지 않지만(ADR 0003) 종류마다 이름을 둔다. */
const NOUN: Record<Locale, Record<Evidence["kind"], string>> = {
  ko: { short: "영상", news: "기사", datalab: "검색 통계", web: "웹 문서", community: "글", human: "검수 기록", wiki: "문서" },
  en: { short: "video", news: "article", datalab: "search stats", web: "web page", community: "post", human: "review note", wiki: "article" },
  ja: { short: "動画", news: "記事", datalab: "検索統計", web: "ページ", community: "投稿", human: "レビュー記録", wiki: "記事" },
};

const QUOTES = /^[\s"'“”‘’「」『』]+|[\s"'“”‘’「」『』]+$/g;
const norm = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");

/** 제목 끝의 " - 디시인사이드" 처럼 출처 이름을 되풀이한 꼬리를 뗀다. 출처 이름과 같을 때만. */
function stripSourceTail(title: string, names: string[]): string {
  const m = /\s[-–|]\s([^-–|]+)$/.exec(title);
  if (!m) return title;
  const tail = norm(m[1]);
  return names.some((n) => n && (norm(n) === tail || tail === norm(n.replace(/^www\./, "")))) ? title.slice(0, m.index).trim() : title;
}

/** 앞에 붙은 사이트 이름('나무위키: 제로투 회피', 'Wikipedia: 오시카츠')을 뗀다 — 출처 칸이 이미 화면 언어로 사이트를 말한다.
 *  일본어·영어 화면에 '나무위키:' 가 한국어로 남았다(10-13). 문서 제목과 라이선스 표시는 그대로 둔다 */
const SITE_HEAD = /^(나무위키|위키백과|위키낱말사전|Namuwiki|Wikipedia|Wiktionary|ナムウィキ|ウィキペディア)\s*:\s*/i;
export function stripSourceHead(title: string, names: string[] = []): string {
  const m = SITE_HEAD.exec(title);
  if (m) return title.slice(m[0].length).trim();
  const n = names.find((x) => x && title.toLowerCase().startsWith(`${x.toLowerCase()}:`));
  return n ? title.slice(n.length + 1).trim() : title;
}

/** 표제어가 보이는 자리를 가운데 두고 자른다 — 앞에서부터 자르면 정작 그 표현이 잘려 나간다(2026-09-16 검토). */
function around(text: string, term: string, width = 60): string {
  const at = text.toLowerCase().indexOf(term.toLowerCase());
  if (at < 0 || text.length <= width * 2) return text.length > width * 2 ? `${text.slice(0, width * 2)}…` : text;
  const from = Math.max(0, at - width);
  const to = Math.min(text.length, at + term.length + width);
  return `${from > 0 ? "…" : ""}${text.slice(from, to)}${to < text.length ? "…" : ""}`;
}

/** 출처 한 줄. 따옴표가 겹친 것을 풀고, 제목을 되풀이할 뿐인 발췌는 내지 않는다(제목 앞 30자만 비교하던 것을 전체 비교로). */
export function cleanSource(e: Evidence, term: string, locale: Locale): SourceRow {
  const names = [e.source_domain, sourceName("ko", e.source_domain), sourceName("en", e.source_domain), sourceName("ja", e.source_domain)];
  const title = stripSourceHead(stripSourceTail((e.title ?? "").trim(), names), names).replace(QUOTES, "") || e.url;
  let excerpt = (e.excerpt ?? "").trim().replace(QUOTES, "");
  const nt = norm(title), ne = norm(excerpt);
  if (!ne || nt.includes(ne)) excerpt = "";
  else if (nt && ne.includes(nt) && ne.length - nt.length < 15) excerpt = "";   // 제목에 몇 글자 붙은 것뿐이면 새 내용이 아니다
  return {
    id: e.evidence_id,
    date: e.observed_at,
    source: sourceLabel(locale, sourceName(locale, e.source_domain), NOUN[locale][e.kind]),
    title,
    url: e.url,
    excerpt: excerpt ? around(excerpt, term) : "",
  };
}

/** "기사 11건, 커뮤니티 12건" / "article 11, community 12" / "記事11件、コミュニティ12件" — 많은 순 */
export function kindCounts(evidences: Evidence[], locale: Locale): string {
  const counts = new Map<Evidence["kind"], number>();
  for (const e of evidences) counts.set(e.kind, (counts.get(e.kind) ?? 0) + 1);
  const label = L(locale).evidenceKind;
  return [...counts].sort((a, b) => b[1] - a[1]).map(([k, n]) => (locale === "ko" ? `${label[k]} ${n}건` : locale === "ja" ? `${label[k]}${n}件` : `${label[k]} ${n}`)).join(sep(locale));
}
