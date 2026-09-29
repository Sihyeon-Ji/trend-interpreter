/* 디자인 시안 '에디토리얼형'(/lab/o-editorial) — 문구·표시 규칙·계산을 한 곳에. 화면(서버·클라이언트 모두)이 부른다.
   판정(단계·리스크·지역)은 백엔드 규칙이 한 것을 글로만 옮긴다. 여기서 새로 세는 것은 네이버 검색 곡선의 4주 변화와 커버 고르기뿐이고,
   그것도 곡선에 있는 값만 쓴다(없는 날은 0, 자료가 모자라면 '자료 부족'). 커뮤니티 글의 제목·인용·사이트 이름은 어디에도 내지 않는다. */
import type { Locale } from "@/lib/i18n";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordCard, Lifecycle } from "@/lib/types";

export const BASE = "/lab/o-editorial";

/* ── 판(edition) ─────────────────────────────────────────────────────────── */

/** 목표 지역(백엔드 REGIONS_FOCUS). 판은 이 가운데 한 곳, 여러 곳을 묶은 것, 통합판(목표 지역 전체), 전 세계판(목표 지역 밖에서 널리 쓰이는 말) */
export const EDITION_ORDER = ["KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG"] as const;
export const SEA: string[] = ["TH", "VN", "ID", "PH", "MY", "SG"];
/** "KR" · "ALL" · "GLOBAL" · 여러 시장이면 목표 지역 순서로 이은 "TH,VN,ID" */
export type EditionKey = string;
export const EDITION_TABS: EditionKey[] = [...EDITION_ORDER, "ALL", "GLOBAL"];

/** 주소의 ?regions= → 판. 쉼표로 잇거나(TH,VN) 여러 번 준 것(regions=TH&regions=VN, 묶기 폼)을 모두 받는다.
 *  모르는 값은 버리고, 없으면 한국판. 'all' 이거나 목표 지역을 모두 고르면 통합판. 전 세계판은 따로만 연다. */
export function parseEdition(raw: string | string[] | undefined): EditionKey {
  const asked = [raw].flat().filter((v): v is string => !!v).join(",").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  if (!asked.length) return "KR";
  if (asked.includes("ALL")) return "ALL";
  const picked = EDITION_ORDER.filter((r) => asked.includes(r));
  if (!picked.length) return asked.includes("GLOBAL") ? "GLOBAL" : "KR";
  return picked.length === EDITION_ORDER.length ? "ALL" : picked.join(",");
}
export const isCombined = (e: EditionKey) => e.includes(",");
/** 판에 든 시장 — 통합판은 목표 지역 전부 */
export const editionMembers = (e: EditionKey): string[] => (e === "ALL" ? [...EDITION_ORDER] : e.split(","));
/** 판 → 대시보드 API 의 regions (통합판은 비워 보낸다 = 목표 지역 전체) */
export const editionRegions = (e: EditionKey): string[] => (e === "ALL" ? [] : e.split(","));
/** 추천(/recommend)에 넘길 목표 지역 — 전 세계판은 없이 */
export const recommendRegions = (e: EditionKey): string[] => (e === "GLOBAL" ? [] : editionMembers(e));
const editionParam = (e: EditionKey) => (e === "ALL" ? "all" : e);
export const editionHref = (e: EditionKey, extra = "") => `${BASE}?regions=${editionParam(e)}${extra}`;
export const entryHref = (termId: string, e?: EditionKey) => `${BASE}/m/${encodeURIComponent(termId)}${e ? `?regions=${editionParam(e)}` : ""}`;
export const listHref = (name: string, e: EditionKey, page = 1) => `${BASE}/list/${name}?regions=${editionParam(e)}${page > 1 ? `&page=${page}` : ""}`;

const REGION_NAME: Record<Locale, Record<string, string>> = {
  ko: { KR: "한국", JP: "일본", TW: "대만", HK: "홍콩", TH: "태국", VN: "베트남", ID: "인도네시아", PH: "필리핀", MY: "말레이시아", SG: "싱가포르", GLOBAL: "전 세계", ALL: "통합" },
  en: { KR: "Korea", JP: "Japan", TW: "Taiwan", HK: "Hong Kong", TH: "Thailand", VN: "Vietnam", ID: "Indonesia", PH: "Philippines", MY: "Malaysia", SG: "Singapore", GLOBAL: "Worldwide", ALL: "All markets" },
};
const displayNames: Partial<Record<Locale, Intl.DisplayNames>> = {};
/** 지역 이름 — 목표 지역은 정해 둔 이름, 그 밖(나라마다 표의 US·RU…)은 Intl 의 나라 이름 */
export function regionName(l: Locale, code: string): string {
  const known = REGION_NAME[l][code];
  if (known) return known;
  try {
    displayNames[l] ??= new Intl.DisplayNames([l === "ko" ? "ko" : "en"], { type: "region" });
    return displayNames[l]!.of(code) ?? code;
  } catch {
    return code;
  }
}
/** "한국판" / "Korea edition". 묶은 판은 "태국·베트남·인도네시아판", 동남아 6개국이면 "동남아시아판". */
export function editionName(l: Locale, e: EditionKey): string {
  if (!isCombined(e)) return l === "ko" ? `${regionName(l, e)}판` : `${regionName(l, e)} edition`;
  const members = e.split(",");
  if (members.length === SEA.length && SEA.every((r) => members.includes(r))) return l === "ko" ? "동남아시아판" : "Southeast Asia edition";
  const names = members.map((r) => regionName(l, r));
  if (l === "ko") return names.length > 4 ? `${names.slice(0, 3).join("·")} 외 ${names.length - 3}개 시장판` : `${names.join("·")}판`;
  const list = names.length > 4 ? `${names.slice(0, 3).join(", ")} and ${names.length - 3} more` : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
  return `${list} edition`;
}

/** 최근 7일 변화 한 줄 (백엔드 GET /updates 에서 이 판의 것만) */
export interface SinceItem {
  kind: "verified" | "meaning_changed" | "spike";
  at: string;
  label: string;
  termId?: string;
  lang?: string;
  reason?: { ko: string; en: string } | null;
  risk?: "caution" | "avoid" | null;   // 새로 실린 밈이 조심할 밈이면 목록에서도 알린다
}

/* ── 문구 ────────────────────────────────────────────────────────────────── */

/** 받침이 있으면 true — '20대는' / '50대 이상은' 처럼 조사를 고른다 */
const batchim = (w: string) => {
  const code = (w.trim().at(-1) ?? "").charCodeAt(0) - 0xac00;
  return code >= 0 && code < 11172 && code % 28 !== 0;
};
const eunNeun = (w: string) => `${w}${batchim(w) ? "은" : "는"}`;
const iGa = (w: string) => `${w}${batchim(w) ? "이" : "가"}`;

const koPortion = (p: number) => (p >= 95 ? "모두" : p >= 67 ? "대부분" : p >= 50 ? "절반 이상이" : "열에 셋 이상이");
const enPortion = (p: number) => (p >= 95 ? "all" : p >= 67 ? "most" : p >= 50 ? "at least half" : "at least three in ten");

