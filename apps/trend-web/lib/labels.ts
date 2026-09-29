/* 데이터 값 → 사용자 언어 라벨. 내부 용어(에이전트·게이트·모델)는 화면에 내지 않는다. */
import type { TrendCategory } from "./trends/types";
import type { Locale } from "./i18n";
import type { CampaignTone, Category, EvidenceKind, Feeling, FitCategory, Generation, Lifecycle, TermStatus, Verification } from "./types";

interface Labels {
  generation: Record<Generation, string>;
  region: Record<string, string>;
  trendCategory: Record<TrendCategory, string>;
  trigger: Record<string, string>;
  lifecycle: Record<Lifecycle, string>;
  lifecycleSentence: Record<Lifecycle, string>;
  verification: Record<Verification, string>;
  termStatus: Record<TermStatus, string>;
  category: Record<Category, string>;
  evidenceKind: Record<EvidenceKind, string>;
  feeling: Record<Feeling, string>;
  fitCategory: Record<FitCategory, string>;
  campaignTone: Record<CampaignTone, string>;
  draftLang: Record<string, string>;
}

const ko: Labels = {
  generation: { "10s": "10대", "20s": "20대", "30s": "30대", "40s": "40대", "50s+": "50대 이상", all: "모든 세대" },
  trigger: { influencer: "인플루언서", release: "출시·공개", event: "사건·행사", controversy: "논란", meme: "밈", promotion: "홍보·방송", holiday: "명절·기념일", sports: "경기", unknown: "원인 미확인" },
  trendCategory: { slang_meme: "유행어·밈", song_challenge: "노래·챌린지", fashion_beauty: "패션·뷰티", food: "음식", product: "제품", people_content: "인물·콘텐츠", sports_event: "스포츠·이벤트" },
  region: {
    KR: "한국", JP: "일본", TW: "대만", HK: "홍콩", TH: "태국", VN: "베트남", ID: "인도네시아", PH: "필리핀", MY: "말레이시아",
    SG: "싱가포르", IN: "인도", AU: "호주", US: "미국", CA: "캐나다", GB: "영국", DE: "독일", FR: "프랑스", ES: "스페인", IT: "이탈리아",
    BR: "브라질", MX: "멕시코", CN: "중국", AE: "아랍에미리트", AR: "아르헨티나", TR: "튀르키예", SA: "사우디아라비아", EG: "이집트", NG: "나이지리아", ZA: "남아프리카", GLOBAL: "전 세계",
  },
  lifecycle: { emerging: "새로 퍼지는 중", rising: "늘어나는 중", peak: "가장 많이 쓰이는 시기", steady: "꾸준히 쓰임", declining: "줄어드는 중", dormant: "거의 안 쓰임", unknown: "추세 미확인" },
  lifecycleSentence: { emerging: "요즘 새로 퍼지고 있습니다.", rising: "요즘 점점 더 많이 쓰입니다.", peak: "지금 가장 많이 쓰이는 시기입니다.", steady: "지금도 꾸준히 쓰입니다.", declining: "요즘은 점점 덜 쓰입니다.", dormant: "지금은 거의 쓰지 않습니다.", unknown: "" },
  verification: { verified_human: "확인됨", verified_auto: "확인됨", unverified: "확인 중", rejected: "제외" },
  termStatus: { candidate: "후보", researching: "조사 중", needs_review: "확인 중", verified: "확인됨", retired: "폐기" },
  category: { slang: "유행어", meme: "밈", song: "노래", drama: "드라마", dance: "댄스", news: "뉴스", geopolitics: "시사", product: "제품", other: "기타" },
  evidenceKind: { short: "영상", news: "기사", datalab: "검색 통계", web: "웹", community: "커뮤니티", human: "검수자", wiki: "위키" },
  feeling: { joy: "기쁨", hype: "들뜸", cute: "귀여움", funny: "웃김", relatable: "공감", comfort: "위로", pride: "자부심", surprise: "놀람", sarcasm: "비꼼",
             frustration: "답답함", tired: "지침", romance: "설렘", nostalgia: "추억", cool: "멋짐" },
  fitCategory: { food_drink: "음식·음료", fashion_beauty: "패션·뷰티", tech: "전자기기·앱", game: "게임", entertainment: "공연·영상·음악", travel: "여행",
                 finance: "금융", health_fitness: "건강·운동", education: "교육", lifestyle: "생활용품" },
  campaignTone: { friendly: "친근함", witty: "재치", premium: "고급스러움" },
  draftLang: { ko: "한국어", ja: "일본어", "zh-Hant": "번체 중국어", th: "태국어", vi: "베트남어", id: "인도네시아어", en: "영어", ms: "말레이어" },
};

