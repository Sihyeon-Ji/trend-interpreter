/* 시안 f-report(트렌드 리포트형)의 자료 가공. 화면이 쓰는 값은 전부 여기서 계산한다 — 숫자를 지어내지 않고, 자료가 없으면 null.
   - 쓰임 추이·증감: 네이버 데이터랩 나이대별 검색 관심(GET /terms/{id}/generations)만 쓴다. 나이대마다 자기 최고점이 100 인 상대값이라
     표제어끼리 높이를 견줄 수 없다 → 순위 변동(▲2)은 만들지 않고, 같은 표제어 안에서 '최근 4주 대 그 전 4주' 증감만 낸다.
   - 근거: 커뮤니티 글(kind community)은 제목·인용·사이트 이름을 화면에 내지 않는다(2026-09-29 자료 방침). 보이는 출처는 참고 위키·기사·영상뿐. */
import type { Locale } from "@/lib/i18n";
import type { KeywordCard } from "@/lib/types";
import type { EvidenceBrief, GenerationCurve, UpdateItem } from "@/lib/trends/types";

export const GEN_ORDER = ["10s", "20s", "30s", "40s", "50s+"];
export const WINDOW_DAYS = 28;
export const SPARK_WEEKS = 26;

export interface Trend {
  pct: number | null;          // 최근 4주 평균 대 그 전 4주 평균, 정수 %. 자료가 8주 미만이면 null
  now: number | null;
  daily: number[];             // 나이대 평균, 날짜순
  smooth: number[];            // 7일 이동 평균 — 큰 곡선용(날 것은 톱니처럼 보였다)
  spark: number[];             // 주 평균, 최근 26주
  from: string;
  to: string;
  byGen: { generation: string; spark: number[]; peak: string | null }[];
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/** 7일 가운데 이동 평균 */
function smoothed(daily: number[], k = 7): number[] {
  const half = Math.floor(k / 2);
  return daily.map((_, i) => Math.round(mean(daily.slice(Math.max(0, i - half), Math.min(daily.length, i + half + 1))) * 10) / 10);
}

/** 끝에서부터 7일씩 묶은 주 평균, 오래된 주가 앞 */
function weekly(daily: number[], weeks = SPARK_WEEKS): number[] {
  const out: number[] = [];
  for (let end = daily.length; end > 0 && out.length < weeks; end -= 7) {
    out.push(mean(daily.slice(Math.max(0, end - 7), end)));
  }
  return out.reverse().map((v) => Math.round(v * 10) / 10);
}

/** 나이대 곡선 다섯을 하나로(날짜마다 있는 나이대의 평균)하고 증감을 센다. 점이 둘 미만이면 null. */
export function combineCurves(curves: GenerationCurve[]): Trend | null {
  const series = curves.filter((c) => Array.isArray(c.points) && c.points.length > 1);
  if (!series.length) return null;
  const byDate = new Map<string, number[]>();
  for (const c of series) for (const [d, v] of c.points) byDate.set(d, [...(byDate.get(d) ?? []), v]);
  const dates = [...byDate.keys()].sort();
  const daily = dates.map((d) => Math.round(mean(byDate.get(d)!) * 10) / 10);
  let pct: number | null = null;
  let now: number | null = null;
  if (daily.length >= WINDOW_DAYS * 2) {
    const a = mean(daily.slice(-WINDOW_DAYS));
    const b = mean(daily.slice(-WINDOW_DAYS * 2, -WINDOW_DAYS));
    now = Math.round(a * 10) / 10;
    pct = b > 0 ? Math.round(((a - b) / b) * 100) : null;
  }
  const byGen = series
    .slice()
    .sort((x, y) => GEN_ORDER.indexOf(x.generation) - GEN_ORDER.indexOf(y.generation))
    .map((c) => ({ generation: c.generation, spark: weekly(c.points.map((p) => p[1])), peak: c.peak_date ?? null }));
  return { pct, now, daily, smooth: smoothed(daily), spark: weekly(daily), from: dates[0], to: dates[dates.length - 1], byGen };
}

/** 유튜브 주소에서 영상 id — 없으면 null(수집된 영상 근거 다수가 'https://youtube.com/' 처럼 id 없이 온다). */
export function youtubeId(url: string | null | undefined): string | null {
  if (!url) return null;
  const m = url.match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}
export const thumbUrl = (id: string) => `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;

/** 참고 위키(나무위키·위키백과·위키낱말사전·Know Your Meme·pixiv 백과)만 'web' 근거 가운데 보인다. */
export const isReferenceDomain = (domain: string) => /(^|\.)(wikipedia\.org|wiktionary\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net)$/i.test(domain);

type Ev = { kind: string; source_domain: string; url: string };
/** 화면에 보여도 되는 근거: 위키·기사·영상, 그리고 참고 위키 도메인의 웹 문서. 커뮤니티·검색 통계·그 밖의 웹은 뺀다. 같은 주소는 하나만. */
export function visibleEvidence<T extends Ev>(evs: T[] | null | undefined): T[] {
  const seen = new Set<string>();
  return (evs ?? []).filter((e) => {
    const ok = e.kind === "wiki" || e.kind === "news" || e.kind === "short" || (e.kind === "web" && isReferenceDomain(e.source_domain));
    if (!ok || seen.has(e.url)) return false;
    seen.add(e.url);
    return true;
  });
}

/** 리스크 사유에서 인용문을 뗀다 — 규칙이 붙인 예문은 커뮤니티 글이 많다. 인용만 있는 줄은 버린다. */
export function cleanRiskReasons(reasons: string[] | null | undefined, locale: Locale): string[] {
  const out: string[] = [];
  for (const raw of reasons ?? []) {
    const r = raw.trim();
    if (!r || /^[“"]/.test(r)) continue;
    const cut = r.split(/\s+—\s+예:|:\s*[“"]/)[0].trim();
    if (!cut) continue;
    const text = locale === "en" ? englishRisk(cut) : cut;
    if (!out.includes(text)) out.push(text);
  }
  return out;
}

function englishRisk(ko: string): string {
  let m = ko.match(/위험 유형이 붙은 근거 (\d+)건/);
  if (m) return `${m[1]} sources carry a risk flag`;
  m = ko.match(/부정적으로 쓰인 근거가 (\d+)%/);
  if (m) return `Used negatively in ${m[1]}% of sources`;
  if (/뉴스에 오른 뒤 언급이 줄고/.test(ko)) return "Mentions fell after news coverage; it may look stale";
  m = ko.match(/분류된 근거 (\d+)건에 위험 신호가 없다/);
  if (m) return `No risk signal in ${m[1]} classified sources`;
  return ko;
}

const SOURCE: Record<Locale, Record<string, string>> = {
  ko: { "wikipedia.org": "위키백과", "ko.wikipedia.org": "위키백과", "en.wikipedia.org": "영어 위키백과", "ja.wikipedia.org": "일본어 위키백과", "zh.wikipedia.org": "중국어 위키백과",
        "id.wikipedia.org": "인도네시아어 위키백과", "en.wiktionary.org": "위키낱말사전", "namu.wiki": "나무위키", "knowyourmeme.com": "Know Your Meme", "dic.pixiv.net": "pixiv 백과", "youtube.com": "YouTube", "www.youtube.com": "YouTube" },
  en: { "wikipedia.org": "Wikipedia", "ko.wikipedia.org": "Korean Wikipedia", "en.wikipedia.org": "Wikipedia", "ja.wikipedia.org": "Japanese Wikipedia", "zh.wikipedia.org": "Chinese Wikipedia",
        "id.wikipedia.org": "Indonesian Wikipedia", "en.wiktionary.org": "Wiktionary", "namu.wiki": "Namuwiki", "knowyourmeme.com": "Know Your Meme", "dic.pixiv.net": "pixiv encyclopedia", "youtube.com": "YouTube", "www.youtube.com": "YouTube" },
};
export const sourceLabel = (locale: Locale, domain: string) => SOURCE[locale][domain] ?? domain;

export const fmtDay = (iso: string | null | undefined) => (iso ? iso.slice(0, 10).replace(/-/g, ".") : "");
export const fmtMonth = (iso: string | null | undefined) => (iso ? iso.slice(0, 7).replace("-", ".") : "");

/** 최근 며칠 안에 사전에 새로 오른 표제어 id — 목록의 '새로 올라옴' 표시 */
export function newlyVerified(items: UpdateItem[], days = 7, ref = Date.now()): Set<string> {
  const from = ref - days * 86_400_000;
  const s = new Set<string>();
  for (const i of items) if (i.kind === "verified" && i.term_id && Date.parse(i.at) >= from) s.add(i.term_id);
  return s;
}

/* ---- 화면 행 모델: 대시보드 카드 + 추이. 클라이언트로 내려가므로 필요한 것만. ---- */
export interface SourceRef { kind: string; domain: string; title: string; url: string; at: string }
export interface Row {
  id: string;
  name: string;
  lang: string;
  category: string;
  gloss: string;
  stage: string;                 // Lifecycle
  diffusion: string | null;
  risk: "none" | "caution" | "avoid" | null;
  riskReasons: string[];
  regions: string[];
  lastSeen: string | null;
  pct: number | null;
  spark: number[] | null;
  byGen: Trend["byGen"] | null;
  from: string | null;
  to: string | null;
  sources: SourceRef[];
  thumb: string | null;          // 유튜브 썸네일 — 영상 근거에 id 가 있을 때만
  video: string | null;
  isNew: boolean;
}

export function toRow(card: KeywordCard, trend: Trend | null, newIds: Set<string>, locale: Locale): Row {
  const visible = visibleEvidence<EvidenceBrief>(card.evidences);
  const short = visible.find((e) => e.kind === "short" && youtubeId(e.url));
  const vid = short ? youtubeId(short.url) : null;
  return {
    id: card.term_id,
    name: card.canonical,
    lang: card.lang,
    category: card.category,
    gloss: (locale === "en" ? card.gloss_en : card.gloss_ko) || card.gloss_ko || card.gloss_en || "",
    stage: card.lifecycle ?? "unknown",
    diffusion: card.diffusion ?? null,
    risk: card.risk_level ?? null,
    riskReasons: cleanRiskReasons(card.risk_reasons, locale),
    regions: card.regions ?? [],
    lastSeen: card.last_seen ?? null,
    pct: trend?.pct ?? null,
    spark: trend?.spark ?? null,
    byGen: trend?.byGen ?? null,
    from: trend?.from ?? null,
    to: trend?.to ?? null,
    sources: visible.slice(0, 4).map((e) => ({ kind: e.kind, domain: e.source_domain, title: e.title, url: e.url, at: e.observed_at })),
    thumb: vid ? thumbUrl(vid) : null,
    video: short?.url ?? null,
    isNew: newIds.has(card.term_id),
  };
}

/** 이번 주 주목 셋: 검색 관심이 가장 많이 늘어난 순, 자료가 모자라면 목록 앞에서 채운다. */
export function pickSpotlight(rows: Row[], n = 3): { rows: Row[]; byGrowth: boolean } {
  const grown = rows.filter((r) => r.pct !== null && r.pct > 0).sort((a, b) => b.pct! - a.pct!).slice(0, n);
  if (grown.length === n) return { rows: grown, byGrowth: true };
  const fill = rows.filter((r) => !grown.includes(r)).slice(0, n - grown.length);
  return { rows: [...grown, ...fill], byGrowth: grown.length > 0 };
}

/** 검색어로 행 거르기 — 이름·뜻 안에 그대로 들어 있는 것만(느슨한 매칭은 판정이 아니므로 하지 않는다) */
export function filterRows(rows: Row[], q: string): Row[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((r) => r.name.toLowerCase().includes(needle) || r.gloss.toLowerCase().includes(needle));
}