const ko = {
  site: "트렌드 통역",
  skip: "본문으로 건너뛰기",
  searchLabel: "밈 이름이나 뜻으로 찾기",
  searchPlaceholder: "밈 이름이나 뜻으로 찾기",
  searchButton: "찾기",
  scraps: "스크랩",
  drafts: "초안 목록",
  editionsNav: "판 고르기",
  thisWeek: (ed: string) => `이번 주 ${ed}`,
  memesUnit: (n: number) => `${n}개`,
  recommend: "내 제품에 맞는 밈 추천받기",
  updated: (t: string) => `${t} 갱신`,

  // 여러 시장 묶기
  combineOpen: "여러 시장 묶기",
  combineTitle: "여러 시장을 한 호로 묶기",
  combineNote: "캠페인이 여러 시장에 걸치면 함께 볼 시장을 고르세요. 밈 추천받기에도 같은 시장이 넘어갑니다.",
  combineSubmit: "고른 시장으로 보기",
  combineSea: "동남아시아 6개국 한 번에 보기",
  combineClose: "닫기",
  combineMember: "이 호에 든 시장",

  // 지난번 방문 한 줄(판 머리)
  sinceLineAfter: (a: number, b: number) => (a && b ? `지난번 방문 이후 새로 실린 밈 ${a}개, 뜻이 바뀐 밈 ${b}개` : a ? `지난번 방문 이후 새로 실린 밈 ${a}개` : `지난번 방문 이후 뜻이 바뀐 밈 ${b}개`),
  sinceLineWeek: (a: number, b: number) => (a && b ? `최근 7일 동안 새로 실린 밈 ${a}개, 뜻이 바뀐 밈 ${b}개` : a ? `최근 7일 동안 새로 실린 밈 ${a}개` : `최근 7일 동안 뜻이 바뀐 밈 ${b}개`),
  sinceLineNone: "지난번 방문 이후 이 판에서 달라진 밈은 없습니다.",
  sinceLineQuiet: "최근 7일 동안 이 판에서 새로 실리거나 뜻이 바뀐 밈은 없습니다.",

  // 커버
  coverRule: {
    among: { none: "쓸 때 조심할 점이 없는 ", unjudged: "쓸 때 조심할 점을 아직 가리지 못한 ", caution: "주의 표시가 붙은 " },
    pool: { rising: "지금 쓰이는 밈 가운데 ", fading: "식어 가는 밈 가운데 " },
    rule: {
      broad: "네이버 검색이 가장 많이 늘어난 말이라 커버에 올렸습니다.",
      peak: "최근 3주 안에 네이버 검색이 6개월 만에 가장 많았던 말이라 커버에 올렸습니다.",
      growing: "쓰임이 늘고 있는 말이라 커버에 올렸습니다.",
      recent: "가장 최근에 쓰인 말이라 커버에 올렸습니다.",
    },
    noneSafe: "조심할 점이 없다고 확인된 밈이 이 판에 아직 없습니다.",
    noRising: "이 판에서 지금 쓰이는 밈으로 확인된 것이 없습니다.",
  },
  coverCautionLead: { rising: "이 판의 지금 쓰이는 밈은 모두 주의 표시가 붙어 있어, 커버도 주의 밈입니다. 브랜드 계정이라면 쓸 때 조심 칸의 이유부터 보세요.", fading: "이 판의 밈은 모두 주의 표시가 붙어 있어, 커버도 주의 밈입니다. 브랜드 계정이라면 쓸 때 조심 칸의 이유부터 보세요." },
  usedRecently: (d: string) => `${d}에도 쓰인 말입니다.`,
  usedLast: (d: string) => `마지막으로 쓰인 것은 ${d}입니다.`,
  broadNow: (valid: number, up: number) => `${valid}개 나이대 가운데 ${up}곳에서 최근 4주 네이버 검색이 그 전 4주보다 늘었습니다.`,
  peakNow: (age: string, d: string) => `${age}의 네이버 검색은 ${d}에 지난 6개월 중 가장 많았습니다.`,
  peakAfter: (age: string, d: string) => `${eunNeun(age)} ${d}에 지난 6개월 중 가장 많이 찾았습니다.`,
  riseNow: (age: string, pct: string) => `${age} 검색은 최근 4주가 그 전 4주보다 ${pct} 많습니다.`,
  make: "이 밈으로 만들기",
  readEntry: "자세히 읽기",
  curveCaption: (age: string, from: string, to: string) => `${age} 네이버 검색 관심, ${from}부터 ${to}까지. 가장 많이 찾은 날을 100으로 본 값입니다.`,
  curvePeak: (d: string) => `${d} 최고`,
  emptyCoverTitle: (ed: string) => `${ed}에 커버로 올릴 밈이 없습니다`,
  emptyCoverBody: "이 지역에서 뜻과 쓰임을 확인한 밈이 아직 없습니다. 확인을 마친 밈부터 여기에 싣습니다. 그동안 다른 판을 보거나, 이 지역에서 검색이 몰린 말을 아래에서 보세요.",
  emptyCoverQuiet: "이 지역에서 뜻과 쓰임을 확인한 밈이 아직 없고, 최근 7일 동안 검색이 몰린 말도 없습니다. 확인을 마친 밈부터 여기에 싣습니다. 그동안 다른 판을 보세요.",
  emptyCoverAvoidOnly: (n: number) => `${n === 1 ? "이 지역에서 확인한 밈은 하나뿐인데 사용 자제 밈이라" : `이 지역에서 확인한 밈 ${n}개가 모두 사용 자제 밈이라`} 커버에 올리지 않았습니다. 아래 ‘브랜드는 조심’에서 무엇을 피해야 하는지 보세요.`,
  emptyCoverAction: "통합판 보기",

  // 단계·리스크
  stageLabel: "단계",
  riskLabel: "쓸 때 조심",
  whereLabel: "쓰이는 곳",
  whoLabel: "누가 찾나",
  lastUsedLabel: "마지막 쓰임",
  checkedLabel: "뜻 확인",
  plainLabel: "쉽게 말하면",
  aliasesLabel: "다른 표기",
  riskNone: "특이 사항 없음",
  riskCaution: "주의",
  riskAvoid: "사용 자제",
  riskUnknown: "판단 보류",
  riskNotChecked: "확인 전",
  riskNoneWhy: "쓰인 글에서 비하나 선정성, 정치 같은 민감한 맥락을 찾지 못했습니다.",
  riskCautionWhy: "부정적이거나 민감한 맥락에서도 쓰입니다. 브랜드 계정이라면 문맥을 확인하고 쓰세요.",
  riskAvoidWhy: "민감한 맥락과 엮여 있어 브랜드 계정에서는 쓰지 않는 편이 안전합니다.",
  riskUnknownWhy: "쓰인 예가 아직 적어 조심할 점을 가리지 못했습니다. 브랜드 계정이라면 문맥을 직접 확인하세요.",
  riskNotCheckedWhy: "쓸 때 조심할 점을 아직 확인하지 않았습니다.",
  why: {
    byPerson: "사람이 직접 확인해 정한 수준입니다.",
    wordItself: "말 자체가 욕설이거나 성적인 표현입니다.",
    badOrigin: "유래에 비하나 혐오와 얽힌 이야기가 있습니다.",
    riskyPosts: (n: number) => `문제가 될 수 있는 맥락에서 쓰인 글이 ${n}건 있습니다.`,
    // 살펴본 글이 열두 건 이하라 비율 숫자를 내지 않는다(작은 표본의 100% 는 거짓 정밀함)
    negative: (p: number) => `최근 쓰인 글 몇 건을 살펴보니 ${koPortion(p)} 비꼬거나 불쾌한 말투였습니다.`,
    dictWarning: (s: string) => `사전 뜻풀이의 주의점: ${s}`,
    staleNews: "뉴스에 오른 뒤 언급이 줄고 있어 식상하게 보일 수 있습니다.",
    tooFew: (n: number) => `그 뜻으로 쓰인 예가 ${n}건뿐이라 아직 판단하지 않았습니다.`,
  },
  stage: { emerging: "막 퍼지기 시작", rising: "쓰임이 느는 중", peak: "지금이 절정", steady: "꾸준히 쓰임", declining: "쓰임이 주는 중", dormant: "거의 안 쓰임", unknown: "추세 미확인" } as Record<Lifecycle, string>,
  diffusion: { underground: "아는 사람만 씀", spreading: "퍼지는 중", mainstream: "누구나 아는 말", fading: "식상해짐" } as Record<string, string>,
  stageSentence: { emerging: "막 퍼지기 시작했습니다.", rising: "점점 더 많이 쓰입니다.", peak: "지금 가장 많이 쓰이는 때입니다.", steady: "지금도 꾸준히 쓰입니다.", declining: "요즘은 점점 덜 쓰입니다.", dormant: "지금은 거의 쓰지 않습니다.", unknown: "쓰임의 추세는 아직 가리지 못했습니다." } as Record<Lifecycle, string>,
  diffusionSentence: {
    underground: "아직 일부 커뮤니티에서만 씁니다. 먼저 쓰면 앞서 보이지만 모르는 사람이 많습니다.",
    spreading: "짧은 영상을 타고 퍼지며 쓰임이 늘고 있습니다.",
    mainstream: "뉴스에까지 오른 말이라 누구나 알아듣지만, 신선하게 들리지는 않습니다.",
    fading: "뉴스에 오른 뒤 쓰임이 줄고 있어 새 캠페인에는 늦었을 수 있습니다.",
  } as Record<string, string>,
  newTape: "새로 실림",
  staleTape: "90일 넘게 안 쓰임",
  changedTape: "뜻 바뀜",
  videoAlt: (name: string) => `${name} 영상 미리보기`,
  usedToday: "오늘 쓰임",
  usedYesterday: "어제 쓰임",
  usedDays: (n: number) => `${n}일 전 쓰임`,
  usedMonths: (n: number) => `${n}개월 전 쓰임`,
  usedYears: (n: number) => `${n}년 전 쓰임`,
  posterSearch: "검색",
  posterSearchSr: (p: string) => `네이버 검색, 최근 4주가 그 전 4주보다 ${p}`,

  // 다시 오신 분께
  sinceTitle: "지난번 방문 이후",
  sinceFirstTitle: "이번 주 달라진 것",
  sinceWhen: (d: string) => `${d}에 마지막으로 보셨습니다.`,
  sinceFirst: "처음 오셨거나 이 브라우저에 방문 기록이 없어, 최근 7일 동안의 변화를 보여 드립니다.",
  sinceNone: "그 뒤로 이 판에서 달라진 것이 없습니다. 최근 7일 동안의 변화는 아래 목록에 있습니다.",
  sinceNew: (n: number) => `새로 실린 밈 ${n}개`,
  sinceChanged: (n: number) => `뜻이 바뀐 밈 ${n}개`,
  sinceSpikes: (n: number) => `검색이 몰린 말 ${n}개`,
  spikesNote: "밈이 아닐 수 있습니다. 뉴스나 사건으로 검색이 갑자기 늘어난 말입니다.",
  sinceMore: (n: number) => `${n}개 더 보기`,
  sinceLess: "접기",
  sinceEmptyWeek: "최근 7일 동안 이 판에서 새로 실리거나 뜻이 바뀐 밈이 없습니다.",
  scrapTitle: "내 스크랩",
  scrapEmpty: "밈 옆의 스크랩 단추를 누르면, 다음에 왔을 때 그 밈의 단계나 쓸 때 조심 수준이 바뀌었는지 여기서 알려 드립니다. 스크랩은 이 브라우저에만 저장됩니다.",
  scrapSince: (d: string) => `${d}에 스크랩`,
  scrapMoved: (from: string, to: string) => `단계: 스크랩할 때는 ‘${from}’, 지금은 ‘${to}’입니다.`,
  scrapRiskMoved: (from: string, to: string) => `쓸 때 조심: 스크랩할 때는 ‘${from}’, 지금은 ‘${to}’입니다.`,
  scrapSame: "스크랩한 뒤로 달라진 것이 없습니다.",
  scrapGone: "지금 목록에서 찾을 수 없습니다. 사전에서 빠졌거나 확인 중입니다.",
  scrapLoading: "스크랩한 밈의 지금 상태를 불러오는 중입니다.",
  scrapFailed: "지금 상태를 불러오지 못했습니다. 잠시 뒤 다시 열어 보세요.",
  scrapAdd: "스크랩",
  scrapAdded: (name: string) => `${name}을(를) 스크랩했습니다.`,
  scrapRemoved: (name: string) => `${name} 스크랩을 취소했습니다.`,

  // 차례·꼭지
  contentsLead: "이번 호에는",
  contentsTail: "가 실렸습니다.",
  contentsPart: { rising: (n: number) => `지금 쓰이는 밈 ${n}개`, searched: (n: number) => `요즘 더 찾는 밈 ${n}개`, fading: (n: number) => `식어 가는 밈 ${n}개`, caution: (n: number) => `브랜드가 조심할 밈 ${n}개` } as Record<string, (n: number) => string>,
  withCover: (n: number) => `커버를 포함해 ${n}개`,
  rubricRising: "지금 쓰이는 밈",
  rubricRisingNote: "지금 퍼지는 중인 밈부터 싣고, 누구나 아는 말은 뒤에 둡니다. 같은 단계에서는 최근에 쓰인 말이 먼저입니다. ‘검색’ 숫자는 네이버 나이대별 최근 4주 변화의 가운데 값이고, 한국어로 검색된 말에만 있습니다.",
  rubricSearch: "요즘 더 찾는 밈",
  rubricSearchNote: "네이버에서 최근 4주 검색이 그 전 4주보다 늘어난 밈입니다. 나이대마다 따로 세어, 절반이 넘는 나이대에서 15% 넘게 늘어난 것만 싣고, 큰 숫자는 그 가운데 값입니다. 전 4주에 거의 찾지 않던 나이대는 비율을 내지 않습니다. 검색이 늘었다고 다시 유행하는 것은 아닙니다.",
  rubricFading: "식어 가는 밈",
  rubricFadingNote: "쓰임이 줄었거나, 12주 동안 언급 없이 마지막 쓰임이 90일을 넘은 말입니다. 새 캠페인보다는 옛 감성을 일부러 살릴 때 씁니다.",
  rubricCaution: "브랜드는 조심",
  rubricCautionNote: "사용 자제 밈을 먼저 싣습니다. 주의 밈은 위 목록에도 표시와 함께 있고, 사용 자제 밈은 여기에만 있습니다.",
  countLine: (shown: number, total: number) => (shown < total ? `${total}개 가운데 ${shown}개` : `${total}개`),
  seeAll: (n: number) => `${n}개 모두 보기`,
  agesUp: (up: number, valid: number) => `${valid}개 나이대 가운데 ${up}곳에서 늘었습니다.`,
  windowEnd: (d: string) => `${d}까지 4주`,
  thin: "자료 부족",
  lowBase: "전엔 거의 없음",
  agesOpen: "나이대별로 보기",
  ageStripLabel: (name: string) => `${name} 나이대별 검색 변화`,
  rankLabel: (n: number) => `${n}위`,
  coverRow: "이번 호 커버",

  // 목록·쪽
  listBack: (ed: string) => `이번 주 ${ed}`,
  pagePrev: "이전 쪽",
  pageNext: "다음 쪽",
  pageOf: (p: number, last: number) => `${last}쪽 가운데 ${p}쪽`,

  // 실패·빈 상태
  loadFailed: "이번 주 밈을 불러오지 못했습니다. 데이터 서버가 답하지 않습니다.",
  retry: "다시 불러오기",
  loading: "이번 주 밈을 펴는 중입니다.",
  entryLoading: "기사를 펴는 중입니다.",
  entryFailed: "이 밈을 불러오지 못했습니다. 데이터 서버가 답하지 않습니다.",
  notFoundTitle: "사전에 없는 밈입니다",
  notFoundBody: "주소가 바뀌었거나, 확인을 거치는 중이라 아직 싣지 않은 밈입니다. 이름으로 찾아보세요.",

  // 기사(사전 항목)
  backTo: (ed: string) => `이번 주 ${ed}`,
  underReview: "확인 중",
  underReviewNote: "아직 확인을 거치는 중인 밈입니다. 뜻과 쓸 때 조심은 확인이 끝나면 바뀔 수 있어, 만들기에는 쓰지 않습니다.",
  factTitle: "브랜드가 써도 될까",
  factCautionMore: "조심할 점 보기",
  secOrigin: "유래",
  secUse: "쓰는 법",
  secCaution: "조심할 점",
  secCountries: "나라마다",
  secSearch: "누가 찾나",
  secSources: "출처",
  secHistory: "뜻이 바뀐 기록",
  sourceLine: "근거",
  newTab: "새 창",
  noOrigin: "유래는 아직 확인하지 못했습니다.",
  noMeaning: "뜻을 아직 확인하지 못했습니다.",
  linkedCol: "엮인 밈:",
  variantUnknown: "이 나라에서 무엇이 다른지는 아직 확인하지 못했습니다.",
  searchIntro: "네이버 데이터랩의 나이대별 검색 관심입니다. 나이대마다 가장 많이 찾은 날을 100으로 따로 맞췄기 때문에, 선의 높이로 나이대끼리 크기를 비교할 수는 없습니다. 오른쪽 숫자는 최근 4주가 그 전 4주보다 얼마나 늘거나 줄었는지입니다.",
  searchNone: "네이버 검색 자료가 없는 밈입니다. 한국어로 검색된 말만 자료가 있습니다.",
  searchTable: "표로 보기",
  searchKeys: "화살표 키로 날짜를 옮기면 그날의 값을 읽습니다.",
  monthCol: "달",
  peakLabel: "가장 많이 찾은 날",
  changeLabel: "최근 4주 변화",
  sourcesMore: (n: number) => `출처 ${n}개 더 보기`,
  historyNow: "지금 뜻",
  historyFrom: (d: string) => `${d}부터`,
  historyRange: (a: string, b: string) => `${a}부터 ${b}까지`,
  historyOnlyOne: "처음 실린 뒤로 뜻이 바뀐 적이 없습니다.",
  mediaFrom: "출처",
  mediaLicense: "라이선스",
  watchVideo: "YouTube에서 보기",
  makeNote: "사진이나 문구를 넣으면 이 밈으로 SNS 카피와 숏폼 대본을 만들어 드립니다.",
  avoidNoMake: "사용 자제 밈이라 만들기에서는 뺐습니다.",
  whoPeak: (age: string, d: string) => `${iGa(age)} ${d}에 가장 많이 찾았습니다`,
  whoNone: "네이버 검색 자료 없음",

  // 찾기
  searchTitle: "찾기",
  searchResults: (q: string, n: number) => `‘${q}’ 검색 결과 ${n}개`,
  searchEmpty: (q: string) => `‘${q}’은(는) 아직 사전에 없습니다. 철자를 바꾸거나 뜻에 들어갈 낱말로 찾아보세요.`,
  searchHint: "밈 이름, 다른 표기, 뜻에 들어간 낱말로 찾을 수 있습니다.",
  searchFailed: "사전을 불러오지 못했습니다. 데이터 서버가 답하지 않습니다.",
  suggestAll: (q: string) => `‘${q}’ 결과 모두 보기`,
  suggestLoading: "사전을 불러오는 중입니다.",
  suggestFailed: "사전을 불러오지 못했습니다. 찾기 단추를 누르면 결과 쪽에서 찾습니다.",
  suggestEmpty: "맞는 밈이 없습니다. 찾기 단추를 누르면 뜻까지 뒤져 봅니다.",
  suggestCount: (n: number) => `밈 ${n}개가 맞습니다. 위아래 화살표로 고르세요.`,

  footerData: "뜻과 쓸 때 조심은 확인을 거친 사전에서, 검색 추이는 네이버 데이터랩에서 옵니다. 커뮤니티 글은 쓰임을 세는 데만 쓰고 화면에 옮기지 않습니다.",
  footerApp: "지금 앱으로 보기",
  sampleNote: "예시 데이터로 보고 있습니다.",
};

