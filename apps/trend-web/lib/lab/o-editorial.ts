/* 디자인 시안 '에디토리얼형'(/lab/o-editorial) — 문구·표시 규칙·계산을 한 곳에. 화면(서버·클라이언트 모두)이 부른다.
   판정(단계·리스크·지역)은 백엔드 규칙이 한 것을 글로만 옮긴다. 여기서 새로 세는 것은 네이버 검색 곡선의 4주 변화뿐이고,
   그것도 곡선에 있는 값만 쓴다(없는 날은 0, 자료가 모자라면 '자료 부족'). 커뮤니티 글의 제목·인용·사이트 이름은 어디에도 내지 않는다. */
import type { Locale } from "@/lib/i18n";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordCard, Lifecycle } from "@/lib/types";

export const BASE = "/lab/o-editorial";

/* ── 판(edition) ─────────────────────────────────────────────────────────── */

/** 목표 지역(백엔드 REGIONS_FOCUS) + 통합판(목표 지역 전체) + 전 세계판(목표 지역 밖에서 널리 쓰이는 말) */
export const EDITION_ORDER = ["KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG"] as const;
export type EditionKey = (typeof EDITION_ORDER)[number] | "ALL" | "GLOBAL";
export const EDITIONS: EditionKey[] = [...EDITION_ORDER, "ALL", "GLOBAL"];

