/* 시안 n-redesign 예시 데이터 — 실데이터의 표제어·출처를 손으로 옮겼다. 화면은 이 파일만 읽는다(백엔드 호출 없음).
   표제어 원문은 번역하지 않는다: word + lang 으로 보관하고, 뜻(gloss)만 화면 언어(한국어)로 둔다. */

export type Stage = "emerging" | "rising" | "peak" | "steady" | "declining" | "dormant";
export type Spread = "underground" | "spreading" | "mainstream" | "fading";
export type Risk = "none" | "caution" | "avoid" | "unknown";
export type Prov = "rule" | "model" | "human";

export const STAGE: Record<Stage, string> = {
  emerging: "막 생김", rising: "뜨는 중", peak: "정점", steady: "꾸준함", declining: "식는 중", dormant: "잠잠함",
};
export const STAGE_ORDER: Stage[] = ["emerging", "rising", "peak", "steady", "declining", "dormant"];
export const SPREAD: Record<Spread, string> = {
  underground: "일부만 씀", spreading: "번지는 중", mainstream: "누구나 앎", fading: "잊히는 중",
};
export const RISK: Record<Risk, string> = {
  none: "문제 없음", caution: "조심해서", avoid: "쓰지 않음", unknown: "근거 부족",
};

export type Market = { code: string; name: string; en: string; lang: string; words: number; note?: string };
export const MARKETS: Market[] = [
  { code: "KR", name: "한국", en: "Korea", lang: "ko", words: 684 },
  { code: "JP", name: "일본", en: "Japan", lang: "ja", words: 40 },
  { code: "TW", name: "대만", en: "Taiwan", lang: "zh-Hant", words: 23 },
  { code: "HK", name: "홍콩", en: "Hong Kong", lang: "zh-Hant", words: 12 },
  { code: "TH", name: "태국", en: "Thailand", lang: "th", words: 9 },
  { code: "VN", name: "베트남", en: "Vietnam", lang: "vi", words: 15 },
  { code: "ID", name: "인도네시아", en: "Indonesia", lang: "id", words: 31 },
  { code: "PH", name: "필리핀", en: "Philippines", lang: "en", words: 212, note: "영어 사전 함께" },
  { code: "MY", name: "말레이시아", en: "Malaysia", lang: "ms", words: 64, note: "영어 사전 함께" },
  { code: "SG", name: "싱가포르", en: "Singapore", lang: "en", words: 238, note: "영어 사전 함께" },
];
export const market = (code: string) => MARKETS.find((m) => m.code === code) ?? MARKETS[0];

export const CATEGORIES = [
  "음식·음료", "패션·뷰티", "테크·앱", "게임", "방송·음악", "여행", "금융", "건강·운동", "교육", "생활",
] as const;
export const TONES = [
  { id: "friendly", name: "친근하게", hint: "친구에게 권하듯" },
  { id: "witty", name: "재치 있게", hint: "한 번 웃게" },
  { id: "premium", name: "고급스럽게", hint: "말수를 줄여" },
] as const;

/* ---------- 말(표제어) ---------- */

export type Word = {
  id: string; word: string; lang: string; markets: string[]; gloss: string;
  stage: Stage; spread: Spread; risk: Risk; riskWhy?: string;
  mentions: number; spark: number[]; lastUsed: string; detail?: boolean;
};

const W = (
  id: string, word: string, lang: string, markets: string[], gloss: string,
  stage: Stage, spread: Spread, risk: Risk, mentions: number, spark: number[], lastUsed: string,
  extra: Partial<Word> = {},
): Word => ({ id, word, lang, markets, gloss, stage, spread, risk, mentions, spark, lastUsed, ...extra });