const en: Labels = {
  generation: { "10s": "teens", "20s": "20s", "30s": "30s", "40s": "40s", "50s+": "50s and older", all: "all ages" },
  trigger: { influencer: "Influencer", release: "Release", event: "Event", controversy: "Controversy", meme: "Meme", promotion: "Promotion / TV", holiday: "Holiday", sports: "Match", unknown: "Cause unknown" },
  trendCategory: { slang_meme: "Slang & memes", song_challenge: "Songs & challenges", fashion_beauty: "Fashion & beauty", food: "Food", product: "Products", people_content: "People & content", sports_event: "Sports & events" },
  region: {
    KR: "Korea", JP: "Japan", TW: "Taiwan", HK: "Hong Kong", TH: "Thailand", VN: "Vietnam", ID: "Indonesia", PH: "Philippines", MY: "Malaysia",
    SG: "Singapore", IN: "India", AU: "Australia", US: "United States", CA: "Canada", GB: "United Kingdom", DE: "Germany", FR: "France", ES: "Spain", IT: "Italy",
    BR: "Brazil", MX: "Mexico", CN: "China", AE: "UAE", AR: "Argentina", TR: "Türkiye", SA: "Saudi Arabia", EG: "Egypt", NG: "Nigeria", ZA: "South Africa", GLOBAL: "worldwide",
  },
  lifecycle: { emerging: "just spreading", rising: "on the rise", peak: "at its peak", steady: "in steady use", declining: "fading", dormant: "rarely used now", unknown: "trend unknown" },
  lifecycleSentence: { emerging: "It is just starting to spread.", rising: "It is being used more and more.", peak: "It is at the height of its use right now.", steady: "It is still in steady use.", declining: "It is used less and less these days.", dormant: "It is rarely used now.", unknown: "" },
  verification: { verified_human: "reviewed", verified_auto: "reviewed", unverified: "under review", rejected: "excluded" },
  termStatus: { candidate: "candidate", researching: "researching", needs_review: "under review", verified: "reviewed", retired: "retired" },
  category: { slang: "slang", meme: "meme", song: "song", drama: "drama", dance: "dance", news: "news", geopolitics: "current affairs", product: "product", other: "other" },
  evidenceKind: { short: "video", news: "article", datalab: "search stats", web: "web", community: "community", human: "reviewer", wiki: "wiki" },
  feeling: { joy: "joy", hype: "hype", cute: "cute", funny: "funny", relatable: "relatable", comfort: "comfort", pride: "pride", surprise: "surprise",
             sarcasm: "sarcasm", frustration: "frustration", tired: "tiredness", romance: "romance", nostalgia: "nostalgia", cool: "cool" },
  fitCategory: { food_drink: "food & drink", fashion_beauty: "fashion & beauty", tech: "tech & apps", game: "games", entertainment: "shows & music",
                 travel: "travel", finance: "finance", health_fitness: "health & fitness", education: "education", lifestyle: "home & lifestyle" },
  campaignTone: { friendly: "Friendly", witty: "Witty", premium: "Premium" },
  draftLang: { ko: "Korean", ja: "Japanese", "zh-Hant": "Traditional Chinese", th: "Thai", vi: "Vietnamese", id: "Indonesian", en: "English", ms: "Malay" },
};

const LABELS: Record<Locale, Labels> = { ko, en };
export const L = (locale: Locale) => LABELS[locale];