type Copy = typeof ko;

const en: Copy = {
  site: "Trend Interpreter",
  skip: "Skip to content",
  searchLabel: "Search memes by name or meaning",
  searchPlaceholder: "Search by name or meaning",
  searchButton: "Search",
  scraps: "Saved",
  drafts: "All drafts",
  editionsNav: "Choose an edition",
  thisWeek: (ed: string) => `This week, ${ed}`,
  memesUnit: (n: number) => `${n}`,
  recommend: "Get memes for my product",
  updated: (t: string) => `Updated ${t}`,

  combineOpen: "Combine markets",
  combineTitle: "Combine markets into one issue",
  combineNote: "If a campaign runs in several markets, pick them here. Meme suggestions for your product use the same markets.",
  combineSubmit: "Show these markets",
  combineSea: "All six Southeast Asian markets",
  combineClose: "Close",
  combineMember: "in this issue",

  sinceLineAfter: (a: number, b: number) => (a && b ? `Since your last visit: ${a} new meme${a === 1 ? "" : "s"}, ${b} changed meaning${b === 1 ? "" : "s"}` : a ? `Since your last visit: ${a} new meme${a === 1 ? "" : "s"}` : `Since your last visit: ${b} changed meaning${b === 1 ? "" : "s"}`),
  sinceLineWeek: (a: number, b: number) => (a && b ? `Last 7 days: ${a} new meme${a === 1 ? "" : "s"}, ${b} changed meaning${b === 1 ? "" : "s"}` : a ? `Last 7 days: ${a} new meme${a === 1 ? "" : "s"}` : `Last 7 days: ${b} changed meaning${b === 1 ? "" : "s"}`),
  sinceLineNone: "No meme in this edition has changed since your last visit.",
  sinceLineQuiet: "No meme in this edition was added or changed in the last 7 days.",

  coverRule: {
    among: { none: " with no brand-safety flags", unjudged: " whose brand safety is not determined yet", caution: " flagged for caution" },
    pool: { rising: "memes in use now", fading: "memes cooling off" },
    rule: {
      broad: "its Naver searches grew the most",
      peak: "its Naver searches hit a six-month high in the last three weeks",
      growing: "its use is growing",
      recent: "it was used most recently",
    },
    noneSafe: "No meme in this edition has been cleared for brand safety yet.",
    noRising: "No meme is confirmed as in use in this edition yet.",
  },
  coverCautionLead: { rising: "Every meme in use in this edition is flagged for caution, so the cover is too. On a brand account, read the brand-safety reasons first.", fading: "Every meme in this edition is flagged, so the cover is a caution meme too. On a brand account, read the brand-safety reasons first." },
  usedRecently: (d: string) => `It was still in use on ${d}.`,
  usedLast: (d: string) => `It was last used on ${d}.`,
  broadNow: (valid: number, up: number) => `Naver searches over the last four weeks beat the four weeks before in ${up} of ${valid} age groups.`,
  peakNow: (age: string, d: string) => `Naver searches by people in their ${age} hit a six-month high on ${d}.`,
  peakAfter: (age: string, d: string) => `People in their ${age} searched most on ${d}, a six-month high.`,
  riseNow: (age: string, pct: string) => `Searches by people in their ${age} are up ${pct} over the previous four weeks.`,
  make: "Make something with this meme",
  readEntry: "Read the full entry",
  curveCaption: (age: string, from: string, to: string) => `Naver search interest, people in their ${age}, ${from} to ${to}. The busiest day is 100.`,
  curvePeak: (d: string) => `High on ${d}`,
  emptyCoverTitle: (ed: string) => `No cover for the ${ed} this week`,
  emptyCoverBody: "No meme from this market has had its meaning and use confirmed yet. Memes appear here once they are checked. Meanwhile, open another edition or see below what people here searched for suddenly.",
  emptyCoverQuiet: "No meme from this market has had its meaning and use confirmed yet, and no search spiked here in the last 7 days. Memes appear here once they are checked. Meanwhile, open another edition.",
  emptyCoverAvoidOnly: (n: number) => `${n === 1 ? "The only confirmed meme here is one to avoid" : `All ${n} confirmed memes here are ones to avoid`}, so there is no cover. See “Brands, take care” below for what to steer clear of.`,
  emptyCoverAction: "Open the all-markets edition",

  stageLabel: "Stage",
  riskLabel: "Brand safety",
  whereLabel: "Used in",
  whoLabel: "Who searches",
  lastUsedLabel: "Last used",
  checkedLabel: "Meaning checked",
  plainLabel: "In plain words",
  aliasesLabel: "Also written",
  riskNone: "No flags",
  riskCaution: "Caution",
  riskAvoid: "Avoid",
  riskUnknown: "Undetermined",
  riskNotChecked: "Not checked yet",
  riskNoneWhy: "We found no derogatory, sexual or political context where it is used.",
  riskCautionWhy: "Also used in negative or sensitive contexts. On a brand account, check the context first.",
  riskAvoidWhy: "Tied to sensitive contexts. Safer to keep it off brand accounts.",
  riskUnknownWhy: "Too few examples to tell what to watch out for yet. On a brand account, check the context yourself.",
  riskNotCheckedWhy: "Not checked for brand safety yet.",
  why: {
    byPerson: "A person checked this and set the level.",
    wordItself: "The word itself is a swear word or sexual.",
    badOrigin: "Its origin involves derogatory or hateful content.",
    riskyPosts: (n: number) => `${n} posts use it in a context that could cause trouble.`,
    negative: (p: number) => `Of the few recent posts we looked at, ${enPortion(p)} use it in a sarcastic or unpleasant tone.`,
    dictWarning: () => "The dictionary entry itself notes a caution.",
    staleNews: "Mentions have dropped since it reached the news, so it may look stale.",
    tooFew: (n: number) => `Only ${n} examples use it in this sense, so we have not judged it yet.`,
  },
  stage: { emerging: "Just starting", rising: "Growing", peak: "At its peak", steady: "In steady use", declining: "Used less", dormant: "Rarely used", unknown: "Trend unclear" } as Record<Lifecycle, string>,
  diffusion: { underground: "Insiders only", spreading: "Spreading", mainstream: "Everyone knows it", fading: "Worn out" } as Record<string, string>,
  stageSentence: { emerging: "It is just starting to spread.", rising: "It is being used more and more.", peak: "It is at the height of its use.", steady: "It is still in steady use.", declining: "It is used less and less.", dormant: "It is rarely used now.", unknown: "Its trend is not clear yet." } as Record<Lifecycle, string>,
  diffusionSentence: {
    underground: "Still used only inside some communities. Using it early stands out, but many people won't get it.",
    spreading: "Spreading through short videos and used more each week.",
    mainstream: "It has reached the news, so everyone gets it, but it no longer sounds fresh.",
    fading: "Use has dropped since it reached the news; it may be late for a new campaign.",
  } as Record<string, string>,
  newTape: "New",
  staleTape: "Unused for 90+ days",
  changedTape: "Meaning changed",
  videoAlt: (name: string) => `Video preview for ${name}`,
  usedToday: "Used today",
  usedYesterday: "Used yesterday",
  usedDays: (n: number) => `Used ${n} days ago`,
  usedMonths: (n: number) => `Used ${n} month${n === 1 ? "" : "s"} ago`,
  usedYears: (n: number) => `Used ${n} year${n === 1 ? "" : "s"} ago`,
  posterSearch: "Searches",
  posterSearchSr: (p: string) => `Naver searches, last four weeks against the four before: ${p}`,

  sinceTitle: "Since your last visit",
  sinceFirstTitle: "What changed this week",
  sinceWhen: (d: string) => `You last looked on ${d}.`,
  sinceFirst: "This browser has no earlier visit, so here are the changes from the last 7 days.",
  sinceNone: "Nothing in this edition has changed since then. The changes from the last 7 days are listed below.",
  sinceNew: (n: number) => `${n} new meme${n === 1 ? "" : "s"}`,
  sinceChanged: (n: number) => `${n} meaning${n === 1 ? "" : "s"} changed`,
  sinceSpikes: (n: number) => `${n} search spike${n === 1 ? "" : "s"}`,
  spikesNote: "These may not be memes. They are words whose searches jumped because of news or events.",
  sinceMore: (n: number) => `Show ${n} more`,
  sinceLess: "Show less",
  sinceEmptyWeek: "No meme in this edition was added or changed in the last 7 days.",
  scrapTitle: "Saved memes",
  scrapEmpty: "Save a meme and next time you visit we'll tell you here whether its stage or brand-safety level has changed. Saved memes stay in this browser only.",
  scrapSince: (d: string) => `Saved ${d}`,
  scrapMoved: (from: string, to: string) => `Stage: “${from}” when you saved it, “${to}” now.`,
  scrapRiskMoved: (from: string, to: string) => `Brand safety: “${from}” when you saved it, “${to}” now.`,
  scrapSame: "No change since you saved it.",
  scrapGone: "Not in the current lists. It was removed or is being re-checked.",
  scrapLoading: "Loading the current state of your saved memes.",
  scrapFailed: "Could not load the current state. Try again in a moment.",
  scrapAdd: "Save",
  scrapAdded: (name: string) => `Saved ${name}.`,
  scrapRemoved: (name: string) => `Removed ${name} from saved.`,

  contentsLead: "In this issue:",
  contentsTail: ".",
  contentsPart: { rising: (n: number) => `${n} memes in use now`, searched: (n: number) => `${n} searched more lately`, fading: (n: number) => `${n} cooling off`, caution: (n: number) => `${n} for brands to handle with care` } as Record<string, (n: number) => string>,
  withCover: (n: number) => `${n}, including the cover`,
  rubricRising: "In use now",
  rubricRisingNote: "Memes spreading now come first; ones everyone already knows come last. Within a stage, the most recently used come first. “Searches” is the middle value of the four-week change across Naver age groups, and exists only for words searched in Korean.",
  rubricSearch: "Searched more lately",
  rubricSearchNote: "Memes whose Naver searches in the last four weeks beat the four weeks before. Each age group is counted on its own; a meme is listed only when searches rose over 15% in more than half of them, and the big number is their middle value. Age groups that barely searched before get no percentage. More searches do not mean a comeback.",
  rubricFading: "Cooling off",
  rubricFadingNote: "Used less, or not mentioned for 12 weeks and last used over 90 days ago. Better for deliberate throwback humour than a new campaign.",
  rubricCaution: "Brands, take care",
  rubricCautionNote: "Memes to avoid come first. Caution memes also appear in the lists above with their flag; memes to avoid appear only here.",
  countLine: (shown: number, total: number) => (shown < total ? `${shown} of ${total}` : `${total}`),
  seeAll: (n: number) => `See all ${n}`,
  agesUp: (up: number, valid: number) => `Up in ${up} of ${valid} age groups.`,
  windowEnd: (d: string) => `Four weeks to ${d}`,
  thin: "Too little data",
  lowBase: "Near zero before",
  agesOpen: "By age group",
  ageStripLabel: (name: string) => `Search change by age group for ${name}`,
  rankLabel: (n: number) => `No. ${n}`,
  coverRow: "This issue's cover",

  listBack: (ed: string) => `This week, ${ed}`,
  pagePrev: "Previous page",
  pageNext: "Next page",
  pageOf: (p: number, last: number) => `Page ${p} of ${last}`,

  loadFailed: "Could not load this week's memes. The data server is not responding.",
  retry: "Try again",
  loading: "Opening this week's issue.",
  entryLoading: "Opening the entry.",
  entryFailed: "Could not load this meme. The data server is not responding.",
  notFoundTitle: "This meme is not in the dictionary",
  notFoundBody: "The address may have changed, or the meme is still being checked. Try searching by name.",

  backTo: (ed: string) => `This week, ${ed}`,
  underReview: "Being checked",
  underReviewNote: "This meme is still being checked. Its meaning and brand safety may change, so it is not offered for making content yet.",
  factTitle: "Can a brand use it?",
  factCautionMore: "See what to watch out for",
  secOrigin: "Origin",
  secUse: "How it is used",
  secCaution: "What to watch out for",
  secCountries: "Country by country",
  secSearch: "Who searches for it",
  secSources: "Sources",
  secHistory: "How the meaning changed",
  sourceLine: "Sources",
  newTab: "opens in a new tab",
  noOrigin: "Its origin has not been confirmed yet.",
  noMeaning: "Its meaning has not been confirmed yet.",
  linkedCol: "Related memes:",
  variantUnknown: "What is different here has not been confirmed yet.",
  searchIntro: "Naver DataLab search interest by age group. Each age group is scaled to its own busiest day (100), so line heights cannot be compared across age groups. The number on the right is the change over the last four weeks against the four weeks before.",
  searchNone: "No Naver search data for this meme. Only words searched in Korean have data.",
  searchTable: "Show as a table",
  searchKeys: "Use the arrow keys to move through the days and read each value.",
  monthCol: "Month",
  peakLabel: "Busiest day",
  changeLabel: "Last 4 weeks",
  sourcesMore: (n: number) => `Show ${n} more source${n === 1 ? "" : "s"}`,
  historyNow: "Current meaning",
  historyFrom: (d: string) => `Since ${d}`,
  historyRange: (a: string, b: string) => `${a} to ${b}`,
  historyOnlyOne: "The meaning has not changed since it was first published.",
  mediaFrom: "Source",
  mediaLicense: "Licence",
  watchVideo: "Watch on YouTube",
  makeNote: "Add a photo or a line about your product and get social copy and a short-video script built on this meme.",
  avoidNoMake: "Memes to avoid are left out of making content.",
  whoPeak: (age: string, d: string) => `People in their ${age} searched most on ${d}`,
  whoNone: "No Naver search data",

  searchTitle: "Search",
  searchResults: (q: string, n: number) => `${n} result${n === 1 ? "" : "s"} for “${q}”`,
  searchEmpty: (q: string) => `“${q}” is not in the dictionary yet. Try another spelling or a word from its meaning.`,
  searchHint: "Search by meme name, other spellings or a word in the meaning.",
  searchFailed: "Could not load the dictionary. The data server is not responding.",
  suggestAll: (q: string) => `See all results for “${q}”`,
  suggestLoading: "Loading the dictionary.",
  suggestFailed: "Could not load the dictionary. Press Search to look on the results page.",
  suggestEmpty: "No meme matches. Press Search to look through meanings too.",
  suggestCount: (n: number) => `${n} meme${n === 1 ? "" : "s"} match. Use the up and down arrows to choose.`,

  footerData: "Meanings and brand safety come from a checked dictionary; search trends come from Naver DataLab. Community posts are used only to count usage and are never shown.",
  footerApp: "Open the current app",
  sampleNote: "You are looking at sample data.",
};