export const WORDS: Word[] = [
  // 한국
  W("jangwonyoung", "장원영 같다", "ko", ["KR"], "흠잡을 데 없이 완벽하고 예쁘다. '밤티'의 반대말", "peak", "mainstream", "none", 1840,
    [12, 18, 22, 30, 41, 58, 77, 96, 120, 151, 168, 174], "2026-10-05", { detail: true }),
  W("bamti", "밤티", "ko", ["KR"], "어설프고 촌스럽다. 만든 사람을 깎아내리는 말로도 쓴다", "rising", "spreading", "caution", 1120,
    [8, 10, 14, 19, 27, 33, 45, 58, 70, 88, 96, 104], "2026-10-05", { detail: true, riskWhy: "남의 외모·작품을 깎아내리는 맥락이 많다" }),
  W("luckyvicky", "럭키비키", "ko", ["KR", "TW"], "나쁜 일도 좋은 일로 바꿔 생각하기", "declining", "fading", "none", 410,
    [160, 171, 158, 140, 122, 101, 88, 74, 62, 51, 44, 39], "2026-10-02", { detail: true }),
  W("chugumi", "추구미", "ko", ["KR"], "닮고 싶은 분위기·스타일", "steady", "mainstream", "none", 960,
    [70, 72, 75, 74, 80, 78, 82, 79, 84, 81, 83, 80], "2026-10-05"),
  W("osalhim", "오살힘", "ko", ["KR"], "오늘을 살게 하는 힘. 좋아하는 것을 가리킬 때", "emerging", "underground", "unknown", 88,
    [0, 0, 0, 1, 1, 2, 3, 3, 5, 7, 9, 12], "2026-10-04"),
  W("junggeokma", "중꺾마", "ko", ["KR"], "중요한 건 꺾이지 않는 마음", "dormant", "fading", "none", 64,
    [18, 15, 14, 12, 11, 9, 8, 8, 7, 6, 6, 5], "2026-09-21"),
  W("mugunghwa", "무궁화 꽃이 피었습니다", "ko", ["KR", "US", "ID", "JP"], "술래가 돌아볼 때 멈추는 놀이. <오징어 게임>으로 전 세계에 알려짐", "steady", "mainstream", "none", 530,
    [40, 42, 39, 44, 43, 41, 45, 44, 42, 46, 44, 45], "2026-10-03", { detail: true }),
  W("oshikatsu", "推し活", "ja", ["JP", "KR", "TW"], "좋아하는 아이돌·캐릭터를 응원하는 모든 활동", "peak", "mainstream", "none", 420,
    [20, 24, 28, 31, 35, 38, 40, 41, 43, 42, 44, 43], "2026-10-05", { detail: true }),
  W("godsaeng", "갓생", "ko", ["KR"], "부지런하고 계획적으로 사는 삶", "steady", "mainstream", "none", 780,
    [60, 62, 64, 61, 63, 65, 64, 66, 63, 65, 64, 66], "2026-10-05"),
  W("kkuankku", "꾸안꾸", "ko", ["KR"], "꾸민 듯 안 꾸민 듯", "steady", "mainstream", "none", 450,
    [38, 36, 37, 39, 38, 37, 36, 38, 37, 39, 38, 37], "2026-10-04"),
  W("kingbatne", "킹받네", "ko", ["KR"], "몹시 약오르다", "declining", "fading", "none", 210,
    [40, 38, 36, 33, 30, 27, 24, 22, 20, 18, 17, 16], "2026-10-01"),
  W("formmichyeotda", "폼 미쳤다", "ko", ["KR"], "실력·상태가 최고다", "steady", "mainstream", "none", 520,
    [44, 45, 43, 46, 45, 44, 46, 45, 47, 44, 46, 45], "2026-10-05"),
  W("neoTya", "너 T야?", "ko", ["KR"], "공감 없이 사실만 말하는 사람에게", "declining", "mainstream", "caution", 300,
    [52, 50, 48, 44, 40, 36, 33, 30, 28, 26, 24, 22], "2026-10-03", { riskWhy: "상대를 몰아세우는 말로 읽힐 수 있다" }),
  W("aboha", "아보하", "ko", ["KR"], "아주 보통의 하루", "rising", "spreading", "none", 340,
    [4, 6, 9, 12, 15, 19, 22, 26, 29, 31, 34, 36], "2026-10-05"),
  W("texthip", "텍스트힙", "ko", ["KR"], "책 읽기·글쓰기가 멋있다는 흐름", "rising", "spreading", "none", 290,
    [6, 8, 10, 13, 15, 18, 21, 23, 25, 27, 28, 30], "2026-10-04"),
  W("teulttak", "틀딱", "ko", ["KR"], "노인을 낮잡아 부르는 말", "steady", "mainstream", "avoid", 610,
    [50, 52, 49, 51, 50, 53, 51, 50, 52, 51, 50, 52], "2026-10-05", { riskWhy: "세대 비하" }),
  W("eojjeoltv", "어쩔티비", "ko", ["KR"], "어쩌라고(장난스럽게)", "dormant", "fading", "none", 40,
    [14, 12, 11, 9, 8, 7, 6, 5, 5, 4, 4, 3], "2026-09-18"),
  W("dopamine", "도파민", "ko", ["KR"], "자극적이고 짜릿한 것", "steady", "mainstream", "none", 700,
    [58, 60, 59, 61, 60, 58, 62, 60, 61, 59, 60, 61], "2026-10-05"),
  // 일본
  W("kaerika", "蛙化現象", "ja", ["JP"], "좋아하던 사람의 사소한 행동에 갑자기 정이 떨어짐", "steady", "mainstream", "none", 210,
    [18, 19, 17, 18, 20, 19, 18, 17, 19, 18, 17, 18], "2026-10-04"),
  W("chirui", "チルい", "ja", ["JP"], "느긋하고 편안하다", "steady", "mainstream", "none", 160,
    [14, 13, 14, 15, 14, 13, 14, 15, 13, 14, 13, 14], "2026-10-03"),
  W("shikakatan", "〜しか勝たん", "ja", ["JP"], "~가 최고다, ~밖에 없다", "declining", "fading", "none", 70,
    [12, 11, 10, 9, 8, 8, 7, 6, 6, 5, 5, 4], "2026-09-30"),
  W("taipa", "タイパ", "ja", ["JP"], "시간 대비 효율", "rising", "spreading", "none", 140,
    [5, 6, 7, 8, 9, 10, 11, 12, 12, 13, 14, 15], "2026-10-05"),
  W("kaiwai", "界隈", "ja", ["JP"], "~쪽 사람들, ~ 판", "rising", "spreading", "none", 120,
    [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13], "2026-10-04"),
  W("pien", "ぴえん", "ja", ["JP"], "울먹이는 마음(귀엽게)", "dormant", "fading", "none", 30,
    [8, 7, 6, 6, 5, 4, 4, 3, 3, 3, 2, 2], "2026-09-12"),
  W("darumasan", "だるまさんがころんだ", "ja", ["JP"], "'무궁화 꽃이 피었습니다'의 일본 놀이 이름", "steady", "mainstream", "none", 60,
    [5, 5, 6, 5, 5, 6, 5, 5, 6, 5, 5, 5], "2026-10-01"),
  // 태국
  W("pang", "ปัง", "th", ["TH"], "대박이다, 잘 터졌다", "steady", "mainstream", "none", 90,
    [8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8], "2026-10-04"),
  W("tuamum", "ตัวมัม", "th", ["TH"], "멋지고 당당한 사람", "peak", "mainstream", "none", 75,
    [2, 3, 4, 5, 6, 6, 7, 7, 8, 8, 8, 8], "2026-10-05"),
  W("jueng", "จึ้ง", "th", ["TH"], "눈부시게 예쁘다", "rising", "spreading", "none", 40,
    [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6], "2026-10-03"),
  W("tach", "ต๊าช", "th", ["TH"], "끝내준다", "steady", "mainstream", "none", 35,
    [3, 3, 3, 4, 3, 3, 3, 4, 3, 3, 4, 3], "2026-10-02"),
  W("mongbon", "มองบน", "th", ["TH"], "눈을 치켜뜨다, 어이없다", "steady", "mainstream", "caution", 30,
    [3, 3, 2, 3, 3, 3, 2, 3, 3, 2, 3, 3], "2026-10-01", { riskWhy: "상대를 비웃는 뜻이 섞인다" }),
  W("phueak", "เผือก", "th", ["TH"], "남의 일에 참견하다", "steady", "mainstream", "none", 28,
    [2, 3, 2, 3, 2, 3, 3, 2, 3, 2, 3, 2], "2026-09-30"),
  W("nok", "นก", "th", ["TH"], "사랑이나 기회를 놓치다", "declining", "fading", "none", 14,
    [4, 4, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1], "2026-09-27"),
  W("kaeng", "แกง", "th", ["TH"], "골탕 먹이다", "steady", "spreading", "unknown", 12,
    [1, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1], "2026-09-29"),
  W("sheserve", "ชีเสิร์ฟ", "th", ["TH"], "그녀가 제대로 해냈다", "emerging", "underground", "unknown", 9,
    [0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 3], "2026-10-02"),
  // 인도네시아
  W("lampumerah", "Lampu merah", "id", ["ID"], "'무궁화 꽃이 피었습니다'의 인도네시아 이름", "steady", "mainstream", "none", 120,
    [10, 10, 11, 10, 10, 11, 10, 9, 10, 10, 11, 10], "2026-10-02"),
  W("gabut", "gabut", "id", ["ID"], "할 일 없이 심심하다", "steady", "mainstream", "none", 260,
    [22, 21, 22, 23, 22, 21, 22, 23, 22, 21, 22, 22], "2026-10-05"),
  W("mager", "mager", "id", ["ID"], "움직이기 귀찮다", "steady", "mainstream", "none", 230,
    [19, 20, 19, 18, 19, 20, 19, 18, 19, 20, 19, 19], "2026-10-05"),
  W("salting", "salting", "id", ["ID"], "설레서 어쩔 줄 모르다", "rising", "spreading", "none", 150,
    [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15, 16], "2026-10-05"),
  W("anjay", "anjay", "id", ["ID"], "감탄사. 욕에서 온 말", "steady", "mainstream", "caution", 300,
    [25, 26, 25, 24, 25, 26, 25, 24, 25, 26, 25, 25], "2026-10-05", { riskWhy: "욕에서 왔다는 지적이 있어 공식 계정에는 조심" }),
];

