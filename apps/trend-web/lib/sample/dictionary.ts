/* 예시 데이터 — 제품이 완성됐을 때의 사전 상태를 가정. 전부 계약 타입(lib/contract/types.ts)을 따른다.
   실데이터가 붙으면 lib/data.ts 의 분기만 바뀌고 이 파일은 데모·테스트용으로 남는다. */
import type { Diffusion } from "../contract/types";
import type { Locale } from "../i18n";
import type { Evidence, Meaning, MeaningDraft, PipelineStage, ReviewItem, TermRecord, TermUsage, WeeklyPoint } from "../types";
import { KOREAN_2026 } from "./korean-2026";
import { LATEST_2026 } from "./latest-2026";

// 12주 (월요일 시작), 마지막 주 = 2026-09-07
const WEEKS = [
  "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27",
  "2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07",
];
const weekly = (counts: number[]): WeeklyPoint[] => counts.map((count, i) => ({ week_start: WEEKS[i], count }));

const seg = (region: string, generation: Meaning["generations"][number], first_seen: string, share: number): TermUsage => ({
  segment: { segment_id: `${region}-${generation}`, generation, region },
  first_seen,
  share,
});

const ev = (id: string, kind: Evidence["kind"], source_domain: string, title: string, observed_at: string, excerpt: string, url?: string): Evidence => ({
  evidence_id: id,
  kind,
  url: url ?? `https://${source_domain}/`,
  title,
  source_domain,
  observed_at,
  excerpt,
});

