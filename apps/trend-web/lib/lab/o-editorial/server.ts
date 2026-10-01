/* 시안 '에디토리얼형' — 서버에서만 쓰는 글 다듬기: 뜻 첫 줄(lede)과 기사의 출처 목록.
   출처는 참고 위키·기사·영상뿐(데이터 방침 09-29, visibleSource). 같은 문서·같은 기사(여러 포털에 실린 것)는 한 번만 싣고,
   제목 앞에 되풀이된 출처 이름('네이버 뉴스 · ', 'Wikipedia: ')을 뗀다. 네이버 뉴스 검색으로 들어온 기사는
   출처를 '네이버 뉴스' 가 아니라 실제 언론사 주소로 적는다(주소가 그 언론사다). */
import { headlineFor } from "@/lib/explain";
import type { Locale } from "@/lib/i18n";
import { scriptLang } from "@/lib/lang";
import { cleanSource } from "@/lib/sources";
import type { Evidence, MeaningText } from "@/lib/types";
import { tidyGloss, visibleSource } from "./index";

/** 뜻 첫 줄 — 줄임말 풀이가 동음이의 문서 제목처럼 망가진 것이면('Point of view (disambiguation) — …') 뜻만 쓴다. 새 글을 짓지 않는다. */
export function ledeFor(tx: MeaningText, l: Locale): string {
  const ex = (tx.expansion ?? "").trim();
  const broken = !ex || /disambiguation|동음이의|曖昧さ回避/i.test(ex) || ex === tx.definition.trim();
  return tidyGloss(broken ? tx.definition : headlineFor(tx, l));
}

export interface SourceItem {
  id: string;
  group: "reference" | "report";   // 참고 위키 / 기사·영상
  named: boolean;                  // 참고 문서의 제목(또는 문서 주소)이 이 밈의 이름이다
  source: string;                  // "위키백과", "cnet.com 기사"
  title: string;
  titleLang?: string;
  url: string;
  date: string;
}

const REF_NAME: [RegExp, Record<Locale, string>][] = [
  [/(^|\.)wiktionary\.org$/, { ko: "위키낱말사전", en: "Wiktionary" }],
  [/^ko\.wikipedia\.org$/, { ko: "위키백과", en: "Korean Wikipedia" }],
  [/^en\.wikipedia\.org$/, { ko: "영어 위키백과", en: "Wikipedia" }],
  [/^ja\.wikipedia\.org$/, { ko: "일본어 위키백과", en: "Japanese Wikipedia" }],
  [/^zh\.wikipedia\.org$/, { ko: "중국어 위키백과", en: "Chinese Wikipedia" }],
  [/^th\.wikipedia\.org$/, { ko: "태국어 위키백과", en: "Thai Wikipedia" }],
  [/(^|\.)wikipedia\.org$/, { ko: "위키백과", en: "Wikipedia" }],
  [/(^|\.)namu\.wiki$/, { ko: "나무위키", en: "Namuwiki" }],
  [/(^|\.)knowyourmeme\.com$/, { ko: "Know Your Meme", en: "Know Your Meme" }],
  [/(^|\.)pixiv\.net$/, { ko: "pixiv 백과사전", en: "pixiv Encyclopedia" }],
  [/(^|\.)nicovideo\.jp$/, { ko: "니코니코 대백과", en: "Niconico Pedia" }],
];

const hostOf = (url: string) => { try { return new URL(url).hostname.toLowerCase(); } catch { return ""; } };
/** 주소 비교용 — 프로토콜·www·m·끝 빗금을 떼고, 위키 문서 이름의 공백·밑줄 차이를 없앤다 */
const urlKey = (url: string) => {
  try {
    const u = new URL(url);
    return `${u.hostname.replace(/^(www|m)\./, "")}${decodeURIComponent(u.pathname).replace(/[\s_]+/g, "_").replace(/\/$/, "")}${u.search}`.toLowerCase();
  } catch { return url; }
};
const titleKey = (t: string) => t.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");
/** 위키 문서 주소의 문서 이름('/wiki/Skibidi_Toilet' → 'Skibidi Toilet') */
const pageName = (url: string) => { try { return decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).at(-1) ?? ""); } catch { return ""; } };
/** 제목 앞에 되풀이된 출처 이름 */
const LEADING_SOURCE = /^(네이버 뉴스|Naver News|네이버 블로그|위키백과|Wikipedia|Wiktionary|나무위키)\s*[·:：|-]\s*/i;