export const wordById = (id: string) => WORDS.find((w) => w.id === id);
export const wordsIn = (code: string) => WORDS.filter((w) => w.markets.includes(code));

export const TODAY = "2026-10-06";

/** '2026-10-05' → '10월 5일' (올해) */
export function day(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return y === 2026 ? `${m}월 ${d}일` : `${y}년 ${m}월 ${d}일`;
}

/* ---------- 표제어 상세 ---------- */

export type Source = { kind: "wiki" | "news" | "video"; title: string; outlet: string; date: string; url: string; quote?: string };
export type Version = { v: number; from: string; to: string | null; text: string; by: string; how: Prov };
export type CountryUse = { code: string; local: string; lang: string; how: string };
export type Detail = {
  reading?: string; meaning: string; origin: string; nuance: string;
  howTo: { ok: string[]; no: string[] };
  riskReasons: string[];
  countries: CountryUse[];
  sources: Source[];
  versions: Version[];
};

export const DETAILS: Record<string, Detail> = {
  jangwonyoung: {
    reading: "jang-won-young gatda",
    meaning: "흠잡을 데 없이 완벽하고 예쁘다는 칭찬. 사람뿐 아니라 음식·물건에도 붙인다. '장원영 라면'은 면이 알맞게 익고 모양까지 완벽한 라면을 말한다.",
    origin: "어설프고 촌스러운 것을 '밤티'라고 부르는 유행이 번지면서, 그 반대편에 늘 완벽해 보이는 아이돌 장원영의 이름이 놓였다.",
    nuance: "가볍고 다정한 칭찬. 실존 인물의 이름이라 그 사람을 깎아내리거나 외모를 평가하는 문장에는 쓰지 않는다.",
    howTo: {
      ok: ["오늘 라떼, 장원영 같다", "장원영 라면 끓이는 법"],
      no: ["사람의 외모를 견주는 문장", "'밤티'와 나란히 놓고 누군가를 깎아내리는 문장"],
    },
    riskReasons: [],
    countries: [
      { code: "KR", local: "장원영 같다", lang: "ko", how: "음식·물건에 붙이는 칭찬으로 가장 많이 쓴다" },
    ],
    sources: [
      { kind: "news", outlet: "연합뉴스TV", title: "\"오늘 라면 장원영 같다\"…'밤티'와 짝을 이룬 신조어", date: "2026-09-22", url: "https://www.yonhapnewstv.co.kr/", quote: "완벽하게 끓인 라면을 '장원영 라면'이라고 부른다" },
      { kind: "news", outlet: "한국경제", title: "MZ 사이 '밤티' 반대말은 '장원영'", date: "2026-09-18", url: "https://www.hankyung.com/" },
      { kind: "wiki", outlet: "나무위키", title: "밤티", date: "2026-10-01", url: "https://namu.wiki/w/%EB%B0%A4%ED%8B%B0", quote: "반대말로 '장원영'이 쓰인다" },
    ],
    versions: [
      { v: 2, from: "2026-09-24", to: null, text: "음식·물건에도 붙이는 칭찬으로 넓힘. '장원영 라면' 예시 추가.", by: "검수자 김태우", how: "human" },
      { v: 1, from: "2026-09-19", to: "2026-09-24", text: "완벽하고 예쁜 사람을 가리키는 말.", by: "검수자 박서연", how: "human" },
    ],
  },
  bamti: {
    reading: "bam-ti",
    meaning: "어설프고 촌스럽다. 기대보다 엉성하게 나온 결과물을 두고 쓴다.",
    origin: "인터넷 방송에서 엉성하게 만든 케이크를 두고 한 말이 짤로 퍼졌다.",
    nuance: "친구끼리는 웃자고 쓰지만, 남이 만든 것이나 외모에 쓰면 깎아내리는 말이 된다.",
    howTo: { ok: ["내가 만든 케이크 완전 밤티"], no: ["남의 작품·외모를 두고", "제품 광고에서 경쟁사를 두고"] },
    riskReasons: ["남의 외모·작품을 깎아내리는 맥락이 많다", "기사 2건이 '조롱' 맥락으로 인용"],
    countries: [{ code: "KR", local: "밤티", lang: "ko", how: "주로 자기 결과물을 낮추는 농담" }],
    sources: [
      { kind: "wiki", outlet: "나무위키", title: "밤티", date: "2026-10-01", url: "https://namu.wiki/w/%EB%B0%A4%ED%8B%B0" },
      { kind: "news", outlet: "한국경제", title: "MZ 사이 '밤티' 반대말은 '장원영'", date: "2026-09-18", url: "https://www.hankyung.com/" },
    ],
    versions: [{ v: 1, from: "2026-09-17", to: null, text: "어설프고 촌스럽다.", by: "검수자 김태우", how: "human" }],
  },
  luckyvicky: {
    reading: "lucky vicky",
    meaning: "나쁜 일이 생겨도 좋은 쪽으로 바꿔 생각하는 태도. '오히려 좋아'의 밝은 버전.",
    origin: "아이브 장원영의 긍정적인 말버릇('원영적 사고')에서 영어 이름 Vicky 를 붙여 만들었다.",
    nuance: "밝고 귀엽다. 다만 2026년 여름 이후 쓰임이 빠르게 줄어 새 캠페인에는 낡아 보일 수 있다.",
    howTo: { ok: ["비가 와서 실내 데이트, 완전 럭키비키잖아"], no: ["실제 사고·재난을 두고"] },
    riskReasons: [],
    countries: [
      { code: "KR", local: "럭키비키", lang: "ko", how: "원래 쓰임" },
      { code: "TW", local: "幸運Vicky", lang: "zh-Hant", how: "K팝 팬 사이에서 소개되듯 쓰인다" },
    ],
    sources: [
      { kind: "wiki", outlet: "나무위키", title: "원영적 사고", date: "2026-08-30", url: "https://namu.wiki/" },
      { kind: "video", outlet: "YouTube Shorts", title: "럭키비키 챌린지 모음", date: "2026-07-14", url: "https://www.youtube.com/" },
    ],
    versions: [{ v: 1, from: "2026-05-02", to: null, text: "나쁜 일도 좋은 일로 바꿔 생각하기.", by: "검수자 박서연", how: "human" }],
  },
  oshikatsu: {
    reading: "oshi-katsu",
    meaning: "좋아하는 아이돌·배우·캐릭터('推し')를 응원하는 모든 활동. 굿즈 사기, 공연 가기, 생일 카페 열기까지.",
    origin: "일본 아이돌 팬덤의 말 '推しメン(밀어주는 멤버)'에서 줄어 '推し', 거기에 활동(活動)이 붙었다.",
    nuance: "사람이나 캐릭터를 향한 응원이 중심이다. 제품 자체를 '推し'로 부르면 뜻이 조금 넓어진다.",
    howTo: { ok: ["推し活のおともに", "推しの誕生日カフェ"], no: ["제품을 사람처럼 '推し'라 부르는 광고는 조심"] },
    riskReasons: [],
    countries: [
      { code: "JP", local: "推し活", lang: "ja", how: "원래 쓰임. 일상어가 됨" },
      { code: "KR", local: "덕질", lang: "ko", how: "같은 뜻으로는 '덕질'을 더 쓴다. '오시카츠'는 일본 팬덤 이야기에서만" },
      { code: "TW", local: "推活", lang: "zh-Hant", how: "한자를 그대로 읽어 쓴다" },
    ],
    sources: [
      { kind: "wiki", outlet: "Wikipedia 日本語", title: "推し", date: "2026-09-10", url: "https://ja.wikipedia.org/wiki/%E6%8E%A8%E3%81%97" },
      { kind: "news", outlet: "NHK", title: "広がる「推し活」市場", date: "2026-08-21", url: "https://www3.nhk.or.jp/" },
    ],
    versions: [{ v: 1, from: "2026-08-25", to: null, text: "좋아하는 대상을 응원하는 활동.", by: "검수자 김태우", how: "human" }],
  },
  mugunghwa: {
    reading: "mu-gung-hwa kko-chi pi-eot-seum-ni-da",
    meaning: "술래가 이 말을 외치고 돌아볼 때 움직이면 걸리는 놀이. 드라마 <오징어 게임>의 첫 게임으로 전 세계에 알려졌다.",
    origin: "한국의 어린이 놀이. 같은 놀이가 나라마다 다른 이름으로 있다.",
    nuance: "멈췄다 움직이는 순간, 긴장감을 빌릴 때 쓴다. 드라마 속 장면은 탈락이 죽음이라 가볍게 쓰면 어색할 수 있다.",
    howTo: { ok: ["무궁화 꽃이 피었습니다, 하고 딱 멈춘 순간의 맛"], no: ["탈락·죽음 장면을 그대로 흉내 내는 광고"] },
    riskReasons: [],
    countries: [
      { code: "KR", local: "무궁화 꽃이 피었습니다", lang: "ko", how: "원래 놀이 이름" },
      { code: "US", local: "Red Light, Green Light", lang: "en", how: "영어권의 같은 놀이 이름으로 번역되어 퍼짐" },
      { code: "ID", local: "Lampu merah", lang: "id", how: "'빨간불'. 드라마 이후 놀이 이름처럼 쓰인다" },
      { code: "JP", local: "だるまさんがころんだ", lang: "ja", how: "일본에 원래 있던 같은 놀이" },
    ],
    sources: [
      { kind: "wiki", outlet: "Wikipedia", title: "Red Light, Green Light", date: "2026-09-02", url: "https://en.wikipedia.org/wiki/Red_light,_green_light" },
      { kind: "wiki", outlet: "나무위키", title: "무궁화 꽃이 피었습니다", date: "2026-08-11", url: "https://namu.wiki/" },
      { kind: "video", outlet: "Netflix (YouTube)", title: "Squid Game — Red Light, Green Light", date: "2025-12-26", url: "https://www.youtube.com/" },
    ],
    versions: [
      { v: 2, from: "2026-01-05", to: null, text: "나라별 놀이 이름(미국·인도네시아·일본) 추가.", by: "검수자 박서연", how: "human" },
      { v: 1, from: "2021-10-04", to: "2026-01-05", text: "술래잡기의 한 가지.", by: "검수자 박서연", how: "human" },
    ],
  },
};

