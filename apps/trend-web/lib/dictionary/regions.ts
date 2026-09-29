/* 사전 항목의 지역과 마지막 쓰임 — 대시보드(백엔드 pipeline/dashboard.py)와 같은 규칙을 한 곳에. 사전 색인·메시지 해석이 함께 쓴다. */
import { TARGET_REGIONS } from "../reader";
import type { TermRecord } from "../types";

const LANG_REGION: Record<string, string> = { ko: "KR", ja: "JP", id: "ID", th: "TH", vi: "VN", zh: "TW", tl: "PH", fil: "PH", ms: "MY" };
// 광동어에만 쓰는 글자가 들었거나 광동어 코드면 홍콩, 다른 중국어는 대만 (백엔드 config.home_region)
const CANTONESE = /[㗎咗嘅冇佢啲喺嘢嚟唔]/;
const homeRegion = (canonical: string, lang: string) => (["yue", "yu"].includes(lang) || CANTONESE.test(canonical) ? "HK" : LANG_REGION[lang]);
const SCRIPT: Record<string, RegExp> = { ko: /[가-힣]/, ja: /[぀-ヿ一-鿿]/, zh: /[一-鿿]/, th: /[฀-๿]/, vi: /[ăâđêôơưĂÂĐÊÔƠƯẠ-ỹ]/ };
const LATIN_LANGS = ["id", "tl", "fil", "ms"];
const LATIN_ONLY = /^[\x00-\x7fÀ-ɏḀ-ỿ\s]+$/;

/** 이 표현을 보여 줄 지역 — 대시보드와 같은 규칙(백엔드 pipeline/dashboard.term_regions). 뜻의 regions 만 보면
 *  쓰임(usage)에만 나라가 있는 표현이 빠져 '한국' 을 골라도 96개가 58개로 나왔다(2026-09-29 검토). */
export function termRegions(r: TermRecord): string[] {
  if (r.regions) return r.regions;   // API 는 백엔드가 정한 지역을 준다(그 나라 매체 수 규칙은 매체 기록이 있는 백엔드에서만)
  const known = new Set(r.usage.map((u) => u.segment.region).filter(Boolean));
  const regions = TARGET_REGIONS.filter((x) => known.has(x));
  const lang = r.term.lang ?? "ko";
  if (!known.size) {
    const home = homeRegion(r.term.canonical, lang);
    if (home && TARGET_REGIONS.includes(home) && (SCRIPT[home === "HK" ? "zh" : lang]?.test(r.term.canonical) || LATIN_LANGS.includes(lang))) regions.push(home);
    else if (LATIN_ONLY.test(r.term.canonical)) return ["GLOBAL"];
  }
  if (known.has("GLOBAL") || (!regions.length && known.size && lang === "en")) regions.push("GLOBAL");
  return regions;
}

const hasPath = (url: string) => { try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; } };

/** 마지막 쓰임 — 대시보드와 같게 실제로 쓰인 글(커뮤니티·기사·영상)의 가장 최근 날짜, 없으면 마지막으로 본 날. */
export function lastUsedOf(r: TermRecord): string | null {
  const used = r.evidences.filter((e) => ["community", "news", "short"].includes(e.kind) && hasPath(e.url)).map((e) => e.observed_at).sort();
  return used.at(-1) ?? r.term.last_seen ?? null;
}