const COPY: Record<Locale, Copy> = { ko, en };
export const copy = (l: Locale): Copy => COPY[l];

/** 나이대 라벨. 한국어는 '20대', 영어는 문장 안에서 'people in their 20s' 로 쓰여 '20s' 만 */
const AGE: Record<Locale, Record<string, string>> = {
  ko: { "10s": "10대", "20s": "20대", "30s": "30대", "40s": "40대", "50s+": "50대 이상" },
  en: { "10s": "teens", "20s": "20s", "30s": "30s", "40s": "40s", "50s+": "50s+" },
};
export const ageName = (l: Locale, g: string) => AGE[l][g] ?? g;
export const AGE_ORDER = ["10s", "20s", "30s", "40s", "50s+"];

/* ── 날짜 ────────────────────────────────────────────────────────────────── */

/** 서버와 브라우저가 같은 글을 내도록 시간대를 고정한다: 한국어는 서울, 영어는 UTC. */
const tz = (l: Locale) => (l === "ko" ? "Asia/Seoul" : "UTC");

/** "9월 28일" / "Sep 28". 올해가 아니면 연도를 붙인다. */
export function fmtDay(l: Locale, iso: string | null | undefined, ref?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  const zone = iso.length === 10 ? "UTC" : tz(l);
  const refYear = ref ? new Date(ref).getUTCFullYear() : new Date().getUTCFullYear();
  const year = Number(new Intl.DateTimeFormat("en-US", { timeZone: zone, year: "numeric" }).format(d));
  const withYear = year !== refYear;
  return new Intl.DateTimeFormat(l === "ko" ? "ko-KR" : "en-US", {
    timeZone: zone, month: l === "ko" ? "long" : "short", day: "numeric", ...(withYear ? { year: "numeric" } : {}),
  }).format(d);
}