/* ---------- 만들기 결과(시장별 초안) ---------- */

export type Issue = { code: "avoid" | "caution" | "undecided" | "fading" | "not_in_region" | "no_script"; note?: string };
export const ISSUE: Record<Issue["code"], string> = {
  avoid: "쓰지 않는 말", caution: "조심해서 쓸 말", undecided: "근거가 아직 부족", fading: "식는 중",
  not_in_region: "이 시장에서 안 쓰임", no_script: "현지 표기 없음",
};
export type Copy = { platform: "Instagram" | "X"; text: string; mark?: string; tags?: string[]; issues: Issue[]; fit: "ok" | "drift" | null; fitNote?: string };
export type Pick = { rule: string; effect: string };
export type Excluded = { id?: string; word: string; lang: string; why: string; kind: Risk | "fading" | "mismatch" };
export type Draft = {
  market: string; lang: string;
  meme: { id: string; word: string; lang: string; gloss: string } | null;
  candidates: number; considered: number;
  picks: Pick[]; excluded: Excluded[];
  copies: Copy[];
  poster: { headline: string; sub: string };
  script?: { title: string; seconds: number; scenes: { t: string; visual: string; caption: string }[] };
  thumb?: { headline: string; layout: string };
  approval: { state: "approved" | "pending"; by?: string; at?: string };
  modelCalls: number; model: string; thin?: string;
};