function isReference(e: Evidence) {
  return e.kind === "wiki" || e.kind === "web";   // visibleSource 가 web 은 참고 위키 주소만 남긴다
}

function referenceName(l: Locale, e: Evidence): string {
  const host = hostOf(e.url);
  for (const [re, name] of REF_NAME) if (re.test(host)) return name[l];
  return host.replace(/^www\./, "");
}

/** 구글 뉴스가 '기사' 로 넘긴 유튜브 영상 — 출처 이름을 영상 사이트로, 종류를 영상으로 적는다 */
const VIDEO_SITE: [RegExp, string][] = [[/^(youtube|youtu\.be|youtube\.com)$/i, "YouTube"], [/^(tiktok|tiktok\.com)$/i, "TikTok"], [/^(instagram|instagram\.com)$/i, "Instagram"]];
function videoSite(e: Evidence): string | null {
  const dom = (e.source_domain ?? "").trim();
  for (const [re, name] of VIDEO_SITE) if (re.test(dom)) return name;
  return e.kind === "short" ? dom.replace(/^www\./, "") : null;
}

/** naver:news 는 네이버 뉴스 검색 API 로 받은 기사 — 주소의 언론사 도메인을 적는다 */
function publisher(e: Evidence, fallback: string): string {
  if (e.source_domain !== "naver:news") return fallback;
  const host = hostOf(e.url).replace(/^(www|m|news|n|mobile)\./, "");
  return host || fallback;
}

/** 출처 목록. names = [표제어, ...다른 표기]. 순서: 참고 문서(이름이 제목인 것 먼저) → 기사·영상(최근 먼저).
 *  이름이 제목에 없는 위키 문서는 그 말이 본문 어딘가에 나올 뿐일 수 있어 참고 문서 가운데 뒤로 둔다 — 빼지는 않는다. */
export function sourceList(evidences: Evidence[], names: string[], l: Locale): SourceItem[] {
  const noun = l === "ko" ? { news: "기사", short: "영상" } : { news: "article", short: "video" };
  const keys = names.map(titleKey).filter((k) => k.length > 0);
  const rows: { item: SourceItem; rank: number }[] = [];
  const seenUrl = new Set<string>();
  const seenTitle = new Set<string>();
  // 같은 주소가 위키 수집(wiki)과 검색(web)으로 두 번 들어오면 위키 수집 쪽을 남긴다
  const ordered = evidences.filter(visibleSource).sort((a, b) => Number(b.kind === "wiki") - Number(a.kind === "wiki") || b.observed_at.localeCompare(a.observed_at));
  for (const e of ordered) {
    const clean = cleanSource(e, names[0] ?? "", l);
    const title = clean.title.replace(LEADING_SOURCE, "").trim() || clean.title;
    const ref = isReference(e);
    const uk = urlKey(e.url);
    const tk = `${ref ? "r" : "n"}:${titleKey(title)}`;
    if (seenUrl.has(uk) || (tk.length > 4 && seenTitle.has(tk))) continue;
    seenUrl.add(uk);
    seenTitle.add(tk);
    const page = titleKey(pageName(e.url));
    const named = ref && keys.some((k) => titleKey(title).includes(k) || (page.length > 0 && page.includes(k)));
    const base = clean.source.replace(/\s(기사|영상|문서|웹 문서|article|video|web page)$/, "");
    const video = ref ? null : videoSite(e);
    rows.push({
      rank: named ? 0 : ref ? 1 : 2,
      item: {
        id: e.evidence_id,
        group: ref ? "reference" : "report",
        named,
        source: ref ? referenceName(l, e) : video ? `${video} ${noun.short}` : `${publisher(e, base)} ${noun.news}`,
        title,
        titleLang: scriptLang(title),
        url: e.url,
        date: e.observed_at,
      },
    });
  }
  return rows.sort((a, b) => a.rank - b.rank || b.item.date.localeCompare(a.item.date)).map((r) => r.item);
}

/** 유래 밑에 붙이는 근거 둘 — 이 밈의 참고 문서, 없으면 다른 참고 문서, 그것도 없으면 가장 먼저 나온 기사 */
export function originSources(list: SourceItem[]): SourceItem[] {
  const named = list.filter((s) => s.named);
  if (named.length) return named.slice(0, 2);
  const refs = list.filter((s) => s.group === "reference");
  if (refs.length) return refs.slice(0, 2);
  return list.filter((s) => s.group === "report").sort((a, b) => a.date.localeCompare(b.date)).slice(0, 2);
}