/** "9월 29일 오후 2:22" / "Sep 29, 05:22 UTC" */
export function fmtStamp(l: Locale, iso: string | null | undefined, zone?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const z = zone ?? tz(l);
  const s = new Intl.DateTimeFormat(l === "ko" ? "ko-KR" : "en-US", { timeZone: z, month: l === "ko" ? "long" : "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: l === "ko" }).format(d);
  return l === "en" && !zone ? `${s} UTC` : s;
}

/** 갱신 시각이 든 주(월–일, 서울 기준) → "9월 28일–10월 4일" / "Sep 28 – Oct 4" */
export function weekRange(l: Locale, iso: string | null | undefined): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const seoul = new Date(t + 9 * 3_600_000);                    // 서울 날짜로 옮긴 뒤 그날의 요일
  const dow = (seoul.getUTCDay() + 6) % 7;                        // 월요일 0
  const mon = new Date(Date.UTC(seoul.getUTCFullYear(), seoul.getUTCMonth(), seoul.getUTCDate() - dow));
  const sun = new Date(mon.getTime() + 6 * 86_400_000);
  const f = (d: Date) => fmtDay(l, d.toISOString().slice(0, 10), iso);
  return l === "ko" ? `${f(mon)}–${f(sun)}` : `${f(mon)} – ${f(sun)}`;
}

export const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);

/** 마지막 쓰임을 이 호의 갱신 시각에서 센 말로 — "3일 전 쓰임", "4개월 전 쓰임". 포스터·색인·장부가 같은 잣대로 견줄 수 있게.
 *  기준은 지금이 아니라 호를 만든 때(하루 네 번 갱신)라 화면이 다시 그려져도 같은 글이 나온다. */
export function usedAgo(l: Locale, iso: string | null | undefined, asOf: string | null | undefined): string | null {
  if (!iso || !asOf) return null;
  const t = Date.parse(iso);
  const now = Date.parse(asOf);
  if (Number.isNaN(t) || Number.isNaN(now)) return null;
  const c = copy(l);
  const d = Math.max(0, Math.floor((now - t) / 86_400_000));
  if (d === 0) return c.usedToday;
  if (d === 1) return c.usedYesterday;
  if (d < 60) return c.usedDays(d);
  if (d < 365) return c.usedMonths(Math.floor(d / 30.44));
  return c.usedYears(Math.floor(d / 365.25));
}

/* ── 단계·리스크 ─────────────────────────────────────────────────────────── */

export type TapeTone = "rise" | "steady" | "fade" | "unknown" | "caution" | "avoid" | "new";

const RISE = new Set(["emerging", "rising", "peak", "spreading"]);
const FADE = new Set(["declining", "dormant", "fading"]);
export const stageTone = (v: string | null | undefined): TapeTone => (!v || v === "unknown" ? "unknown" : RISE.has(v) ? "rise" : FADE.has(v) ? "fade" : "steady");

type StageInput = { lifecycle?: Lifecycle | null; diffusion?: string | null };

/** 목록의 밈 한 장에 붙일 단계 테이프 하나 — 움직임을 말하는 쪽(생애주기)이 있으면 그것, 아니면 퍼진 정도. */
export function stageTape(l: Locale, s: StageInput): { text: string; tone: TapeTone } {
  const c = copy(l);
  const life = s.lifecycle ?? "unknown";
  if (life !== "steady" && life !== "unknown") return { text: c.stage[life], tone: stageTone(life) };
  if (s.diffusion) return { text: c.diffusion[s.diffusion] ?? s.diffusion, tone: stageTone(s.diffusion) };
  return { text: c.stage[life], tone: stageTone(life) };
}

/** '지금 쓰이는 밈' 포스터에 붙일 단계 테이프 — 그 꼭지의 보통 상태(누구나 아는 말·꾸준히 쓰임)는 되풀이하지 않고,
 *  보통과 다른 것(퍼지는 중·쓰임이 느는 중·아는 사람만 씀)만. 열 장이 모두 '누구나 아는 말' 을 달던 것(검토 09-29). */
export function notableStage(l: Locale, s: StageInput): { text: string; tone: TapeTone } | null {
  const c = copy(l);
  const life = s.lifecycle ?? "unknown";
  if (life === "emerging" || life === "rising" || life === "peak") return { text: c.stage[life], tone: "rise" };
  if (s.diffusion === "spreading") return { text: c.diffusion.spreading, tone: "rise" };
  if (s.diffusion === "underground") return { text: c.diffusion.underground, tone: "steady" };
  return null;
}

/** 식어 가는 밈이 그 목록에 선 까닭 한 마디 — 90일 넘게 안 쓰임 → 쓰임이 주는 중·거의 안 쓰임 → 식상해짐 (백엔드 dashboard._is_fading 과 같은 갈래) */
export function fadeReason(l: Locale, card: Pick<KeywordCard, "lifecycle" | "diffusion" | "weekly" | "last_used" | "last_seen">, ref: string): string {
  const c = copy(l);
  const last = card.last_used ?? card.last_seen;
  const stale = !!last && !card.weekly?.some((p) => p.count) && Date.parse(ref) - Date.parse(last) > 90 * 86_400_000;
  if (stale) return c.staleTape;
  if (card.lifecycle === "declining" || card.lifecycle === "dormant") return c.stage[card.lifecycle];
  if (card.diffusion === "fading") return c.diffusion.fading;
  return stageTape(l, card).text;
}