export const BRIEF = {
  product: "여름 한정 아이스 흑당 라떼",
  pitch: "진한 흑당 시럽에 얼음을 가득 채운, 8월 31일까지만 파는 라떼",
  category: "음식·음료", tone: "witty" as const, markets: ["KR", "JP", "TH"],
  runAt: "2026-10-06 14:12",
};

export const DRAFTS: Draft[] = [
  {
    market: "KR", lang: "ko", candidates: 684, considered: 12, modelCalls: 2, model: "Gemini 3.8 Flash",
    meme: { id: "jangwonyoung", word: "장원영 같다", lang: "ko", gloss: "흠잡을 데 없이 완벽하다. 음식에도 쓴다" },
    picks: [
      { rule: "분야 겹침", effect: "음식에 붙여 쓰는 예가 많음" },
      { rule: "느낌 겹침", effect: "'완벽함'이 제품 설명과 같음" },
      { rule: "퍼진 정도", effect: "누구나 앎" },
      { rule: "생애주기", effect: "정점, 4주 언급 1,840회" },
      { rule: "브랜드 리스크", effect: "문제 없음" },
    ],
    excluded: [
      { id: "bamti", word: "밤티", lang: "ko", why: "뜻이 반대(어설픔). 남을 깎아내리는 맥락이 많다", kind: "caution" },
      { id: "luckyvicky", word: "럭키비키", lang: "ko", why: "12주 동안 언급이 4분의 1로 줄었다", kind: "fading" },
      { id: "teulttak", word: "틀딱", lang: "ko", why: "세대 비하", kind: "avoid" },
    ],
    copies: [
      { platform: "Instagram", text: "오늘 라떼, 장원영 같다. 흑당은 진하게, 얼음은 가득. 8월 31일까지만 만나요.", tags: ["여름한정", "흑당라떼"], issues: [], fit: "ok", fitNote: "음식을 완벽하다고 칭찬하는 원래 쓰임과 같다" },
      { platform: "Instagram", text: "흑당 비율이 완벽하면 그건 장원영 라떼. 한 모금이면 알아요.", tags: ["장원영라떼"], issues: [], fit: "ok", fitNote: "'장원영 라면'과 같은 꼴" },
      { platform: "X", text: "흑당 진하게 얼음 가득, 오늘 라떼 장원영 같다", issues: [], fit: "ok" },
      { platform: "X", text: "여름 한정이라 더 아까운 장원영 같은 한 잔. 8월 31일까지", issues: [], fit: "ok" },
    ],
    poster: { headline: "오늘 라떼, 장원영 같다", sub: "여름 한정 아이스 흑당 라떼, 8월 31일까지" },
    script: {
      title: "장원영 라떼 15초", seconds: 15, scenes: [
        { t: "0–4초", visual: "더운 오후, 컵에 얼음이 가득 채워진다", caption: "오후 3시" },
        { t: "4–10초", visual: "흑당 시럽이 천천히 번진다", caption: "흑당은 진하게" },
        { t: "10–15초", visual: "완성된 잔을 위에서", caption: "오늘 라떼, 장원영 같다" },
      ],
    },
    thumb: { headline: "장원영 라떼", layout: "제품을 왼쪽 3분의 1, 문구는 오른쪽 두 줄" },
    approval: { state: "approved", by: "김태우", at: "10월 6일 14:20" },
  },
  {
    market: "JP", lang: "ja", candidates: 40, considered: 6, modelCalls: 2, model: "Gemini 3.8 Flash",
    meme: { id: "oshikatsu", word: "推し活", lang: "ja", gloss: "좋아하는 대상을 응원하는 활동" },
    picks: [
      { rule: "분야 겹침", effect: "카페·굿즈와 함께 쓰는 예가 많음" },
      { rule: "퍼진 정도", effect: "누구나 앎" },
      { rule: "생애주기", effect: "정점" },
      { rule: "브랜드 리스크", effect: "문제 없음" },
    ],
    excluded: [
      { word: "ぴえん", lang: "ja", why: "잠잠함. 마지막 쓰임 9월 12일", kind: "fading" },
      { word: "蛙化現象", lang: "ja", why: "연애 맥락이라 음료와 느낌이 겹치지 않는다", kind: "mismatch" },
    ],
    copies: [
      { platform: "Instagram", text: "推し活の合間に、ひと休み。夏だけのアイス黒糖ラテ。", tags: ["夏限定", "黒糖ラテ"], issues: [], fit: "ok", fitNote: "응원 활동 사이의 쉼이라 원래 쓰임 안" },
      { platform: "Instagram", mark: "推し", text: "推しを語るなら、冷たい黒糖ラテを片手に。8月31日まで。", tags: ["推し活"], issues: [], fit: "ok" },
      { platform: "X", text: "推し活のおともに、夏限定の黒糖ラテ", issues: [], fit: "ok" },
      { platform: "X", mark: "推し", text: "今日の推しは、このラテ。", issues: [{ code: "caution", note: "제품을 '推し'로 부름" }], fit: "drift", fitNote: "'推し'는 사람·캐릭터를 향한 말이라 제품에 쓰면 뜻이 넓어진다. 검수자가 판단할 것" },
    ],
    poster: { headline: "推し活の合間に、ひと休み。", sub: "夏限定 アイス黒糖ラテ" },
    approval: { state: "pending" },
  },
  {
    market: "TH", lang: "th", candidates: 9, considered: 9, modelCalls: 1, model: "Gemini 3.8 Flash",
    meme: null,
    thin: "태국 사전에 확인된 말이 9개뿐이고, 이 제품에 맞는 말이 없어 밈 없이 썼습니다. 맞지 않는 밈을 억지로 넣지 않습니다.",
    picks: [],
    excluded: [
      { word: "ปัง", lang: "th", why: "제품 출시보다 '대박 난 결과'에 쓰는 말이라 느낌이 겹치지 않는다", kind: "mismatch" },
      { word: "มองบน", lang: "th", why: "비웃는 뜻이 섞인다", kind: "caution" },
      { word: "ชีเสิร์ฟ", lang: "th", why: "근거 문서가 아직 1건", kind: "unknown" },
    ],
    copies: [
      { platform: "Instagram", text: "ลาเต้น้ำตาลทรายแดงเย็นฉ่ำ มีแค่หน้าร้อนนี้เท่านั้น", tags: ["ลาเต้เย็น"], issues: [], fit: null },
      { platform: "Instagram", text: "หวานเข้ม เย็นชื่นใจ ถึง 31 ส.ค. นี้", issues: [], fit: null },
      { platform: "X", text: "ลาเต้น้ำตาลทรายแดงเย็น เฉพาะหน้าร้อน", issues: [], fit: null },
      { platform: "X", text: "หมดหน้าร้อนก็หมดแก้วนี้", issues: [], fit: null },
    ],
    poster: { headline: "ลาเต้น้ำตาลทรายแดงเย็น", sub: "เฉพาะหน้าร้อนนี้ ถึง 31 ส.ค." },
    approval: { state: "pending" },
  },
];