const BASE_RECORDS: TermRecord[] = [
  {
    term: { term_id: "t_jamanchu", canonical: "자만추", lang: "ko", aliases: ["자만추파", "자만추하다"], status: "verified", lifecycle: "steady", first_seen: "2019-06-02T00:00:00Z", last_seen: "2026-09-13T21:10:00Z" },
    category: "slang",
    plain: "자연스러운 만남",
    en: { definition: "Preferring to meet a partner naturally in everyday life rather than through blind dates or dating apps.", expansion: "자연스러운 만남 추구 ('seeking natural encounters')", origin: "Emerged in Korean online communities in the late 2010s as the counterpart of 인만추 ('seeking arranged encounters').", nuance: "A neutral way to describe one's dating values. Since 2026 it is also used self-deprecatingly to mean 'there is no natural way to meet anyone anymore', and use among people in their 40s has grown.", plain: "meeting someone naturally" },
    meanings: [
      {
        meaning_id: "m_jamanchu_1", term_id: "t_jamanchu", version: 1,
        definition: "자연스러운 만남을 추구한다는 뜻. 소개팅·데이팅 앱이 아니라 일상에서 자연스럽게 만나는 연애를 선호함을 말한다.",
        expansion: "자연스러운 만남 추구",
        origin: "2010년대 후반 온라인 커뮤니티에서 '인만추(인위적 만남 추구)'와 짝으로 쓰이기 시작.",
        nuance: "연애 가치관을 말하는 중립적 표현. 부정적 뉘앙스 없음.",
        generations: ["20s", "30s"], regions: ["KR"], self_confidence: 0.86, confidence: 0.9,
        verification: "verified_human", valid_from: "2025-11-02T09:00:00Z", valid_to: "2026-08-20T06:00:00Z", created_by: "research_agent",
        citations: ["https://namu.wiki/"],
      },
      {
        meaning_id: "m_jamanchu_2", term_id: "t_jamanchu", version: 2,
        definition: "자연스러운 만남을 추구한다는 뜻. 소개팅·데이팅 앱이 아니라 일상에서 자연스럽게 만나는 연애를 선호함을 말한다.",
        expansion: "자연스러운 만남 추구",
        origin: "2010년대 후반 온라인 커뮤니티에서 '인만추(인위적 만남 추구)'와 짝으로 쓰이기 시작.",
        nuance: "2026년 들어 '자연스럽게 만날 기회가 없다'는 자조적 맥락으로도 쓰임. 40대 사용이 늘며 세대 폭이 넓어졌다.",
        generations: ["20s", "30s", "40s"], regions: ["KR"], self_confidence: 0.81, confidence: 0.82,
        verification: "verified_auto", valid_from: "2026-08-20T06:00:00Z", valid_to: null, created_by: "research_agent",
        citations: ["https://namu.wiki/", "https://n.news.naver.com/"],
      },
    ],
    evidences: [
      ev("e_jam_w1", "wiki", "namu.wiki", "나무위키: 자만추", "2026-09-18T00:00:00Z", "자만추 — 자연스러운 만남 추구", "https://namu.wiki/w/%EC%9E%90%EB%A7%8C%EC%B6%94"),
      ev("e_jam_s1", "short", "youtube.com", "자만추 vs 인만추, 요즘 20대 연애 방식 | 쇼츠", "2026-08-18T12:00:00Z", "\"저는 자만추파라 소개팅 안 나가요\" — 댓글 1.2만, 20대 비율 높음"),
      ev("e_jam_n1", "news", "n.news.naver.com", "MZ 연애 키워드 '자만추'… 데이팅앱 피로감이 낳은 역설", "2026-07-30T02:00:00Z", "자만추(자연스러운 만남 추구)를 선호한다는 응답이 30대에서도 절반을 넘었다"),
      ev("e_jam_d1", "datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13T00:00:00Z", "20대 2025-11 피크 → 30대 2026-02 → 40대 2026-08 상승. 세대 간 확산 지연 약 9개월"),
      ev("e_jam_w1", "web", "namu.wiki", "자만추 - 나무위키", "2026-08-19T00:00:00Z", "자연스러운 만남 추구의 줄임말. 반의어 인만추"),
    ],
    usage: [seg("KR", "20s", "2025-11-18", 0.55), seg("KR", "30s", "2026-02-26", 0.3), seg("KR", "40s", "2026-08-05", 0.12)],
    weekly: weekly([14, 12, 15, 13, 16, 14, 15, 17, 16, 15, 16, 15]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_luckyvicky", canonical: "럭키비키", lang: "ko", aliases: ["완전 럭키비키잖아", "럭키비키잖아"], status: "verified", lifecycle: "declining", first_seen: "2024-04-20T00:00:00Z", last_seen: "2026-09-12T15:00:00Z" },
    readings: { ja: "ラッキービッキー", en: "Lucky Vicky" },
    category: "meme",
    plain: "오히려 좋아",
    en: { definition: "An attitude of finding the upside in a bad situation and calling it 'lucky after all'.", expansion: "Lucky + Vicky (Jang Won-young's English name)", origin: "Started in April 2024 when IVE's Jang Won-young said '완전 럭키비키잖아' ('that's totally lucky-Vicky') in a video; spread together with 원영적 사고.", nuance: "The fad had passed by 2026; it survives mainly as an ironic use of a dated meme. A brand using it earnestly reads as out of touch.", plain: "lucky after all" },
    ja: { definition: "悪い状況でも良い面を見つけて「かえって運がいい」と考える態度を表す言葉。", expansion: "Lucky + Vicky（チャン・ウォニョンの英語名）", origin: "2024年4月、IVEのチャン・ウォニョンが動画で言った「완전 럭키비키잖아」（完全にラッキービッキーじゃん）がミームになった。「원영적 사고」とともに広まった。", nuance: "2026年現在、流行は過ぎており、わざと古いミームを使う皮肉な使い方が残っている。ブランドが真剣に使うと時代遅れに見える。", plain: "かえってラッキー" },
    meanings: [
      {
        meaning_id: "m_lv_1", term_id: "t_luckyvicky", version: 1,
        definition: "나쁜 상황에서도 좋은 면을 찾아 '오히려 운이 좋다'고 여기는 태도를 뜻하는 말.",
        expansion: "Lucky + Vicky(장원영의 영어 이름)",
        origin: "2024년 4월 아이브 장원영이 영상에서 한 \"완전 럭키비키잖아\" 발언이 밈이 되었다. '원영적 사고'와 함께 확산.",
        nuance: "2026년 현재 유행은 지났고, 일부러 철 지난 밈을 쓰는 반어적 용법이 남아 있다. 브랜드가 진지하게 쓰면 촌스럽게 읽힌다.",
        generations: ["10s", "20s"], regions: ["KR", "JP"], self_confidence: 0.9, confidence: 0.9,
        verification: "verified_human", valid_from: "2025-10-12T09:00:00Z", valid_to: null, created_by: "research_agent", citations: ["https://namu.wiki/"],
      },
    ],
    evidences: [
      ev("e_lv_w1", "wiki", "namu.wiki", "나무위키: 원영적 사고 — 럭키비키", "2026-09-27T00:00:00Z", "'완전 럭키비키잖아' 에서 나온 말", "https://namu.wiki/w/%EC%9B%90%EC%98%81%EC%A0%81%20%EC%82%AC%EA%B3%A0"),
      ev("e_lv_s1", "short", "youtube.com", "럭키비키 원본 장면 모음", "2026-06-02T00:00:00Z", "\"완전 럭키비키잖아~\" 반복 편집. 조회수 증가율 둔화"),
      ev("e_lv_n1", "news", "n.news.naver.com", "'럭키비키'는 끝났다? 2026 광고 카피에 남은 철 지난 밈들", "2026-08-11T01:00:00Z", "밈 수명은 평균 3개월인데 광고는 6개월 뒤에 따라온다"),
      ev("e_lv_d1", "datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13T00:00:00Z", "10대 2024-05 피크 후 지속 하락. 40대는 2025-01 소폭 상승 뒤 소멸"),
    ],
    usage: [seg("KR", "10s", "2024-04-20", 0.5), seg("KR", "20s", "2024-05-10", 0.33), seg("JP", "10s", "2024-07-01", 0.1), seg("KR", "40s", "2025-01-15", 0.07)],
    weekly: weekly([40, 36, 30, 27, 22, 20, 17, 15, 13, 12, 10, 9]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_wonyoung", canonical: "원영적 사고", lang: "ko", aliases: ["원영적사고"], status: "verified", lifecycle: "steady", first_seen: "2024-04-20T00:00:00Z", last_seen: "2026-09-13T08:00:00Z" },
    category: "meme",
    plain: "긍정적으로 생각하기",
    en: { definition: "Ultra-positive thinking that reframes whatever happens as working in your favor, named after Jang Won-young's way of speaking.", expansion: null, origin: "Appeared in 2024 alongside the 럭키비키 meme. It settled into a word for an attitude rather than a meme, so it outlived the fad.", nuance: "The meme itself has cooled, but new '-적 사고' spin-offs keep appearing.", plain: "thinking positively" },
    meanings: [
      {
        meaning_id: "m_wy_1", term_id: "t_wonyoung", version: 1,
        definition: "어떤 일이 생겨도 자기에게 유리한 쪽으로 해석하는 초긍정 사고방식. 장원영의 말버릇에서 이름을 따왔다.",
        expansion: null,
        origin: "2024년 '럭키비키' 밈과 함께 등장. 밈보다는 '태도'를 가리키는 말로 굳어져 유행어보다 오래 살아남았다.",
        nuance: "밈 자체는 식었지만 '~적 사고' 형태의 파생어(예: 지영적 사고)가 계속 만들어진다.",
        generations: ["10s", "20s", "30s"], regions: ["KR"], self_confidence: 0.85, confidence: 0.88,
        verification: "verified_human", valid_from: "2025-10-12T09:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
      },
    ],
    evidences: [
      ev("e_wy_w1", "wiki", "namu.wiki", "나무위키: 원영적 사고", "2026-09-27T00:00:00Z", "원영적 사고", "https://namu.wiki/w/%EC%9B%90%EC%98%81%EC%A0%81%20%EC%82%AC%EA%B3%A0"),
      ev("e_wy_s1", "short", "youtube.com", "원영적 사고로 회사 다니는 법", "2026-09-01T00:00:00Z", "직장인 채널에서 30대 시청 비율 상승"),
      ev("e_wy_n1", "news", "n.news.naver.com", "'원영적 사고' 2년 — 밈은 죽고 태도는 남았다", "2026-05-20T00:00:00Z", "심리학자들은 '인지 재구성'의 대중 버전이라고 본다"),
    ],
    usage: [seg("KR", "10s", "2024-04-25", 0.3), seg("KR", "20s", "2024-05-02", 0.4), seg("KR", "30s", "2024-09-10", 0.3)],
    weekly: weekly([21, 22, 20, 23, 22, 24, 21, 22, 23, 22, 21, 22]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_jeomechu", canonical: "저메추", lang: "ko", aliases: ["저메추좀"], status: "verified", lifecycle: "steady", first_seen: "2018-03-01T00:00:00Z", last_seen: "2026-09-13T10:00:00Z" },
    category: "slang",
    plain: "저녁 메뉴 추천",
    en: { definition: "Asking someone to recommend what to have for dinner.", expansion: "저녁 메뉴 추천 ('dinner menu recommendation')", origin: "Derived from 점메추 (lunch menu recommendation); became everyday chat language in the late 2010s.", nuance: "Casual speech between friends. Sounds flippant in notices or announcements.", plain: "a dinner suggestion" },
    meanings: [
      {
        meaning_id: "m_jm_1", term_id: "t_jeomechu", version: 1,
        definition: "저녁 메뉴를 추천해 달라는 말.",
        expansion: "저녁 메뉴 추천",
        origin: "'점메추(점심 메뉴 추천)'에서 파생. 2010년대 후반 커뮤니티·메신저에서 일상어가 됐다.",
        nuance: "친한 사이의 구어. 공지·안내문에 쓰면 가볍게 읽힌다.",
        generations: ["10s", "20s", "30s"], regions: ["KR"], self_confidence: 0.92, confidence: 0.93,
        verification: "verified_human", valid_from: "2025-10-12T09:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
      },
    ],
    evidences: [
      ev("e_jm_s1", "short", "youtube.com", "저메추 해주는 AI 써봤다", "2026-08-25T00:00:00Z", "\"저메추 좀\" 이라고 치면 메뉴 3개를 추천"),
      ev("e_jm_c1", "community", "theqoo.net", "오늘 저메추 좀", "2026-09-10T00:00:00Z", "매일 반복되는 정형 게시글. 세대 신호 약함"),
      ev("e_jm_d1", "datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13T00:00:00Z", "모든 연령대에서 평탄. 계절성(연말 상승)만 있음"),
    ],
    usage: [seg("KR", "20s", "2018-03-01", 0.45), seg("KR", "10s", "2018-06-01", 0.3), seg("KR", "30s", "2019-01-10", 0.25)],
    weekly: weekly([18, 19, 18, 20, 19, 18, 20, 21, 19, 20, 19, 20]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_aljal", canonical: "알잘딱깔센", lang: "ko", aliases: ["알잘딱"], status: "verified", lifecycle: "dormant", first_seen: "2020-05-01T00:00:00Z", last_seen: "2026-07-02T00:00:00Z" },
    category: "slang",
    plain: "알아서 깔끔하게",
    en: { definition: "Asking someone to just handle it well, neatly and with good judgment.", expansion: "알아서 잘 딱 깔끔하고 센스있게 ('on your own, well, precisely, neatly and with good sense')", origin: "Spread around 2020 among viewers of Korean internet streams.", nuance: "Usage dropped sharply after 2023; today it sounds like internet speak from a few years back.", plain: "handle it neatly" },
    meanings: [
      {
        meaning_id: "m_aj_1", term_id: "t_aljal", version: 1,
        definition: "일을 알아서, 잘, 딱, 깔끔하게, 센스 있게 처리해 달라는 뜻.",
        expansion: "알아서 잘 딱 깔끔하고 센스있게",
        origin: "2020년경 인터넷 방송(트위치) 시청자 커뮤니티에서 확산.",
        nuance: "2023년 이후 사용이 급감. 지금 쓰면 '몇 년 전 인터넷 말투'로 읽힌다.",
        generations: ["10s", "20s"], regions: ["KR"], self_confidence: 0.88, confidence: 0.9,
        verification: "verified_human", valid_from: "2025-10-12T09:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
      },
    ],
    evidences: [
      ev("e_aj_w1", "web", "namu.wiki", "알잘딱깔센 - 나무위키", "2026-01-05T00:00:00Z", "알아서 잘 딱 깔끔하고 센스있게의 줄임말", "https://namu.wiki/w/%EC%95%8C%EC%9E%98%EB%94%B1%EA%B9%94%EC%84%BC"),
      ev("e_aj_d1", "datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13T00:00:00Z", "2021-03 피크(100) → 2026-09 지수 2. 전 연령 소멸"),
    ],
    usage: [seg("KR", "10s", "2020-05-01", 0.5), seg("KR", "20s", "2020-06-15", 0.45), seg("KR", "30s", "2021-02-01", 0.05)],
    weekly: weekly([3, 2, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
    recheck_days: 60,
  },
  {
    term: { term_id: "t_sixseven", canonical: "6-7", lang: "en", aliases: ["6 7", "six seven", "67 밈"], status: "verified", lifecycle: "declining", first_seen: "2025-05-10T00:00:00Z", last_seen: "2026-09-13T18:00:00Z" },
    category: "meme",
    plain: "",
    en: { definition: "An exclamation whose whole point is that it means nothing. Shouted as 'six seven' with both hands bobbing like a scale; sometimes just 'so-so'.", expansion: null, origin: "Exploded among US middle-schoolers in 2025 from the lyric in Skrilla's 'Doot Doot (6 7)' combined with edits of NBA player LaMelo Ball (6 ft 7). Teachers banned it in class.", nuance: "An in-group signal among teens. Adults who use it are instantly read as copying. Declining in 2026.", plain: null },
    meanings: [
      {
        meaning_id: "m_67_1", term_id: "t_sixseven", version: 1,
        definition: "의미가 없다는 것이 핵심인 감탄사. \"식스 세븐\"이라 외치며 양손을 저울처럼 흔든다. '그저 그렇다' 정도로도 쓰인다.",
        expansion: null,
        origin: "2025년 래퍼 Skrilla 의 곡 'Doot Doot (6 7)' 가사와 NBA 라멜로 볼(6피트 7인치) 편집 영상이 결합해 미국 초·중학생 사이에서 폭발. 교사들이 수업 중 금지할 정도로 확산.",
        nuance: "10대 안에서만 통하는 내집단 신호. 어른이 쓰면 즉시 '따라하기'로 읽힌다. 2026년 들어 하락.",
        generations: ["10s"], regions: ["US", "GB", "AU", "KR"], self_confidence: 0.84, confidence: 0.8,
        verification: "verified_auto", valid_from: "2025-12-01T09:00:00Z", valid_to: null, created_by: "research_agent",
        citations: ["https://www.cnn.com/", "https://mashable.com/"],
      },
    ],
    evidences: [
      ev("e_67_w1", "web", "en.wikipedia.org", "Wikipedia: 6-7", "2026-09-15T00:00:00Z", "6-7 (meme)", "https://en.wikipedia.org/wiki/6-7"),
      ev("e_67_n1", "news", "cnn.com", "The '6-7' meme can be annoying. But kids are shouting it for good reason", "2025-11-14T00:00:00Z", "The meaninglessness is the point, researchers say"),
      ev("e_67_n2", "news", "mashable.com", "From 6-7 to aura farming: Defining 2025's viral internet slang", "2025-12-20T00:00:00Z", "A year-end glossary of the terms adults could not escape"),
      ev("e_67_s1", "short", "youtube.com", "6 7 explained in 60 seconds", "2026-01-08T00:00:00Z", "Skrilla 가사 → 라멜로 볼 → 학교 밈 순서로 설명"),
      ev("e_67_w1", "web", "knowyourmeme.com", "6-7 (Six Seven)", "2026-02-01T00:00:00Z", "Origin: Skrilla — Doot Doot (6 7)"),
    ],
    usage: [seg("US", "10s", "2025-06-01", 0.7), seg("US", "20s", "2025-09-01", 0.18), seg("KR", "10s", "2025-11-20", 0.12)],
    weekly: weekly([55, 50, 48, 44, 40, 35, 33, 30, 28, 25, 22, 20]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_aurafarming", canonical: "aura farming", lang: "en", aliases: ["aura farm", "아우라 파밍"], status: "verified", lifecycle: "steady", first_seen: "2025-01-15T00:00:00Z", last_seen: "2026-09-13T20:00:00Z" },
    category: "meme",
    plain: "멋있어 보이려는 행동",
    en: { definition: "Repeating cool-looking moves or poses to build up 'aura' (charisma points). Used both sincerely and mockingly.", expansion: null, origin: "Grew out of the 'aura points' joke in gaming and anime fandoms; in 2025 a video of an Indonesian boy dancing deadpan on the bow of a racing boat made it a worldwide meme.", nuance: "A global meme with Southeast Asian roots. In Korea, teens and twenty-somethings use the transliteration 아우라 파밍.", plain: "acting cool for effect" },
    meanings: [
      {
        meaning_id: "m_af_1", term_id: "t_aurafarming", version: 1,
        definition: "멋있어 보이는 행동이나 포즈를 반복해 '아우라(카리스마 점수)'를 쌓는다는 뜻. 진지하게도, 놀리는 말로도 쓴다.",
        expansion: null,
        origin: "게임·애니 팬덤의 'aura points' 농담에서 출발. 2025년 인도네시아 소년이 보트 경주 뱃머리에서 무표정으로 춤추는 영상이 전 세계로 퍼지며 대표 이미지가 됐다.",
        nuance: "동남아 발 글로벌 밈. 한국에서는 '아우라 파밍' 음차로 10~20대가 쓴다.",
        generations: ["10s", "20s"], regions: ["US", "ID", "GLOBAL"], self_confidence: 0.83, confidence: 0.8,
        verification: "verified_auto", valid_from: "2026-01-20T09:00:00Z", valid_to: null, created_by: "research_agent", citations: ["https://mashable.com/"],
      },
    ],
    evidences: [
      ev("e_af_w1", "web", "en.wikipedia.org", "Wikipedia: Aura farming", "2026-09-16T00:00:00Z", "Aura farming", "https://en.wikipedia.org/wiki/Aura_farming"),
      ev("e_af_s1", "short", "youtube.com", "Boat race kid aura farming (original)", "2025-07-05T00:00:00Z", "조회수 급증. 댓글 다국어 — ID·US·BR·KR"),
      ev("e_af_n1", "news", "mashable.com", "From 6-7 to aura farming: Defining 2025's viral internet slang", "2025-12-20T00:00:00Z", "'Aura farming' — performing coolness for an audience"),
      ev("e_af_s2", "short", "youtube.com", "아우라 파밍 하는 우리 강아지", "2026-08-30T00:00:00Z", "한국어 음차 사용 확인. 20대 채널"),
    ],
    usage: [seg("US", "10s", "2025-01-15", 0.35), seg("ID", "10s", "2025-07-01", 0.3), seg("US", "20s", "2025-08-01", 0.2), seg("KR", "20s", "2025-08-10", 0.15)],
    weekly: weekly([30, 31, 29, 33, 32, 30, 31, 34, 33, 32, 31, 32]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_oshikatsu", canonical: "推し活", lang: "ja", aliases: ["오시카츠", "oshikatsu"], status: "verified", lifecycle: "steady", first_seen: "2015-01-01T00:00:00Z", last_seen: "2026-09-13T11:00:00Z" },
    readings: { ko: "오시카쓰", en: "oshikatsu" },
    category: "slang",
    plain: "좋아하는 스타 응원 활동",
    en: { definition: "Everything you do to support your favorite idol or character: buying goods, going to shows, promoting them online.", expansion: "推し (the one you root for) + 活動 (activity)", origin: "Japanese idol-fandom term from the 2010s; became mainstream after being shortlisted for the 2021 word-of-the-year awards.", nuance: "In Japan it is standard vocabulary across generations. Korean fans transliterate it as 오시카츠, which is unfamiliar to people over 30.", plain: "supporting your favorite star" },
    ja: { definition: "好きなアイドルやキャラクター（推し）を応援する活動全般。グッズの購入、ライブへの参加、SNSでの発信など。", expansion: "推し（応援する対象）＋活動", origin: "2010年代の日本のアイドルファンの言葉。2021年の新語・流行語大賞にノミネートされ、一般的な言葉になった。", nuance: "日本では世代を問わず通じる標準的な言葉。韓国のファンは「오시카츠」と音訳して使うが、30代以上にはなじみが薄い。", plain: "推しの応援" },
    meanings: [
      {
        meaning_id: "m_ok_1", term_id: "t_oshikatsu", version: 1,
        definition: "좋아하는 아이돌·캐릭터('推し')를 응원하는 활동 전반. 굿즈 구매, 공연 참석, SNS 홍보 등.",
        expansion: "推し(응원하는 대상) + 活動",
        origin: "2010년대 일본 아이돌 팬덤 용어. 2021년 신어·유행어 대상 후보에 오르며 일반어가 됐다.",
        nuance: "일본에서는 세대를 가리지 않는 표준어급. 한국 팬덤은 '오시카츠'로 음차해 쓰지만 30대 이상은 낯설다.",
        generations: ["10s", "20s", "30s", "40s"], regions: ["JP", "KR", "TW"], self_confidence: 0.9, confidence: 0.88,
        verification: "verified_auto", valid_from: "2026-02-02T09:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
      },
    ],
    evidences: [
      ev("e_ok_w1", "web", "ko.wikipedia.org", "Wikipedia: 오시카츠 (推し活)", "2026-09-17T00:00:00Z", "推し活", "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%8B%9C%EC%B9%B4%EC%B8%A0"),
      ev("e_ok_s1", "short", "youtube.com", "推し活グッズ収納ルームツアー", "2026-08-12T00:00:00Z", "일본어 쇼츠. 30~40대 여성 시청 비율 높음"),
      ev("e_ok_n1", "news", "news.yahoo.co.jp", "推し活市場、2026年も拡大　シニア層の参入が鮮明", "2026-07-08T00:00:00Z", "60대 이상 참여가 늘었다는 조사"),
      ev("e_ok_s2", "short", "youtube.com", "오시카츠 브이로그 | 도쿄돔", "2026-09-02T00:00:00Z", "한국어 음차 사용. 20대 채널"),
    ],
    usage: [seg("JP", "20s", "2015-01-01", 0.3), seg("JP", "10s", "2016-01-01", 0.2), seg("JP", "30s", "2019-01-01", 0.2), seg("JP", "40s", "2021-06-01", 0.15), seg("KR", "20s", "2023-03-01", 0.1), seg("TW", "20s", "2023-09-01", 0.05)],
    weekly: weekly([26, 25, 27, 26, 28, 27, 26, 27, 29, 28, 27, 28]),
    recheck_days: 14,
  },
  {
    term: { term_id: "t_skibidi", canonical: "skibidi", lang: "en", aliases: ["스키비디"], status: "verified", lifecycle: "dormant", first_seen: "2023-02-01T00:00:00Z", last_seen: "2026-06-10T00:00:00Z" },
    category: "meme",
    plain: "",
    en: { definition: "A filler word attached with no fixed meaning; it can mean good or bad.", expansion: null, origin: "From the YouTube animated series 'Skibidi Toilet' (2023); became the poster child of 'brainrot' vocabulary in 2024.", nuance: "By 2026 even teens treat it as an old meme; using it invites ridicule.", plain: null },
    meanings: [
      {
        meaning_id: "m_sk_1", term_id: "t_skibidi", version: 1,
        definition: "특정한 뜻 없이 붙이는 감탄·수식어. 좋다는 뜻도, 나쁘다는 뜻도 된다.",
        expansion: null,
        origin: "2023년 유튜브 애니메이션 시리즈 'Skibidi Toilet'에서 나옴. 2024년 '브레인롯(brainrot)' 어휘의 대표 사례가 됐다.",
        nuance: "2026년 현재 10대조차 '옛날 밈'으로 취급. 사용 시 조롱 대상이 됨.",
        generations: ["10s"], regions: ["US", "GLOBAL"], self_confidence: 0.9, confidence: 0.86,
        verification: "verified_auto", valid_from: "2025-12-01T09:00:00Z", valid_to: null, created_by: "research_agent", citations: ["https://knowyourmeme.com/"],
      },
    ],
    evidences: [
      ev("e_sk_w2", "web", "ko.wikipedia.org", "Wikipedia: Skibidi Toilet", "2026-09-28T00:00:00Z", "Skibidi Toilet", "https://ko.wikipedia.org/wiki/Skibidi_Toilet"),
      ev("e_sk_w1", "web", "knowyourmeme.com", "Skibidi Toilet", "2026-01-10T00:00:00Z", "Web series by DaFuq!?Boom!, 2023"),
      ev("e_sk_n1", "news", "theguardian.com", "'Brain rot' words: what parents need to know", "2025-03-02T00:00:00Z", "skibidi, rizz, sigma — the vocabulary of a generation"),
    ],
    usage: [seg("US", "10s", "2023-02-01", 0.8), seg("KR", "10s", "2023-10-01", 0.2)],
    weekly: weekly([4, 3, 3, 2, 1, 1, 0, 0, 1, 0, 0, 0]),
    recheck_days: 60,
  },
  // ---- 검수 큐에 있는 후보 (unverified) ----
  {
    term: { term_id: "t_galau", canonical: "galau", lang: "id", aliases: ["갈라우"], status: "needs_review", lifecycle: "emerging", first_seen: "2026-08-28T00:00:00Z", last_seen: "2026-09-13T13:00:00Z" },
    category: "slang",
    plain: "마음이 복잡한",
    en: { definition: "Feeling confused, down and unable to make up your mind, often about a relationship.", expansion: null, origin: "Indonesian colloquial word. Became teen slang on social media in the early 2010s; in 2026 it started appearing as a caption (갈라우) in Korean short videos.", nuance: "An everyday word for all ages in Indonesia. Its arrival in Korea is at an early stage and may not spread.", plain: "feeling torn" },
    meanings: [
      {
        meaning_id: "m_ga_1", term_id: "t_galau", version: 1,
        definition: "마음이 복잡하고 우울하며 갈피를 못 잡는 상태. 연애 고민 맥락이 많다.",
        expansion: null,
        origin: "인도네시아 구어. 2010년대 초 SNS 에서 청소년 표현으로 굳어졌고, 2026년 한국 쇼츠에 '갈라우' 자막으로 등장하기 시작.",
        nuance: "인도네시아에서는 전 세대 일상어. 한국 유입은 초기 단계 — 확산 여부 미확정.",
        generations: ["10s", "20s"], regions: ["ID", "KR"], self_confidence: 0.42, confidence: 0.4,
        verification: "unverified", valid_from: "2026-09-12T06:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
      },
    ],
    evidences: [
      ev("e_ga_s1", "short", "youtube.com", "갈라우… (인니 유학생 브이로그)", "2026-09-11T00:00:00Z", "자막에 'galau(갈라우)' 표기. 조회수 낮음"),
    ],
    usage: [seg("ID", "all", "2012-01-01", 0.9), seg("KR", "20s", "2026-08-28", 0.1)],
    weekly: weekly([0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 6]),
    recheck_days: 2,
    gate_reasons: ["확신도 42% (기준 50%)", "서로 다른 출처가 2개 미만"],
  },
];

// 예시에도 쓸 때 조심과 퍼진 정도를 채운다 — 비어 있으면 예시 화면이 모두 '확인 전' 이라 배지도 '주의가 필요한 밈' 목록도 비었다
// (개편 통합 09-29). 값은 뜻풀이의 뉘앙스를 보고 실데이터 규칙(pipeline/risk.py)이 낼 법한 것으로 골랐다. 목록에 없는 확인된 말은 '특이 사항 없음'.
const CHECKED = "2026-09-13T21:00:00Z";
const UNCHECKED = new Set(["t_crumbl", "t_dipstack"]);     // 아직 검사 전 — '확인 전'
const SIGNALS: Record<string, { risk?: "caution" | "avoid" | null; reasons?: string[]; diffusion?: Diffusion }> = {
  t_jungti: { risk: "avoid", reasons: ["국적을 빗댄 표현이라 비하로 읽힐 수 있다"] },
  t_shagal: { risk: "caution", reasons: ["순화형이지만 뿌리는 욕설이다"], diffusion: "mainstream" },
  t_temuhuman: { risk: "caution", reasons: ["남에게 붙이면 사람을 낮춰 부르는 말이 된다"] },
  t_wegovy: { risk: "caution", reasons: ["의학적 효과를 단정하는 문구로 쓰면 곤란하다"], diffusion: "spreading" },
  t_raeulla: { risk: null },                                  // 근거가 모자라 판단 보류 — 화면에는 '근거 부족'
  t_ptpa: { risk: null },
  t_pierrot: { diffusion: "spreading" },
  t_aislop: { diffusion: "mainstream" },
  t_oshikatsu: { diffusion: "mainstream" },
  t_ttogago: { diffusion: "mainstream" },
  t_nanlijabeth: { diffusion: "underground" },
  t_tungtung: { diffusion: "fading" },
  t_skibidi: { diffusion: "fading" },
};

function withSignals(r: TermRecord): TermRecord {
  if (r.term.status !== "verified" || UNCHECKED.has(r.term.term_id)) return r;
  const s = SIGNALS[r.term.term_id] ?? {};
  return { ...r, term: { ...r.term, risk_level: "risk" in s ? s.risk ?? null : "none", risk_reasons: s.reasons ?? [], risk_checked_at: CHECKED,
    ...(s.diffusion && { diffusion: s.diffusion }) } };
}

export const SAMPLE_RECORDS: TermRecord[] = [...BASE_RECORDS, ...KOREAN_2026, ...LATEST_2026].map(withSignals);

export const SAMPLE_STAGES: PipelineStage[] = [
  { key: "collect", label: "수집", count_24h: 1284, status: "ok", note: "27개국 · 영상 891 · 기사 393" },
  { key: "classify", label: "선별", count_24h: 412, status: "ok", note: "다음 단계로 넘긴 비율 32%" },
  { key: "interpret", label: "영상 해석", count_24h: 96, status: "ok", note: "" },
  { key: "discover", label: "새 용어 발견", count_24h: 31, status: "ok", note: "처음 보는 용어 9" },
  { key: "research", label: "뜻 조사", count_24h: 18, status: "warn", note: "월 검색 한도 62% 사용" },
  { key: "verify", label: "확인", count_24h: 11, status: "ok", note: "확인 7 · 검수 대기 4" },
];

const published = (termId: string): Meaning => SAMPLE_RECORDS.find((r) => r.term.term_id === termId)!.meanings.find((m) => m.valid_to == null)!;
/** 지금 실린 뜻 위에 몇 칸만 고친 안 — 백엔드 pipeline/crosscheck.merged 와 같다(풀이·세대·나라는 그대로). */
const fixOf = (termId: string, fix: Partial<Pick<MeaningDraft, "definition" | "origin" | "nuance">>): MeaningDraft => {
  const m = published(termId);
  return { definition: m.definition, expansion: m.expansion ?? null, origin: m.origin, nuance: m.nuance, generations: m.generations, regions: m.regions,
    self_confidence: m.self_confidence, is_expression: true, ...fix };
};

/* 검수 큐 — 새 말(조사 결과) 다섯과 문서 대조의 제안(Plan 12) 종류마다 하나. 문서 대조의 제안은 지금 뜻이 공개된 채로 올라온다. */
export const SAMPLE_QUEUE: ReviewItem[] = [
  {
    term_id: "t_aurafarming", canonical: "aura farming", kind: "correction",
    draft: fixOf("t_aurafarming", { origin: "'aura'(아우라) 인터넷 속어에서 나온 말로, 2024년 X·인스타그램·틱톡에서 널리 쓰이기 시작했다. 2025년 인도네시아 소년이 보트 경주 뱃머리에서 무표정으로 춤추는 영상이 대표 이미지가 됐다." }),
    reasons: ["문서 대조: 고칠 것", "유래: 문서는 'aura' 속어에서 나와 2024년에 퍼졌다고 적는다. 지금 뜻은 게임·애니 팬덤의 농담에서 출발했다고 적는다",
      "참고 문서: https://en.wikipedia.org/wiki/Aura_farming"],
    evidence_count: 4, queued_at: "2026-09-29T02:10:00Z",
    docs: [{ wiki: "Wikipedia", url: "https://en.wikipedia.org/wiki/Aura_farming", summary: "멋있어 보이려고 일부러 애쓰는 행동을 가리키며, 'aura' 속어에서 나왔다고 적는다.", proposal: null }],
  },
  {
    term_id: "t_skibidi", canonical: "skibidi", kind: "conflict",
    reasons: ["문서 대조: 위키끼리 다름", "뜻: 나무위키는 뜻 없이 붙이는 말이라고, 위키백과는 '멋지다·이상하다' 같은 뜻으로 쓴다고 적는다",
      "참고 문서: https://namu.wiki/w/Skibidi%20Toilet", "참고 문서: https://en.wikipedia.org/wiki/Skibidi_Toilet"],
    evidence_count: 3, queued_at: "2026-09-29T02:12:00Z",
    docs: [
      { wiki: "나무위키", url: "https://namu.wiki/w/Skibidi%20Toilet", summary: "'Skibidi Toilet' 시리즈에서 나온 말로, 특별한 뜻 없이 붙인다고 적는다.", proposal: null },
      { wiki: "Wikipedia", url: "https://en.wikipedia.org/wiki/Skibidi_Toilet", summary: "10대가 '멋지다' 또는 '이상하다·별로다'라는 뜻으로 붙인다고 적는다.",
        proposal: fixOf("t_skibidi", { definition: "'Skibidi Toilet' 시리즈에서 나와 10대가 '멋지다' 또는 '이상하다·별로다'라는 뜻으로 붙이는 말. 맥락에 따라 뜻이 정반대가 된다." }) },
    ],
  },
  {
    term_id: "t_mugonghae", canonical: "무공해", kind: "retire",
    reasons: ["문서 대조: 밈이 아님", "문서는 환경 용어 '무공해'(공해가 없음)를 다룬다 — 사람을 두고 쓰는 뜻은 문서에 없다", "참고 문서: https://ko.wikipedia.org/wiki/무공해"],
    evidence_count: 3, queued_at: "2026-09-29T02:14:00Z",
    docs: [{ wiki: "위키백과(ko)", url: "https://ko.wikipedia.org/wiki/무공해", summary: "", proposal: null }],
  },
  {
    term_id: "t_sabopil", canonical: "사보필", kind: "new",
    proposed: SAMPLE_RECORDS.find((r) => r.term.term_id === "t_sabopil")!.meanings[0],
    reasons: ["뜻을 정의한 공개 출처가 없음 (캐릿 기사 목차만)", "서로 다른 출처가 2개 미만"],
    evidence_count: 1, queued_at: "2026-09-14T07:40:00Z",
  },
  {
    term_id: "t_sixseven", canonical: "6-7", kind: "new",
    proposed: {
      meaning_id: "m_67_2", term_id: "t_sixseven", version: 2,
      definition: "의미 없는 감탄사. 최근 근거에서는 '그저 그렇다(5~7점)' 라는 평가 뉘앙스가 뚜렷해짐.",
      expansion: null, origin: "(v1 과 동일)", nuance: "평가하는 뉘앙스가 새로 보임. 뜻이 바뀌었을 가능성",
      generations: ["10s"], regions: ["US", "GB", "AU", "KR"], self_confidence: 0.71, confidence: 0.6,
      verification: "unverified", valid_from: "2026-09-13T06:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
    },
    reasons: ["지금 실린 뜻(1판: 의미 없음)과 다릅니다. 뜻이 바뀐 것인지 확인 필요"],
    evidence_count: 3, queued_at: "2026-09-13T06:10:00Z",
  },
  {
    term_id: "t_galau", canonical: "galau", kind: "new",
    proposed: SAMPLE_RECORDS.find((r) => r.term.term_id === "t_galau")!.meanings[0],
    reasons: ["확신도 42% (기준 50%)", "서로 다른 출처가 2개 미만"],
    evidence_count: 1, queued_at: "2026-09-12T06:20:00Z",
  },
  {
    term_id: "t_aurafarming_ko", canonical: "아우라 농사", kind: "new",
    proposed: {
      meaning_id: "m_afko_1", term_id: "t_aurafarming_ko", version: 1,
      definition: "'aura farming'의 직역 표기. 실제 사용 표기인지 불명.",
      expansion: null, origin: "웹 검색 결과 2건만 있음", nuance: "실제로는 '아우라 파밍'으로 쓰는 경우가 많아 보임. 같은 말의 다른 표기로 묶을지 판단 필요",
      generations: ["20s"], regions: ["KR"], self_confidence: 0.35, confidence: 0.3,
      verification: "unverified", valid_from: "2026-09-11T06:00:00Z", valid_to: null, created_by: "research_agent", citations: [],
    },
    reasons: ["영상·기사·검색 통계 근거가 없고 웹 검색 결과만 있음", "확신도 35% (기준 50%)"],
    evidence_count: 2, queued_at: "2026-09-11T06:30:00Z",
  },
  {
    term_id: "t_luckyvicky", canonical: "럭키비키", kind: "new",
    proposed: {
      meaning_id: "m_lv_retire", term_id: "t_luckyvicky", version: 2,
      definition: "추세를 '거의 안 쓰임'으로 바꾸자는 제안. 12주 연속 감소, 최근 4주 평균 10건 미만.",
      expansion: null, origin: "(v1 과 동일)", nuance: "자동 추적 결과. 확인 후 유지 또는 폐기 결정",
      generations: ["10s", "20s"], regions: ["KR", "JP"], self_confidence: 0.9, confidence: 0.9,
      verification: "unverified", valid_from: "2026-09-14T06:00:00Z", valid_to: null, created_by: "tracking_agent", citations: [],
    },
    reasons: ["추세 변경 제안: 줄어드는 중 → 거의 안 쓰임"],
    evidence_count: 3, queued_at: "2026-09-14T06:05:00Z",
  },
];

export const SAMPLE_COPY = "엄마 오늘 저메추 좀ㅋㅋ 소개팅은 됐고 나는 자만추 할래. 시험은 망했는데 완전 럭키비키잖아? 원영적 사고 가자";
export const SAMPLE_COPY_EN = "ngl that boat kid is pure aura farming 😭 6-7!! bro is so skibidi";
/** 일본어 화면의 예시 메시지 — 예시 사전의 말(推し活·aura farming)이 든 일본어 글. 미리 만든 재작성은 없다(모델 출력을 손으로 지어내지 않는다) */
export const SAMPLE_COPY_JA = "週末は「推し活」でライブ遠征！ 会場で撮った写真、完全に aura farming だった 😭";

/* '쉽게 풀어 쓰면' — 예시 메시지에 대해 로컬 Gemma(gemma4:12b, interpreters/gemma_rewrite.py)가 만든 재작성.
   규칙 치환은 쓰지 않는다. 다른 메시지는 API 모드에서 서버가 만든다. */
export const SAMPLE_REWRITES: Record<Locale, Record<string, string>> = {
  ko: { [SAMPLE_COPY]: "엄마 오늘 저녁 메뉴 좀 추천해줘ㅋㅋ 소개팅은 됐고 나는 자연스럽게 만나서 연애할래. 시험은 망했는데 오히려 운이 좋네? 긍정적으로 생각하자" },
  en: { [SAMPLE_COPY_EN]: "ngl that boat kid is just trying to look impressive on purpose 😭 bro is so silly" },
  ja: {},
};