/** 커버·기사에 붙이는 단계 테이프 전부(퍼진 정도, 생애주기) — 같은 말이면 한 번만 */
export function stageTapes(l: Locale, s: StageInput): { text: string; tone: TapeTone }[] {
  const c = copy(l);
  const out: { text: string; tone: TapeTone }[] = [];
  if (s.diffusion) out.push({ text: c.diffusion[s.diffusion] ?? s.diffusion, tone: stageTone(s.diffusion) });
  const life = s.lifecycle ?? "unknown";
  if (!(life === "unknown" && out.length)) out.push({ text: c.stage[life], tone: stageTone(life) });
  return out;
}

/** 단계 한두 문장 */
export function stageSentence(l: Locale, s: StageInput): string {
  const c = copy(l);
  const parts = [s.diffusion ? c.diffusionSentence[s.diffusion] : null, c.stageSentence[s.lifecycle ?? "unknown"]];
  return parts.filter(Boolean).join(" ");
}

type RiskInput = { risk_level?: string | null; risk_checked_at?: string | null; risk_reasons?: string[] | null };
export type RiskKind = "none" | "caution" | "avoid" | "unknown" | "unchecked";

/** 백엔드 keyword.riskOf 와 같은 갈래: 검사했는데 근거가 모자라면 '판단 보류', 검사 전이면 '확인 전' */
export function riskKind(r: RiskInput): RiskKind {
  if (r.risk_level === "caution" || r.risk_level === "avoid" || r.risk_level === "none") return r.risk_level;
  return r.risk_checked_at ? "unknown" : "unchecked";
}
export function riskWord(l: Locale, k: RiskKind): string {
  const c = copy(l);
  return { none: c.riskNone, caution: c.riskCaution, avoid: c.riskAvoid, unknown: c.riskUnknown, unchecked: c.riskNotChecked }[k];
}
export function riskWhy(l: Locale, k: RiskKind): string {
  const c = copy(l);
  return { none: c.riskNoneWhy, caution: c.riskCautionWhy, avoid: c.riskAvoidWhy, unknown: c.riskUnknownWhy, unchecked: c.riskNotCheckedWhy }[k];
}
export const riskTone = (k: RiskKind): TapeTone | null => (k === "caution" ? "caution" : k === "avoid" ? "avoid" : k === "unknown" ? "unknown" : null);

/** 리스크 규칙이 남긴 이유(한국어, 커뮤니티 글 인용이 들어 있다)를 인용 없이 쉬운 문장으로 옮긴다.
 *  데이터 방침(09-29): 커뮤니티 글의 제목·인용·사이트 이름은 화면에 내지 않는다 — 알아보는 틀만 옮기고, 모르는 틀은 버린다.
 *  부정 비율은 살펴본 글이 열두 건 이하(risk.PER_TERM)라 숫자 대신 '모두·대부분·절반 이상' 으로 쓴다. */
export function riskNotes(l: Locale, reasons: string[] | null | undefined): string[] {
  const w = copy(l).why;
  const out: string[] = [];
  for (const raw of reasons ?? []) {
    const r = raw.trim();
    let m: RegExpExecArray | null;
    if (r.startsWith("검수자가 정한 수준")) out.push(w.byPerson);
    else if (r.startsWith("표제어 자체가 욕설")) out.push(w.wordItself);
    else if (r.startsWith("영상 해석이 지적한 기원")) out.push(w.badOrigin);
    else if ((m = /^위험 유형이 붙은 근거 (\d+)건/.exec(r))) out.push(w.riskyPosts(Number(m[1])));
    else if ((m = /^부정적으로 쓰인 근거가 (\d+)%/.exec(r))) out.push(w.negative(Number(m[1])));
    else if ((m = /^사전 뜻풀이에 적힌 주의점: “(.+)”$/.exec(r))) out.push(w.dictWarning(m[1]));
    else if (r.startsWith("뉴스에 오른 뒤 언급이 줄고")) out.push(w.staleNews);
    else if ((m = /^그 뜻으로 쓰인 근거가 (\d+)건뿐/.exec(r))) out.push(w.tooFew(Number(m[1])));
  }
  return [...new Set(out)];
}

/* ── 이름 조판(맞춤 크기) ───────────────────────────────────────────────── */

const WIDE = /[ᄀ-ᇿ㄰-㆏가-힣぀-ヿ㐀-鿿豈-﫿！-｠]/;
const THAI_MARK = /[ัิ-ฺ็-๎]/;      // 태국 글자의 위·아래 붙는 표시는 폭이 없다
const NO_LINE_START = /^[、。，．・ー〜！？）」』】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ]/;

/* Pretendard Variable 900 의 실제 글자 폭(em, 자간 없이) — 브라우저에서 잰 값(09-29). 라틴 소문자를 0.56 으로 어림하던 것이
   5% 모자라 휴대폰 커버에서 'delul|u' 로 끊겼다. 한글은 0.86–0.92, 가나·한자는 1. */
const LATIN: Record<string, number> = {
  a: 0.63, b: 0.63, c: 0.59, d: 0.63, e: 0.59, f: 0.39, g: 0.63, h: 0.63, i: 0.29, j: 0.29, k: 0.59, l: 0.29, m: 0.91,
  n: 0.63, o: 0.61, p: 0.62, q: 0.63, r: 0.42, s: 0.57, t: 0.39, u: 0.63, v: 0.59, w: 0.85, x: 0.58, y: 0.59, z: 0.57,
  A: 0.77, B: 0.65, C: 0.74, D: 0.71, E: 0.6, F: 0.57, G: 0.74, H: 0.73, I: 0.29, J: 0.57, K: 0.7, L: 0.56, M: 0.91,
  N: 0.71, O: 0.76, P: 0.64, Q: 0.76, R: 0.65, S: 0.65, T: 0.67, U: 0.71, V: 0.77, W: 1.06, X: 0.73, Y: 0.74, Z: 0.67,
  "0": 0.7, "1": 0.49, "2": 0.63, "3": 0.66, "4": 0.68, "5": 0.65, "6": 0.63, "7": 0.61, "8": 0.67, "9": 0.64,
  "!": 0.34, "?": 0.58, ".": 0.3, ",": 0.31, ":": 0.3, ";": 0.3, "'": 0.2, "’": 0.2, "-": 0.45, "&": 0.67, "(": 0.42, ")": 0.42, "/": 0.4,
};
const HANGUL = /[ᄀ-ᇿ㄰-㆏가-힣]/;
const KANA_HAN = /[぀-ヿ㐀-鿿豈-﫿！-｠]/;

function charEm(ch: string): number {
  if (HANGUL.test(ch)) return 0.92;
  if (KANA_HAN.test(ch)) return 1;
  if (THAI_MARK.test(ch)) return 0;
  if (/[฀-๿]/.test(ch)) return 0.63;
  if (/\s/.test(ch)) return 0.22;
  return LATIN[ch] ?? (/[A-Z]/.test(ch) ? 0.74 : /[a-z0-9]/i.test(ch) ? 0.63 : 0.5);
}

/** 굵은 글씨(900)에 자간을 좁혔을 때 한 줄의 폭(em). 자간은 화면과 같게: 일본어·중국어·태국어 −0.02em, 그 밖 −0.045em(글자마다 붙는다).
 *  잰 값에 3% 를 얹어 넘치지 않게 한다. */
export function emWidth(s: string): number {
  const tracking = /[぀-ヿ㐀-鿿฀-๿]/.test(s) ? -0.02 : -0.045;
  let w = 0;
  for (const ch of s) {
    const e = charEm(ch);
    if (e) w += e + tracking;
  }
  return w * 1.03;
}

function splitWords(words: string[], k: number, joiner = " "): string[][] {
  // 낱말 순서를 지키며 k 줄로 나누는 모든 경우 가운데 가장 긴 줄이 가장 짧은 것 — 같으면 줄 길이가 고른 것,
  // 그것도 같으면 윗줄이 긴 것(포스터 제목은 위가 무겁다). 이름은 길어야 몇 낱말이라 다 세어 본다.
  if (k === 1) return [words];
  let best: string[][] = [words];
  let bestKey = [Infinity, Infinity, Infinity];
  const rec = (start: number, left: number, acc: string[][]) => {
    if (left === 1) {
      const lines = [...acc, words.slice(start)];
      const ws = lines.map((ln) => emWidth(ln.join(joiner)));
      const mw = Math.max(...ws);
      const key = [mw, ws.reduce((a, w) => a + (mw - w) ** 2, 0), -ws[0]];
      const better = key.findIndex((v, i) => Math.abs(v - bestKey[i]) > 1e-6);
      if (better >= 0 && key[better] < bestKey[better]) { bestKey = key; best = lines; }
      return;
    }
    for (let i = start + 1; i <= words.length - (left - 1); i++) rec(i, left - 1, [...acc, words.slice(start, i)]);
  };
  rec(0, k, []);
  return best;
}

const NO_LINE_END = /[（「『【〈《(]$/;
// 앞 조각에 붙는 것: 히라가나 한 글자(조사·어미, 사전이 잘못 끊은 꼬리), 닫는 문장부호, 흔한 조동사('萌え|ない' 를 끊지 않게)
const ATTACH = /^([぀-ゟ]|[!?.,:;)\]]|ない|なく|ます|です|でした|ました|たい|じゃん|だよ|だね)$/;
const segmenters: Record<string, Intl.Segmenter> = {};

/** 띄어쓰기 없는 일본어·중국어·태국어 이름을 낱말 조각으로(ICU 사전). 줄은 조각 사이에서만 바꾸고,
 *  줄 첫머리에 올 수 없는 글자(ー ぅ 、…)나 히라가나 한 글자는 앞 조각에 붙인다 — 'オタクに|優しい|ギャル', 'きのこ|たけのこ|戦争'. */