/** 주소의 ?regions= → 판. 모르는 값은 버리고, 없으면 한국판. 'all' 은 통합판. */
export function parseEdition(raw: string | undefined): EditionKey {
  const v = (raw ?? "").trim().toUpperCase();
  if (v === "ALL") return "ALL";
  return (EDITIONS as string[]).includes(v) ? (v as EditionKey) : "KR";
}
/** 판 → 대시보드 API 의 regions (통합판은 비워 보낸다 = 목표 지역 전체) */
export const editionRegions = (e: EditionKey): string[] => (e === "ALL" ? [] : [e]);
/** 추천(/recommend)에 넘길 목표 지역 — 전 세계판은 없이 */
export const recommendRegions = (e: EditionKey): string[] => (e === "ALL" ? [...EDITION_ORDER] : e === "GLOBAL" ? [] : [e]);
export const editionHref = (e: EditionKey, extra = "") => `${BASE}?regions=${e === "ALL" ? "all" : e}${extra}`;
export const entryHref = (termId: string, e?: EditionKey) => `${BASE}/m/${encodeURIComponent(termId)}${e ? `?regions=${e === "ALL" ? "all" : e}` : ""}`;

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
/** "한국판" / "Korea edition" */
export const editionName = (l: Locale, e: EditionKey) => (l === "ko" ? `${regionName(l, e)}판` : `${regionName(l, e)} edition`);

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

  // 커버
  coverWhy: "지금 쓰이는 밈 가운데 가장 널리 퍼지고 가장 최근까지 쓰인 말이라 커버에 올렸습니다.",
  coverWhyFading: (ed: string) => `${ed}에서 지금 쓰이는 밈으로 확인된 것이 없어, 식어 가는 밈 가운데 가장 최근까지 쓰인 말을 올렸습니다.`,
  usedRecently: (d: string) => `${d}에도 쓰인 말입니다.`,
  usedLast: (d: string) => `마지막으로 쓰인 것은 ${d}입니다.`,
  peakNow: (age: string, d: string) => `${age}의 네이버 검색은 ${d}에 지난 6개월 중 가장 많았습니다.`,
  riseNow: (age: string, pct: string) => `${age} 검색은 최근 4주가 그 전 4주보다 ${pct} 많습니다.`,
  make: "이 밈으로 만들기",
  readEntry: "자세히 읽기",
  curveCaption: (age: string, from: string, to: string) => `${age} 네이버 검색 관심, ${from}부터 ${to}까지. 가장 많이 찾은 날을 100으로 본 값입니다.`,
  curvePeak: (d: string) => `${d} 최고`,
  emptyCoverTitle: (ed: string) => `${ed}에 커버로 올릴 밈이 없습니다`,
  emptyCoverBody: "이 지역에서 뜻과 쓰임을 확인한 밈이 아직 없습니다. 확인을 마친 밈부터 여기에 싣습니다. 그동안 다른 판을 보거나, 이 지역에서 검색이 몰린 말을 아래에서 보세요.",
  emptyCoverQuiet: "이 지역에서 뜻과 쓰임을 확인한 밈이 아직 없고, 최근 7일 동안 검색이 몰린 말도 없습니다. 확인을 마친 밈부터 여기에 싣습니다. 그동안 다른 판을 보세요.",
  emptyCoverAvoidOnly: (n: number) => `이 지역에서 확인한 밈 ${n}개가 모두 사용 자제 밈이라 커버에 올리지 않았습니다. 아래 ‘브랜드는 조심’에서 무엇을 피해야 하는지 보세요.`,
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
    negative: (p: number) => `쓰인 글의 ${p}%가 비꼬거나 불쾌한 말투입니다.`,
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
  rubricRisingNote: "널리 퍼진 말부터, 같으면 가장 최근에 쓰인 말부터 싣습니다. 주의 표시가 붙은 밈도 여기 함께 있습니다.",
  rubricSearch: "요즘 더 찾는 밈",
  rubricSearchNote: "네이버에서 최근 4주 검색이 그 전 4주보다 늘어난 밈입니다. 나이대마다 따로 세고, 절반이 넘는 나이대에서 늘어난 것만 싣습니다. 검색이 늘었다고 다시 유행하는 것은 아닙니다. 뜻을 찾아보는 사람이 늘었다는 뜻일 수 있습니다.",
  rubricFading: "식어 가는 밈",
  rubricFadingNote: "쓰임이 줄었거나, 12주 동안 언급 없이 마지막 쓰임이 90일을 넘은 말입니다. 새 캠페인보다는 옛 감성을 일부러 살릴 때 씁니다.",
  rubricCaution: "브랜드는 조심",
  rubricCautionNote: "사용 자제 밈을 먼저 싣습니다. 주의 밈은 위 목록에도 표시와 함께 있고, 사용 자제 밈은 여기에만 있습니다.",
  countLine: (shown: number, total: number) => (shown < total ? `${total}개 가운데 ${shown}개` : `${total}개`),
  seeAll: (n: number) => `${n}개 모두 보기`,
  agesUp: (up: number, valid: number) => `${valid}개 나이대 가운데 ${up}곳에서 늘었습니다.`,
  windowEnd: (d: string) => `${d}까지 4주`,
  thin: "자료 부족",
  ageStripLabel: (name: string) => `${name} 나이대별 검색 변화`,
  rankLabel: (n: number) => `${n}위`,

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
  whoPeak: (age: string, d: string) => `${age}가 ${d}에 가장 많이 찾았습니다`,
  whoNone: "네이버 검색 자료 없음",

  // 찾기
  searchTitle: "찾기",
  searchResults: (q: string, n: number) => `‘${q}’ 검색 결과 ${n}개`,
  searchEmpty: (q: string) => `‘${q}’은(는) 아직 사전에 없습니다. 철자를 바꾸거나 뜻에 들어갈 낱말로 찾아보세요.`,
  searchHint: "밈 이름, 다른 표기, 뜻에 들어간 낱말로 찾을 수 있습니다.",
  searchFailed: "사전을 불러오지 못했습니다. 데이터 서버가 답하지 않습니다.",

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

  coverWhy: "On the cover because it is the most widely spread meme in use now, and the most recently used.",
  coverWhyFading: (ed: string) => `No meme is confirmed as in use in the ${ed} yet, so the cover is the most recently used meme among those cooling off.`,
  usedRecently: (d: string) => `It was still in use on ${d}.`,
  usedLast: (d: string) => `It was last used on ${d}.`,
  peakNow: (age: string, d: string) => `Naver searches by people in their ${age} hit a six-month high on ${d}.`,
  riseNow: (age: string, pct: string) => `Searches by people in their ${age} are up ${pct} over the previous four weeks.`,
  make: "Make something with this meme",
  readEntry: "Read the full entry",
  curveCaption: (age: string, from: string, to: string) => `Naver search interest, people in their ${age}, ${from} to ${to}. The busiest day is 100.`,
  curvePeak: (d: string) => `High on ${d}`,
  emptyCoverTitle: (ed: string) => `No cover for the ${ed} this week`,
  emptyCoverBody: "No meme from this market has had its meaning and use confirmed yet. Memes appear here once they are checked. Meanwhile, open another edition or see below what people here searched for suddenly.",
  emptyCoverQuiet: "No meme from this market has had its meaning and use confirmed yet, and no search spiked here in the last 7 days. Memes appear here once they are checked. Meanwhile, open another edition.",
  emptyCoverAvoidOnly: (n: number) => `All ${n} confirmed meme${n === 1 ? " here is one" : "s here are ones"} to avoid, so there is no cover. See “Brands, take care” below for what to steer clear of.`,
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
    negative: (p: number) => `${p}% of the posts use it in a sarcastic or unpleasant tone.`,
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
  rubricRisingNote: "Most widely spread first, then most recently used. Memes flagged for caution are listed here too, with their flag.",
  rubricSearch: "Searched more lately",
  rubricSearchNote: "Memes whose Naver searches in the last four weeks beat the four weeks before. Each age group is counted on its own, and a meme is listed only when more than half of the age groups rose. More searches do not mean a comeback; more people may simply be looking it up.",
  rubricFading: "Cooling off",
  rubricFadingNote: "Used less, or not mentioned for 12 weeks and last used over 90 days ago. Better for deliberate throwback humour than a new campaign.",
  rubricCaution: "Brands, take care",
  rubricCautionNote: "Memes to avoid come first. Caution memes also appear in the lists above with their flag; memes to avoid appear only here.",
  countLine: (shown: number, total: number) => (shown < total ? `${shown} of ${total}` : `${total}`),
  seeAll: (n: number) => `See all ${n}`,
  agesUp: (up: number, valid: number) => `Up in ${up} of ${valid} age groups.`,
  windowEnd: (d: string) => `Four weeks to ${d}`,
  thin: "Too little data",
  ageStripLabel: (name: string) => `Search change by age group for ${name}`,
  rankLabel: (n: number) => `No. ${n}`,

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