/** "20대·30대" / "20s and 30s" */
export function listJoin(locale: Locale, items: string[]) {
  if (locale === "ko" || items.length < 2) return items.join(locale === "ko" ? "·" : ", ");
  return `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}
export const joinGens = (locale: Locale, gens: Generation[]) => listJoin(locale, gens.map((g) => L(locale).generation[g]));
export const joinRegions = (locale: Locale, regions: string[]) => listJoin(locale, regions.map((r) => L(locale).region[r] ?? r));
export const regionLabel = (locale: Locale, code: string) => L(locale).region[code] ?? code;

/* 근거 출처 이름. 수집기가 붙인 코드('naver:blog')를 사람이 읽는 이름으로. 모르는 것은 도메인 그대로.
   커뮤니티·SNS 글은 화면에 내지 않으므로(ADR 0003) 그 사이트 이름은 두지 않는다. */
const SOURCE_NAME: Record<Locale, Record<string, string>> = {
  ko: { "naver:blog": "네이버 블로그", "naver:news": "네이버 뉴스", "datalab.naver.com": "네이버 데이터랩", "trends.google.com": "Google Trends",
        // 사람이 읽는 이름 — 도메인을 그대로 내지 않는다(디자인 개편 검토)
        "namu.wiki": "나무위키", "brunch.co.kr": "브런치", "instagram.com": "Instagram", "youtube.com": "YouTube",
        "wikipedia.org": "위키백과", "ko.wikipedia.org": "위키백과", "en.wikipedia.org": "영어 위키백과", "ja.wikipedia.org": "일본어 위키백과",
        "zh.wikipedia.org": "중국어 위키백과" },
  en: { "naver:blog": "Naver Blog", "naver:news": "Naver News", "datalab.naver.com": "Naver DataLab", "trends.google.com": "Google Trends",
        "namu.wiki": "Namuwiki", "brunch.co.kr": "Brunch", "instagram.com": "Instagram", "youtube.com": "YouTube",
        "wikipedia.org": "Wikipedia", "ko.wikipedia.org": "Korean Wikipedia", "en.wikipedia.org": "Wikipedia", "ja.wikipedia.org": "Japanese Wikipedia",
        "zh.wikipedia.org": "Chinese Wikipedia" },
};
export const sourceName = (locale: Locale, domain: string) => SOURCE_NAME[locale][domain] ?? domain;

/** 용어 원문의 언어 (Term.lang) */
const TERM_LANG: Record<Locale, Record<string, string>> = {
  ko: { ko: "한국어", en: "영어", ja: "일본어", id: "인도네시아어", th: "태국어", vi: "베트남어", zh: "중국어" },
  en: { ko: "Korean", en: "English", ja: "Japanese", id: "Indonesian", th: "Thai", vi: "Vietnamese", zh: "Chinese" },
};
export const termLangLabel = (locale: Locale, code: string) => TERM_LANG[locale][code] ?? code;

export const fmtDate = (iso: string | null | undefined) => (iso ? iso.slice(0, 10).replace(/-/g, ".") : "—");
/** 시각까지. 한국어 화면은 서울 시간, 영어 화면은 UTC 로 고정(서버 렌더와 브라우저가 같은 값을 내야 한다). */
export function fmtDateTime(iso: string | null | undefined, locale: Locale) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const tz = locale === "ko" ? "Asia/Seoul" : "UTC";
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(d);
  const g = (t: string) => parts.find((x) => x.type === t)?.value ?? "";
  return `${g("year")}.${g("month")}.${g("day")} ${g("hour")}:${g("minute")}${locale === "en" ? " UTC" : ""}`;
}
export const fmtInt = (n: number) => n.toLocaleString("en-US");

/* 관리 화면 전용 (한국어) */
export const CREATED_BY: Record<string, string> = { research_agent: "자동 조사", tracking_agent: "자동 추적", human: "검수자" };
export const VERIFICATION_DETAIL: Record<Verification, string> = { verified_human: "확인됨 (검수자)", verified_auto: "확인됨 (자동)", unverified: "확인 중", rejected: "제외" };