function segments(s: string): string[] | null {
  const lang = /[぀-ヿ]/.test(s) ? "ja" : /[฀-๿]/.test(s) ? "th" : /[一-鿿]/.test(s) ? "zh" : null;
  if (!lang || typeof Intl.Segmenter !== "function") return null;
  segmenters[lang] ??= new Intl.Segmenter(lang, { granularity: "word" });
  const out: string[] = [];
  for (const { segment } of segmenters[lang].segment(s)) {
    if (out.length && (NO_LINE_START.test(segment) || ATTACH.test(segment) || NO_LINE_END.test(out[out.length - 1]))) out[out.length - 1] += segment;
    else out.push(segment);
  }
  return out.length > 1 ? out : null;
}

/** 낱말을 못 찾은 이름은 글자 하나하나가 조각 — 줄 첫머리에 올 수 없는 글자(、ー っ…)는 앞 글자에 붙인다 */
function charPieces(s: string): string[] {
  const out: string[] = [];
  for (const ch of s) {
    if (out.length && (NO_LINE_START.test(ch) || NO_LINE_END.test(out[out.length - 1]))) out[out.length - 1] += ch;
    else out.push(ch);
  }
  return out;
}

/** 이름을 줄로 나누고 가장 긴 줄의 폭(em)을 돌려준다. 화면은 font-size = min(상한, 100cqi / em) 으로 폭을 채운다.
 *  splitAbove = 그 칸이 상한 크기로 담는 대략의 폭(em). 한 줄이 그 안에 들면 한 줄, 아니면 그 안에 드는 가장 적은 줄 수,
 *  어느 쪽도 안 되면 줄이 늘 때마다 손해를 매긴 점수가 가장 낮은 것 — 크기가 늘지 않는데 줄만 느는 일이 없게. */
export function fitName(name: string, maxLines = 3, splitAbove = 4.6): { lines: string[]; em: number } {
  const clean = name.trim().replace(/\s+/g, " ");
  const one = emWidth(clean);
  const limit = splitAbove * 1.15;          // 어림셈이라 조금 넘쳐도 줄을 더 늘리지 않는다
  if (one <= limit || maxLines === 1) return { lines: [clean], em: Math.max(one, 1.2) };
  const spaced = clean.includes(" ");
  const pieces = spaced ? clean.split(" ") : segments(clean);
  const joiner = spaced ? " " : "";
  const chars = [...clean].length;
  const options: { lines: string[]; em: number }[] = [];
  for (let k = 2; k <= maxLines; k++) {
    const lines = pieces && pieces.length >= k
      ? splitWords(pieces, k, joiner).map((ln) => ln.join(joiner))
      // 낱말을 못 찾은 긴 한·중·일 이름은 글자 수로 — 낱말 중간이 끊기므로 다섯 글자에 한 줄 넘게는 나누지 않는다
      : !spaced && chars > 6 && k <= Math.ceil(chars / 5) && WIDE.test(clean) ? splitWords(charPieces(clean), k, "").map((ln) => ln.join("")) : null;
    if (lines) options.push({ lines, em: Math.max(...lines.map((ln) => emWidth(ln))) });
  }
  const score = (o: { lines: string[]; em: number }) => o.em * (1 + 0.22 * (o.lines.length - 1));
  const best = options.find((o) => o.em <= limit) ?? options.reduce((a, o) => (score(o) < score(a) ? o : a), { lines: [clean], em: one });
  return { lines: best.lines, em: Math.max(best.em, 1.2) };
}

/* ── 네이버 검색 곡선 ───────────────────────────────────────────────────── */

/** ok: 비율을 낸다 · thin: 한 창에 20일 미만 · low: 그 전 4주 평균이 그 나이대 최고치의 5% 미만(거의 안 찾던 때라 비율이 부풀려진다 — +629% 같은) */
export type AgeState = "ok" | "thin" | "low";

export interface AgeTrend {
  gen: string;
  change: number | null;       // 최근 4주 / 그 전 4주 − 1. state 가 ok 일 때만
  state: AgeState;
  end: string | null;          // 곡선의 마지막 날
  peak: string | null;         // 가장 많이 찾은 날
  points: [string, number][];  // 날짜순
}

const DAY = 86_400_000;
const WINDOW = 28;
const MIN_DAYS = 20;
const MIN_BASE = 5;

export function ageTrend(c: GenerationCurve): AgeTrend {
  const points = [...c.points].filter((p) => Array.isArray(p) && typeof p[1] === "number").sort((a, b) => a[0].localeCompare(b[0]));
  const end = points.at(-1)?.[0] ?? null;
  let a = 0, na = 0, b = 0, nb = 0;
  if (end) {
    const endMs = Date.parse(`${end}T00:00:00Z`);
    for (const [d, v] of points) {
      const age = (endMs - Date.parse(`${d}T00:00:00Z`)) / DAY;
      if (age < WINDOW) { a += v; na++; } else if (age < WINDOW * 2) { b += v; nb++; }
    }
  }
  // 없는 날은 0 으로 본다(합을 같은 28일로 나누므로 합의 비가 곧 평균의 비)
  const state: AgeState = na < MIN_DAYS || nb < MIN_DAYS ? "thin" : b / WINDOW < MIN_BASE ? "low" : "ok";
  const change = state === "ok" ? a / b - 1 : null;
  return { gen: c.generation, change, state, end, peak: c.peak_date ?? null, points };
}

export interface SearchSummary { ages: AgeTrend[]; valid: number; up: number; median: number | null; end: string | null }

const UP = 0.15;

export function searchSummary(curves: GenerationCurve[] | null | undefined): SearchSummary | null {
  if (!curves?.length) return null;
  const ages = AGE_ORDER.map((g) => curves.find((c) => c.generation === g)).filter((c): c is GenerationCurve => !!c && c.points.length > 0).map(ageTrend);
  if (!ages.length) return null;
  const vals = ages.map((a) => a.change).filter((v): v is number => v !== null).sort((x, y) => x - y);
  const median = vals.length ? (vals.length % 2 ? vals[(vals.length - 1) / 2] : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2) : null;
  const end = ages.map((a) => a.end).filter(Boolean).sort().at(-1) ?? null;
  return { ages, valid: vals.length, up: vals.filter((v) => v >= UP).length, median, end };
}

/** '요즘 더 찾는 밈' 에 실을까 — 셋 이상 나이대에 자료가 있고, 절반이 넘는 나이대에서 15% 이상 늘고, 가운데 값도 15% 이상 */
export const searchedMore = (s: SearchSummary | null | undefined): s is SearchSummary =>
  !!s && s.valid >= 3 && s.up > s.valid / 2 && (s.median ?? 0) >= UP;

/** 커버의 곡선 — 가장 최근에 정점을 찍은 나이대(지금 가장 뜨거운 나이대). 자료가 모자란 나이대는 뺀다. */
export function hottestAge(s: SearchSummary | null | undefined): AgeTrend | null {
  if (!s) return null;
  const withData = s.ages.filter((a) => a.points.length >= 60 && a.peak);
  return withData.sort((a, b) => (b.peak ?? "").localeCompare(a.peak ?? "") || (b.change ?? -9) - (a.change ?? -9))[0] ?? null;
}