/** 목록용 테이프 — 보통 하나. 퍼진 정도와 생애주기가 서로 다른 쪽을 말하면(식상해졌는데 쓰임은 느는 중) 둘 다 보인다. */
export function listTapes(l: Locale, s: StageInput): { text: string; tone: TapeTone }[] {
  const main = stageTape(l, s);
  const c = copy(l);
  const dt = s.diffusion ? stageTone(s.diffusion) : null;
  if (s.diffusion && dt && dt !== main.tone && main.tone !== "unknown" && (dt === "rise" || dt === "fade" || main.tone === "rise" || main.tone === "fade")) {
    const d = { text: c.diffusion[s.diffusion] ?? s.diffusion, tone: dt };
    return d.text === main.text ? [main] : [d, main];
  }
  return [main];
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
 *  데이터 방침(09-29): 커뮤니티 글의 제목·인용·사이트 이름은 화면에 내지 않는다 — 알아보는 틀만 옮기고, 모르는 틀은 버린다. */
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

const WIDE = /[ᄀ-ᇿ㄰-㆏가-힣぀-ヿ㐀-鿿豈-﫿！-｠]/;
const THAI_MARK = /[ัิ-ฺ็-๎]/;      // 태국 글자의 위·아래 붙는 표시는 폭이 없다
const NO_LINE_START = /^[、。，．・ー〜！？）」』】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ]/;

function charEm(ch: string): number {
  if (WIDE.test(ch)) return 1;
  if (THAI_MARK.test(ch)) return 0;
  if (/[฀-๿]/.test(ch)) return 0.62;
  if (/\s/.test(ch)) return 0.28;
  if (/[A-Z]/.test(ch)) return 0.7;
  if (/[a-z]/.test(ch)) return /[ilj]/.test(ch) ? 0.28 : /[mw]/.test(ch) ? 0.86 : 0.56;
  if (/[0-9]/.test(ch)) return 0.6;
  return 0.36;
}

/** 굵은 글씨(900)에 자간을 좁혔을 때 한 줄의 대략 폭(em). 넘치지 않게 조금 넉넉히 잡는다. */
export function emWidth(s: string, tracking = -0.04): number {
  let w = 0;
  for (const ch of s) {
    const e = charEm(ch);
    if (e) w += e + tracking;
  }
  return w * 1.04;
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

export interface AgeTrend {
  gen: string;
  change: number | null;       // 최근 4주 / 그 전 4주 − 1. 한 창에 20일 미만이면 null(자료 부족)
  end: string | null;          // 곡선의 마지막 날
  peak: string | null;         // 가장 많이 찾은 날
  points: [string, number][];  // 날짜순
}

const DAY = 86_400_000;
const WINDOW = 28;
const MIN_DAYS = 20;

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
  const change = na >= MIN_DAYS && nb >= MIN_DAYS && b > 0 ? a / b - 1 : null;
  return { gen: c.generation, change, end, peak: c.peak_date ?? null, points };
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
export const searchedMore = (s: SearchSummary | null): s is SearchSummary =>
  !!s && s.valid >= 3 && s.up > s.valid / 2 && (s.median ?? 0) >= UP;

/** 커버의 곡선 — 가장 최근에 정점을 찍은 나이대(지금 가장 뜨거운 나이대). 자료가 모자란 나이대는 뺀다. */
export function hottestAge(s: SearchSummary | null): AgeTrend | null {
  if (!s) return null;
  const withData = s.ages.filter((a) => a.points.length >= 60 && a.peak);
  return withData.sort((a, b) => (b.peak ?? "").localeCompare(a.peak ?? "") || (b.change ?? -9) - (a.change ?? -9))[0] ?? null;
}

/** "+48%" / "−13%" (빼기는 진짜 빼기표) */
export function pct(v: number): string {
  const n = Math.round(v * 100);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n)}%`;
}

/* ── 근거·영상 ──────────────────────────────────────────────────────────── */

/** 화면에 내는 출처는 참고 위키·기사·영상만. 커뮤니티 글과 검색 통계 행은 내지 않는다(데이터 방침 09-29). */
const REFERENCE = /(^|\.)((\w+\.)?wikipedia\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net|wiktionary\.org|nicovideo\.jp|wikiwiki\.jp)$/i;
const hostOf = (url: string) => { try { return new URL(url).hostname; } catch { return ""; } };
const hasPath = (url: string) => { try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; } };

export function visibleSource(e: { kind: string; url: string; source_domain?: string | null }): boolean {
  if (!e.url || !hasPath(e.url)) return false;                  // 홈페이지 주소뿐인 것은 근거가 아니다
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

/** 뜻 한 줄 — 카드의 화면 언어 뜻. 영어가 없으면 한국어(그때는 lang="ko") */
export function glossOf(l: Locale, c: Pick<KeywordCard, "gloss_ko" | "gloss_en">): { text: string; lang?: string } {
  if (l === "en") return c.gloss_en ? { text: c.gloss_en } : { text: c.gloss_ko, lang: "ko" };
  return c.gloss_ko ? { text: c.gloss_ko } : { text: c.gloss_en, lang: "en" };
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