/** "+48%" / "−13%" (빼기는 진짜 빼기표) */
export function pct(v: number): string {
  const n = Math.round(v * 100);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n)}%`;
}

/* ── 커버 고르기 ────────────────────────────────────────────────────────── */

export type CoverRule = "broad" | "peak" | "growing" | "recent";
export type CoverSafety = "none" | "unjudged" | "caution";
export interface CoverPick { card: KeywordCard; rule: CoverRule; safety: CoverSafety; pool: "rising" | "fading" }

const lastTs = (c: KeywordCard) => Math.max(...[c.last_used, c.last_seen].map((d) => (d ? Date.parse(d) : 0)).filter((v) => !Number.isNaN(v)), 0);

/** 이번 호의 커버. 브랜드 마케터의 첫 화면이라 주의 밈을 말없이 앞에 세우지 않는다(검토 09-29).
 *  1) 쓸 때 조심할 점이 없는 밈 → 아직 가리지 못한 밈 → 주의 밈 순으로 찾고(사용 자제는 목록에 없다),
 *  2) 그 안에서 네이버 검색이 넓게 는 말(가운데 값이 큰 것) → 최근 3주 안에 6개월 최고를 찍은 말(가장 최근)
 *     → 쓰임이 늘고 있는 말(퍼지는 중·쓰임이 느는 중, 백엔드 순서) → 가장 최근에 쓰인 말.
 *  지금 쓰이는 밈이 없으면 식어 가는 밈에서 같은 규칙으로. 곡선은 호의 갱신 시각에서 2주 안에 끝난 것만 믿는다. */
export function pickCover(rising: KeywordCard[], fading: KeywordCard[], searches: Record<string, SearchSummary>, ref: string): CoverPick | null {
  const pool = rising.length ? "rising" : "fading";
  const cards = rising.length ? rising : fading;
  const fresh = (s: SearchSummary | undefined) => !!s?.end && Math.abs(daysBetween(s.end, ref)) <= 14;
  const tiers: [CoverSafety, (k: RiskKind) => boolean][] = [
    ["none", (k) => k === "none"],
    ["unjudged", (k) => k === "unknown" || k === "unchecked"],
    ["caution", (k) => k === "caution"],
  ];
  for (const [safety, ok] of tiers) {
    const cands = cards.filter((c) => ok(riskKind(c)));
    if (!cands.length) continue;
    const broad = cands.filter((c) => fresh(searches[c.term_id]) && searchedMore(searches[c.term_id]))
      .sort((a, b) => (searches[b.term_id].median ?? 0) - (searches[a.term_id].median ?? 0));
    if (broad.length) return { card: broad[0], rule: "broad", safety, pool };
    const peak = cands
      .map((c) => ({ c, hot: fresh(searches[c.term_id]) ? hottestAge(searches[c.term_id]) : null }))
      .filter((x) => x.hot?.peak && x.hot.end && daysBetween(x.hot.peak, x.hot.end) <= 21)
      .sort((a, b) => b.hot!.peak!.localeCompare(a.hot!.peak!));
    if (peak.length) return { card: peak[0].c, rule: "peak", safety, pool };
    // 검색 곡선이 없으면(한국 밖 판) 백엔드가 매긴 단계 — 퍼지는 중·쓰임이 느는 중인 말이 먼저(백엔드 순서 그대로)
    const growing = cands.find((c) => c.diffusion === "spreading" || c.lifecycle === "emerging" || c.lifecycle === "rising");
    if (growing) return { card: growing, rule: "growing", safety, pool };
    return { card: [...cands].sort((a, b) => lastTs(b) - lastTs(a))[0], rule: "recent", safety, pool };
  }
  return null;
}

/** 커버 밑에 적는 '왜 이 밈이 커버인가' — 고른 규칙을 그대로 한 문장으로 */
export function coverReason(l: Locale, p: Pick<CoverPick, "rule" | "safety" | "pool">): string {
  const r = copy(l).coverRule;
  const lead = [p.pool === "fading" ? r.noRising : "", p.safety === "unjudged" ? r.noneSafe : ""].filter(Boolean).join(" ");
  const body = l === "ko"
    ? `${r.among[p.safety]}${r.pool[p.pool]}${r.rule[p.rule]}`
    : `On the cover because ${r.rule[p.rule]}, among ${r.pool[p.pool]}${r.among[p.safety]}.`;
  return lead ? `${lead} ${body}` : body;
}

/* ── 근거·영상 ──────────────────────────────────────────────────────────── */

/** 화면에 내는 출처는 참고 위키·기사·영상만. 커뮤니티 글과 검색 통계 행은 내지 않는다(데이터 방침 09-29). */
const REFERENCE = /(^|\.)((\w+\.)?wikipedia\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net|wiktionary\.org|nicovideo\.jp|wikiwiki\.jp)$/i;
const hostOf = (url: string) => { try { return new URL(url).hostname; } catch { return ""; } };
const hasPath = (url: string) => { try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; } };

/* 백엔드가 기사(news)로 분류했지만 실은 커뮤니티·블로그·SNS 글인 것 — 구글 뉴스로 들어온 위버스 커뮤니티 포스트, 브런치 글,
   네이트판 글(구글 뉴스는 네이트 뉴스와 같은 '네이트' 로 준다), EA 커뮤니티 갤러리. 이름(source_domain)과 주소를 모두 본다. */
const UGC_NAMES = new Set([
  "브런치", "brunch", "weverse", "위버스", "네이트", "nate", "네이트판", "디시인사이드", "dcinside", "갤러리", "더쿠", "theqoo", "인스티즈", "instiz",
  "에펨코리아", "fmkorea", "루리웹", "ruliweb", "클리앙", "clien", "뽐뿌", "ppomppu", "네이버블로그", "네이버카페", "네이버지식in", "네이버포스트", "다음카페",
  "티스토리", "tistory", "velog", "medium", "note", "ameba", "ameblo", "アメーバブログ", "はてなブログ", "hatena", "yahoo!知恵袋", "知恵袋", "togetter",
  "5ch", "5ちゃんねる", "2ch", "pantip", "dcard", "ptt", "lihkg", "kaskus", "lowyat", "hardwarezone", "reddit", "bluesky", "bsky", "lemmy", "hackernews",
  "x", "twitter", "instagram", "threads", "facebook", "tiktok", "pinterest", "tumblr", "quora", "포스타입", "postype", "블라인드", "blind", "에브리타임",
  "오늘의유머", "보배드림", "mlbpark", "ea",
]);
const UGC_PREFIX = /^naver:(blog|cafe|cafearticle|kin|post)/;
const UGC_HOST = /(^|\.)(dcinside\.com|theqoo\.net|instiz\.net|fmkorea\.com|ruliweb\.com|clien\.net|ppomppu\.co\.kr|reddit\.com|redd\.it|bsky\.app|ycombinator\.com|5ch\.net|pantip\.com|dcard\.tw|ptt\.cc|lihkg\.com|kaskus\.co\.id|lowyat\.net|hardwarezone\.com\.sg|brunch\.co\.kr|weverse\.io|cafe\.naver\.com|kin\.naver\.com|blog\.naver\.com|post\.naver\.com|cafe\.daum\.net|pann\.nate\.com|tistory\.com|velog\.io|medium\.com|note\.com|ameblo\.jp|hatenablog\.com|hatena\.ne\.jp|togetter\.com|chiebukuro\.yahoo\.co\.jp|x\.com|twitter\.com|instagram\.com|threads\.net|facebook\.com|tumblr\.com|quora\.com|postype\.com|teamblind\.com|everytime\.kr|todayhumor\.co\.kr|bobaedream\.co\.kr|tiktok\.com)$/i;
const sourceKey = (s: string | null | undefined) => (s ?? "").toLowerCase().normalize("NFKC").replace(/\s+/g, "");

/** 커뮤니티·블로그·SNS 글인가 — 쓰임을 세는 데만 쓰고 제목·인용·사이트 이름을 내지 않는다. 영상(short)은 영상으로 본다. */
export function isCommunitySource(e: { kind: string; url: string; source_domain?: string | null }): boolean {
  if (e.kind === "community") return true;
  const dom = sourceKey(e.source_domain);
  if (UGC_PREFIX.test(dom)) return true;
  if (e.kind !== "news" && e.kind !== "web") return false;
  return UGC_NAMES.has(dom) || UGC_HOST.test(hostOf(e.url));
}

export function visibleSource(e: { kind: string; url: string; source_domain?: string | null }): boolean {
  if (!e.url || !hasPath(e.url)) return false;                  // 홈페이지 주소뿐인 것은 근거가 아니다
  if (isCommunitySource(e)) return false;
  if (e.kind === "news" || e.kind === "short" || e.kind === "wiki") return true;
  if (e.kind === "web") return REFERENCE.test(hostOf(e.url)) || REFERENCE.test(e.source_domain ?? "");
  return false;
}

export function youtubeId(url: string | null | undefined): string | null {
  const m = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/.exec(url ?? "");
  return m ? m[1] : null;
}

/** 카드의 영상 미리보기 — 근거 가운데 유튜브 영상(쇼츠) 주소가 있을 때만. 파일은 받지 않고 주소만 쓴다. */
export function cardVideo(card: Pick<KeywordCard, "evidences">): { id: string; url: string } | null {
  for (const e of card.evidences ?? []) {
    if (e.kind !== "short") continue;
    const id = youtubeId(e.url);
    if (id) return { id, url: e.url };
  }
  return null;
}

/** 뜻풀이 끝에 붙은 출처 꼬리('(위키낱말사전 기반)', '(Based on Wiktionary)')를 뗀다 — 출처는 기사의 출처 목록이 밝힌다. 뜻은 고치지 않는다. */
const SOURCE_TAIL = /\s*\((?:(?:위키낱말사전|위키백과|나무위키|Wiktionary|Wikipedia)\s*기반|Based on (?:Wiktionary|Wikipedia|Namuwiki))\)\s*\.?\s*$/i;
export const tidyGloss = (t: string) => t.replace(SOURCE_TAIL, "").trim() || t;

/** 뜻 한 줄 — 카드의 화면 언어 뜻. 영어가 없으면 한국어(그때는 lang="ko") */
export function glossOf(l: Locale, c: Pick<KeywordCard, "gloss_ko" | "gloss_en">): { text: string; lang?: string } {
  if (l === "en") return c.gloss_en ? { text: tidyGloss(c.gloss_en) } : { text: tidyGloss(c.gloss_ko), lang: "ko" };
  return c.gloss_ko ? { text: tidyGloss(c.gloss_ko) } : { text: tidyGloss(c.gloss_en), lang: "en" };
}

/* ── 곡선 그리기 ────────────────────────────────────────────────────────── */

const dayMs = (d: string) => Date.parse(`${d.slice(0, 10)}T00:00:00Z`);

/** 날짜·값(0–100) 점을 SVG 경로로. 사흘 넘게 빈 곳은 잇지 않는다 — 없는 날을 이어 그리면 없던 추이가 생긴다. */
export function curvePaths(points: [string, number][], from: string, to: string, w: number, h: number, top = 4): { line: string; area: string } {
  const x0 = dayMs(from), x1 = dayMs(to);
  const span = Math.max(1, x1 - x0);
  const X = (d: string) => ((dayMs(d) - x0) / span) * w;
  const Y = (v: number) => h - (Math.max(0, Math.min(100, v)) / 100) * (h - top);
  let line = "", area = "";
  let seg: [number, number][] = [];
  let prev: number | null = null;
  const flush = () => {
    if (seg.length) {
      line += seg.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
      if (seg.length > 1) area += `M${seg[0][0].toFixed(1)} ${h}` + seg.map(([x, y]) => `L${x.toFixed(1)} ${y.toFixed(1)}`).join("") + `L${seg.at(-1)![0].toFixed(1)} ${h}Z`;
    }
    seg = [];
  };
  for (const [d, v] of points) {
    const t = dayMs(d);
    if (t < x0 || t > x1) continue;
    if (prev !== null && t - prev > 3 * DAY) flush();
    seg.push([X(d), Y(v)]);
    prev = t;
  }
  flush();
  return { line, area };
}

export const xOf = (d: string, from: string, to: string, w: number) => ((dayMs(d) - dayMs(from)) / Math.max(1, dayMs(to) - dayMs(from))) * w;
