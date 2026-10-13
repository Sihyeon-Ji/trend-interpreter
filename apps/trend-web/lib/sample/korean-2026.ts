/* 2026년 한국 유행어 추가분 (2026-09-14 웹 조사: 나무위키·경향신문·매일경제·캐릿·여행픽·네이트 카드뉴스·카더라 결산 등).
   예시 데이터 — 뜻·시점은 조사 시점 기준이고, 언급 수·비중은 가정치. */
import type { Category, Evidence, Generation, Lifecycle, MeaningText, TermRecord, TermStatus, Verification } from "../types";

export const WEEKS = ["2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27", "2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07"];

export interface Spec {
  id: string;
  canonical: string;
  lang?: string;
  aliases?: string[];
  category: Category;
  lifecycle: Lifecycle;
  status?: TermStatus;
  first: string;
  last?: string;
  ko: { definition: string; expansion?: string | null; origin: string; nuance: string; plain: string | null; gens: Generation[]; regions: string[]; verification?: Verification; since?: string };
  en: MeaningText;
  evidence: [Evidence["kind"], string, string, string, string?][]; // kind, domain, title, date, excerpt
  usage: [string, Generation, string, number][]; // region, generation, first_seen, share
  weekly: number[];
  recheck?: number;
  readings?: Record<string, string>;   // 화면 언어 → 표제어 읽기 (TermRecord.readings)
}

export function rec(s: Spec): TermRecord {
  const v = s.ko.verification ?? "verified_auto";
  return {
    term: { term_id: s.id, canonical: s.canonical, lang: s.lang ?? "ko", aliases: s.aliases ?? [], status: s.status ?? "verified", lifecycle: s.lifecycle, first_seen: `${s.first}T00:00:00Z`, last_seen: `${s.last ?? "2026-09-13"}T12:00:00Z` },
    category: s.category,
    plain: s.ko.plain ?? "",
    en: s.en,
    readings: s.readings,
    meanings: [{
      meaning_id: `m_${s.id.replace(/^t_/, "")}_1`, term_id: s.id, version: 1,
      definition: s.ko.definition, expansion: s.ko.expansion ?? null, origin: s.ko.origin, nuance: s.ko.nuance,
      generations: s.ko.gens, regions: s.ko.regions, self_confidence: 0.8, confidence: v === "verified_human" ? 0.9 : 0.8,
      verification: v, valid_from: `${s.ko.since ?? "2026-06-01"}T09:00:00Z`, valid_to: null, created_by: "research_agent", citations: s.evidence.filter((e) => e[0] === "web").map((e) => `https://${e[1]}/`),
    }],
    evidences: s.evidence.map(([kind, domain, title, date, excerpt], i) => ({ evidence_id: `e_${s.id.replace(/^t_/, "")}_${i + 1}`, kind, url: `https://${domain}/`, title, source_domain: domain, observed_at: `${date}T00:00:00Z`, excerpt: excerpt ?? "" })),
    usage: s.usage.map(([region, generation, first_seen, share]) => ({ segment: { segment_id: `${region}-${generation}`, generation, region }, first_seen, share })),
    weekly: s.weekly.map((count, i) => ({ week_start: WEEKS[i], count })),
    recheck_days: s.recheck ?? ({ emerging: 2, rising: 3, peak: 7, steady: 14, declining: 14, dormant: 60, unknown: 7 } as Record<Lifecycle, number>)[s.lifecycle],
  };
}

export const KOREAN_2026: TermRecord[] = [
  rec({
    id: "t_youngkk", canonical: "영크크", aliases: ["영ㅋㅋ", "영크크다"], category: "meme", lifecycle: "steady", first: "2026-02-10",
    ko: { definition: "젊고 트렌디한 감성, 또는 그런 사람을 가리키는 말. '요즘 애들 느낌'을 한 단어로 부르는 데 쓴다.",
      expansion: "YOUNGCREATORCREW(영 크리에이터 크루)", origin: "2026년 2월 보이그룹 CORTIS의 노래 'YOUNGCREATORCREW'와 가사 \"요를레이히 말고 영크크\"에서 나왔다. 공식 채널 챌린지 영상으로 퍼지다가 K팝 팬덤 → 인스타그램 → 예능 자막('냉장고를 부탁해')까지 갔다.",
      nuance: "진지한 세대 구분이 아니라 놀이다. 50대라도 감각이 좋으면 영크크, 20대라도 생각이 늙었으면 늙크크. 격식 있는 자리나 상사에게 쓰기엔 위험하다.",
      plain: "요즘 감각", gens: ["10s", "20s"], regions: ["KR"], verification: "verified_human", since: "2026-03-20" },
    en: { definition: "A young, trendy vibe, or a person who has it. A one-word way to say 'very Gen Z'.", expansion: "YOUNGCREATORCREW", origin: "From the February 2026 CORTIS track 'YOUNGCREATORCREW' and its lyric \"요를레이히 말고 영크크\" ('not yodel-ay-hee, young-kk'). Spread from K-pop fandom to Instagram and variety-show captions.", nuance: "A game, not a real generational label: a stylish 50-year-old can be 영크크 and a stuffy 20-year-old 늙크크. Risky in formal settings or toward a boss.", plain: "trendy" },
    evidence: [
      ["short", "youtube.com", "CORTIS 'YOUNGCREATORCREW' 챌린지 모음", "2026-03-02", "공식 채널 챌린지 영상. 댓글에 '나는 늙크크인가' 자기 검열 밈"],
      ["news", "mk.co.kr", "나는 '영크크'인가 또는 '늙크크'인가…사회적 언어가 된 밈, 젠지어 이해하기 [커버스토리]", "2026-09-05", "노래 제목 축약이 세대 감각을 가르는 사회적 언어가 됐다"],
      ["news", "careet.net", "도대체 어디서 시작된 거야? 요즘 SNS에서 뜨는 밈 모음", "2026-08-20", "늙크크는 2030이 자신을 칭하는 말로 자주 쓰이면서 퍼졌다"],
      ["web", "namu.wiki", "영크크 - 나무위키", "2026-09-01", "원래 '젊은 창작자 무리'라는 뜻이었지만 '트렌디한 것', '젊음'을 뜻하는 밈으로 확장"],
    ],
    usage: [["KR", "10s", "2026-02-15", 0.4], ["KR", "20s", "2026-02-20", 0.4], ["KR", "30s", "2026-04-05", 0.2]],
    weekly: [52, 50, 54, 51, 53, 50, 52, 49, 51, 50, 52, 51],
  }),
  rec({
    id: "t_oldkk", canonical: "늙크크", aliases: ["늙ㅋㅋ", "올크크", "늙크크다"], category: "meme", lifecycle: "steady", first: "2026-02-20",
    ko: { definition: "촌스럽거나 옛날 감성, 이른바 '아재 감성'을 가리키는 말. 영크크의 반대말.",
      expansion: "늙은 + 크크(영크크의 변형)", origin: "영크크(CORTIS 'YOUNGCREATORCREW')가 유행하자 반대말로 만들어졌다. 2030 직장인들이 \"우리는 완연한 늙크크다\"처럼 자신을 부르는 데 쓰며 퍼졌다.",
      nuance: "대부분 자조·농담. '이걸 모르다니 내가 늙크크인가' 식으로 스스로를 놀리는 데 쓴다. 남에게 붙이면 무례하게 들릴 수 있다. 일부에서는 'ㅋㅋㅋ'를 과하게 쓰는 옛날 채팅 습관을 가리킨다고도 한다.",
      plain: "옛날 감성", gens: ["20s", "30s"], regions: ["KR"], verification: "verified_human", since: "2026-03-20" },
    en: { definition: "An old-fashioned, dated vibe — 'dad energy'. The opposite of 영크크.", expansion: "늙은 ('old') + 크크", origin: "Coined as the counterpart to 영크크 after the CORTIS song went viral in early 2026. Office workers in their late 20s and 30s adopted it to describe themselves.", nuance: "Almost always self-deprecating humor ('I didn't know that meme — am I 늙크크?'). Calling someone else this can land as rude.", plain: "old-fashioned" },
    evidence: [
      ["news", "mk.co.kr", "나는 '영크크'인가 또는 '늙크크'인가…사회적 언어가 된 밈, 젠지어 이해하기 [커버스토리]", "2026-09-05"],
      ["news", "careet.net", "도대체 어디서 시작된 거야? 요즘 SNS에서 뜨는 밈 모음", "2026-08-20", "\"늙크크를 회사에서 석방하라\" 같은 자조적 밈"],
      ["community", "brunch.co.kr", "영크크 VS 늙크크", "2026-06-11", "빠르게 바뀌는 디지털 문화 속 2030의 피로를 웃어넘기는 도구"],
      ["web", "namu.wiki", "영크크 - 나무위키", "2026-09-01"],
    ],
    usage: [["KR", "20s", "2026-02-25", 0.45], ["KR", "30s", "2026-03-10", 0.45], ["KR", "40s", "2026-06-01", 0.1]],
    weekly: [44, 46, 45, 47, 46, 48, 47, 46, 48, 47, 46, 47],
  }),
  rec({
    id: "t_bamti", canonical: "밤티", aliases: ["밤티나다", "밤티난다", "밤티력", "길티 밤티"], category: "slang", lifecycle: "rising", first: "2020-03-01",
    ko: { definition: "촌스럽다, 별로다, 어딘가 엉성하다는 뜻의 평가. 옷차림·디자인·CG 등 '어설프게 만들어진 느낌'에 쓴다. 2026년에는 엉성한데 묘하게 정감 간다는 뉘앙스까지 넓어졌다.",
      expansion: null, origin: "아바타 게임 라인플레이의 한 유저 닉네임에서 시작(1차 유행 2020). 2025년 X(트위터)와 여초 커뮤니티에서 다시 발굴돼 팬아트·릴스·틱톡으로 번졌고, 2000년대 장난감 브랜드 '엔젤이' 계정의 패러디가 기름을 부었다.",
      nuance: "실존 유저의 닉네임이 비하어로 쓰이는 것이라 논란이 있다. 사람의 외모에 직접 쓰면 상처가 된다. 두바이 쫀득 쿠키의 퍽퍽한 실패작, 어색한 CG('밤티 호랑이') 같은 사물 평가가 안전한 용법.",
      plain: "촌스러운", gens: ["10s", "20s"], regions: ["KR"], since: "2026-05-10" },
    en: { definition: "Tacky, off, a bit clumsy-looking — said of outfits, designs or CGI that feel amateurish. In 2026 it also gained a 'clumsy but oddly endearing' shade.", expansion: null, origin: "Started as one user's nickname in the avatar game LINE PLAY (first wave 2020). Dug up again in 2025 on X and women's communities, then spread via fan art, Reels and TikTok.", nuance: "Controversial because it is a real person's nickname turned insult. Hurtful when aimed at someone's looks; safer for objects (a failed Dubai cookie, awkward movie CGI).", plain: "tacky" },
    evidence: [
      ["news", "khan.co.kr", "과잉의 미학·의도된 어설픔…요즘 신조어 '중티·밤티'", "2026-05-02", "단순 비하를 넘어 복합적인 감각을 전달하는 말로 확장"],
      ["short", "youtube.com", "밤티 코디 vs 영크크 코디 챌린지", "2026-08-14", "10대 패션 채널. 댓글 '이거 완전 밤티난다'"],
      ["news", "thetrippick.com", "밤티·야르·아자스가 뭐야? 인스타에서 유행하는 2026 밈 뜻", "2026-07-15"],
      ["web", "namu.wiki", "밤티 - 나무위키", "2026-09-03", "'길티 밤티' — 촌스럽고 못생겼지만 묘하게 끌리는 매력"],
    ],
    usage: [["KR", "20s", "2025-09-01", 0.5], ["KR", "10s", "2025-11-10", 0.4], ["KR", "30s", "2026-05-01", 0.1]],
    weekly: [20, 22, 25, 24, 28, 30, 33, 35, 38, 40, 44, 47],
  }),
  rec({
    id: "t_jungti", canonical: "중티", aliases: ["중티나다", "중티난다"], category: "slang", lifecycle: "rising", first: "2026-01-15",
    ko: { definition: "'중국 티 난다'의 줄임말. 디자인이나 스타일이 과하게 화려하거나 어딘가 어설퓨 보인다는 평가.",
      expansion: "중국 티 (난다)", origin: "한·중 커플 크리에이터 '여단오'의 영상에서 비롯됐고, 2026년 봄 '밤티'와 짝을 이뤄 퍼졌다.",
      nuance: "국적을 빗댄 표현이라 비하로 읽힐 수 있다. 공개 문구·상품 설명에는 부적절하고, 친구 사이 농담에 머문다.",
      plain: "과하게 화려한", gens: ["10s", "20s"], regions: ["KR"], since: "2026-05-10" },
    en: { definition: "Short for '중국 티 난다' ('looks Chinese-made'): overdone, flashy or slightly clumsy design.", expansion: "중국 티 (난다)", origin: "From videos by the Korean-Chinese couple creator 여단오; paired with 밤티 in spring 2026.", nuance: "Leans on a nationality stereotype and can read as derogatory. Fine as a joke among friends, not in public copy.", plain: "over-the-top" },
    evidence: [
      ["news", "khan.co.kr", "과잉의 미학·의도된 어설픔…요즘 신조어 '중티·밤티'", "2026-05-02"],
      ["short", "youtube.com", "중티 vs 밤티 구분법", "2026-07-30"],
      ["web", "kaehaelab.com", "2026 신조어 사전 — 요즘 유행어 뜻 총정리", "2026-08-01"],
    ],
    usage: [["KR", "20s", "2026-01-20", 0.55], ["KR", "10s", "2026-03-01", 0.45]],
    weekly: [8, 9, 10, 12, 12, 14, 15, 17, 18, 20, 22, 24],
  }),
  rec({
    id: "t_yar", canonical: "야르", aliases: ["꺄르", "할렐야루", "야르~"], category: "slang", lifecycle: "peak", first: "2026-03-01",
    ko: { definition: "'앗싸', '오예' 같은 신남의 감탄사. 좋은 일이 생겼을 때 짧게 외친다.",
      expansion: null, origin: "예전부터 쓰이던 감탄사가 2026년 숏폼과 인스타 댓글에서 다시 유행. '꺄르'(꺅+야르), '할렐야루'(할렐루야+야르) 같은 상위 버전이 붙었다.",
      nuance: "가볍고 귀여운 톤. 뜻은 없고 기분만 전달한다.",
      plain: "앗싸", gens: ["10s"], regions: ["KR"], since: "2026-06-01" },
    en: { definition: "An exclamation of glee, like 'yay!' or 'woo!'.", expansion: null, origin: "An old interjection revived in 2026 by short-form videos and Instagram comments; upgraded forms 꺄르 and 할렐야루 ('hallelu-yar') followed.", nuance: "Light and cute. Carries mood, not meaning.", plain: null },
    evidence: [
      ["news", "thetrippick.com", "밤티·야르·아자스가 뭐야? 인스타에서 유행하는 2026 밈 뜻", "2026-07-15", "'야르'는 '앗싸', '오예', '신난다' 같은 의미를 가진 감탄사"],
      ["news", "news.nate.com", "[카드뉴스] 2026 상반기 신조어 총정리…'신조어 활용 가이드'", "2026-07-24"],
      ["short", "youtube.com", "할렐야루 모음", "2026-08-09"],
    ],
    usage: [["KR", "10s", "2026-03-05", 0.7], ["KR", "20s", "2026-04-15", 0.3]],
    weekly: [30, 34, 38, 42, 45, 47, 50, 52, 51, 53, 52, 54],
  }),
  rec({
    id: "t_shagal", canonical: "샤갈", aliases: ["아 샤갈", "샤갈이네"], category: "slang", lifecycle: "steady", first: "2025-11-01",
    ko: { definition: "욕설('씨X')을 순화해 부르는 감탄사. 놀람·당황·짜증·어이없음에 \"아 샤갈\"처럼 붙인다.",
      expansion: null, origin: "게임·SNS 댓글에서 욕설 필터를 피하려 쓰이다 2026년 밈으로 굳었다. 화가 샤갈과는 관계없다.",
      nuance: "순화형이지만 뿌리는 욕설이다. 어른·공적인 자리에서는 욕으로 들린다. 화가 마르크 샤갈 이야기와 헷갈릴 수 있다.",
      plain: null, gens: ["10s", "20s"], regions: ["KR"], since: "2026-06-01" },
    en: { definition: "A softened stand-in for a Korean swear word, used as an exclamation of surprise, annoyance or disbelief ('ah, 샤갈').", expansion: null, origin: "Used in games and comment sections to dodge profanity filters, hardened into a meme in 2026. Nothing to do with the painter Chagall.", nuance: "Softened, but still a swear at heart — adults will hear it as one. Can be confused with the painter Marc Chagall.", plain: null },
    evidence: [
      ["news", "thetrippick.com", "밤티·야르·아자스가 뭐야? 인스타에서 유행하는 2026 밈 뜻", "2026-07-15", "욕설을 순화해 부르는 표현. 놀람·당황·짜증·어이없음"],
      ["web", "gatobus2025.com", "요즘신조어 총정리! 샤갈·밤티·야르·야자스·동엽이·막나귀·젬민이·테무인간…", "2026-08-05"],
    ],
    usage: [["KR", "10s", "2025-11-05", 0.6], ["KR", "20s", "2026-01-10", 0.4]],
    weekly: [26, 25, 27, 26, 28, 27, 26, 27, 28, 27, 26, 27],
  }),
  rec({
    id: "t_ajass", canonical: "아자스", aliases: ["앗자스", "아리가또 고자이마스"], category: "slang", lifecycle: "steady", first: "2025-12-01",
    ko: { definition: "'고맙습니다'. 일본어 '아리가토 고자이마스'를 극단적으로 줄인 말.",
      expansion: "아리가토 고자이마스 → 아자스", origin: "일본 갸루 문화 밈이 2025~26년 한국 숏폼으로 넘어왔다. 함께 '멘고멘고'(고멘=미안), '~야호' 인사가 쓰인다.",
      nuance: "진짜 감사 인사로도 쓰지만 가볍게 비꼬는 밈 감성이 섞이는 경우가 많다. 어른에게는 장난처럼 보일 수 있다.",
      plain: "고마워", gens: ["10s", "20s"], regions: ["KR", "JP"], since: "2026-06-01" },
    en: { definition: "'Thanks' — an extreme clipping of the Japanese ありがとうございます (arigatō gozaimasu).", expansion: "ありがとうございます → 아자스", origin: "A Japanese gyaru-culture meme that crossed into Korean short-form video in 2025–26, along with 멘고멘고 ('sorry') and '~야호' greetings.", nuance: "Sometimes sincere, often lightly ironic. Reads as a joke to older people.", plain: "thanks" },
    evidence: [
      ["news", "thetrippick.com", "밤티·야르·아자스가 뭐야? 인스타에서 유행하는 2026 밈 뜻", "2026-07-15"],
      ["short", "youtube.com", "아자스 멘고멘고 갸루 인사 따라하기", "2026-08-02"],
      ["news", "news.nate.com", "[카드뉴스] 2026 상반기 신조어 총정리…'신조어 활용 가이드'", "2026-07-24"],
    ],
    usage: [["KR", "10s", "2025-12-05", 0.6], ["KR", "20s", "2026-02-01", 0.4]],
    weekly: [18, 19, 20, 19, 21, 20, 22, 21, 22, 23, 22, 23],
  }),
  rec({
    id: "t_nanlijabeth", canonical: "난리자베스", aliases: ["슬프자베스", "행복자베스", "자베스"], category: "meme", lifecycle: "declining", first: "2026-01-20",
    ko: { definition: "'난리 났다'를 장난스럽게 늘인 말. 놀랐을 때, 호들갑 떨 때 쓴다. '[감정]+자베스'로 무한히 응용된다(슬프자베스, 행복자베스).",
      expansion: "난리 (났다) + 엘리자베스", origin: "2026년 1월 인스타 크리에이터 오상추(@oh_sangchu)가 \"2026년 유행어 배포합니다\"라며 릴스로 선포했고 실제로 유행했다. 원본 릴스 200만 회 이상.",
      nuance: "유행어를 만들겠다고 선언해 성공한 드문 사례. 가을 들어 사용이 줄고 있다.",
      plain: "난리 났다", gens: ["10s", "20s"], regions: ["KR"], since: "2026-03-01" },
    en: { definition: "A playful stretch of '난리 났다' ('it's chaos!'), used when surprised or making a fuss. Infinitely remixable as '[feeling]+자베스'.", expansion: "난리 ('chaos') + Elizabeth", origin: "Declared in January 2026 by Instagram creator 오상추 (@oh_sangchu) in a Reel titled 'releasing the 2026 slang word' — and it actually caught on (2M+ views).", nuance: "A rare case of someone announcing a slang word and succeeding. Fading by autumn 2026.", plain: "it's chaos" },
    evidence: [
      ["short", "instagram.com", "@oh_sangchu — 2026년 유행어 배포합니다", "2026-01-22", "원본 릴스. 조회수 213만"],
      ["web", "kaderra.net", "2026 상반기 밈 결산 - 윤정아·나무 챌린지·난리자베스", "2026-07-10"],
      ["news", "news.nate.com", "[카드뉴스] 2026 상반기 신조어 총정리…'신조어 활용 가이드'", "2026-07-24"],
    ],
    usage: [["KR", "10s", "2026-01-25", 0.5], ["KR", "20s", "2026-02-01", 0.45], ["KR", "30s", "2026-04-01", 0.05]],
    weekly: [70, 66, 60, 55, 50, 46, 42, 40, 36, 33, 30, 28],
  }),
  rec({
    id: "t_temuhuman", canonical: "테무인간", aliases: ["테무 인간"], category: "slang", lifecycle: "steady", first: "2025-10-01",
    ko: { definition: "겉은 화려하고 멋있어 보이지만 실속이 없는 사람.",
      expansion: "테무(중국 쇼핑앱) + 인간", origin: "테무의 '사진은 화려한데 실물은 저품질'이라는 인식에서 나왔다. 2025년 말~2026년 사람 유형 밈으로 퍼졌다.",
      nuance: "사람을 낮춰 부르는 말이다. 본인 자조로 쓰면 무난하고, 남에게 붙이면 공격이 된다.",
      plain: "겉만 번지르르한 사람", gens: ["20s", "30s"], regions: ["KR"], since: "2026-06-01" },
    en: { definition: "Someone who looks impressive on the surface but has no substance.", expansion: "Temu (the shopping app) + 인간 ('human')", origin: "From Temu's reputation for glossy product photos and cheap reality. Spread as a personality-type meme in late 2025–2026.", nuance: "Belittling. Fine as self-deprecation, an attack when aimed at others.", plain: "all show, no substance" },
    evidence: [
      ["web", "gatobus2025.com", "요즘신조어 총정리! 샤갈·밤티·야르·야자스·동엽이·막나귀·젬민이·테무인간…", "2026-08-05"],
      ["news", "harpersbazaar.co.kr", "2026년, 우리는 어떤 언어로 세상을 설명할까? 올해의 단어와 신조어 트렌드", "2026-01-10"],
    ],
    usage: [["KR", "20s", "2025-10-10", 0.5], ["KR", "30s", "2025-12-01", 0.5]],
    weekly: [22, 23, 22, 24, 23, 22, 24, 23, 25, 24, 23, 24],
  }),
  rec({
    id: "t_gemmini", canonical: "젬민이", aliases: ["젬민", "젬민이형"], category: "slang", lifecycle: "rising", first: "2026-02-01",
    ko: { definition: "점심 메뉴부터 이별까지 모든 결정을 AI(제미나이)에게 맡기는 사람.",
      expansion: "제미나이(Gemini) + -이", origin: "AI 비서가 일상화된 2026년, AI에 과의존하는 사람 유형을 놀리는 말로 생겼다.",
      nuance: "가벼운 놀림. 스스로를 '젬민이'라고 부르는 자조가 많다.",
      plain: "AI에 다 물어보는 사람", gens: ["20s", "30s"], regions: ["KR"], since: "2026-06-01" },
    en: { definition: "Someone who lets an AI assistant (Gemini) make every decision, from lunch to breakups.", expansion: "Gemini + the Korean diminutive -이", origin: "Coined in 2026 as AI assistants became everyday tools, to tease people over-reliant on them.", nuance: "Gentle teasing; often self-applied.", plain: "someone who asks AI everything" },
    evidence: [
      ["web", "gatobus2025.com", "요즘신조어 총정리! 샤갈·밤티·야르·야자스·동엽이·막나귀·젬민이·테무인간…", "2026-08-05"],
      ["short", "youtube.com", "젬민이 특: 저메추도 제미나이한테 물어봄", "2026-08-21"],
    ],
    usage: [["KR", "20s", "2026-02-05", 0.55], ["KR", "30s", "2026-03-15", 0.45]],
    weekly: [10, 11, 13, 14, 16, 17, 19, 21, 22, 24, 26, 28],
  }),
  rec({
    id: "t_aislop", canonical: "AI slop", lang: "en", aliases: ["slop", "슬롭", "AI 슬롭"], category: "slang", lifecycle: "steady", first: "2024-05-01",
    ko: { definition: "AI가 대량으로 찍어낸 저품질·반복적 콘텐츠. 인터넷을 채우는 'AI 쓰레기'.",
      expansion: "slop = (돼지) 사료 찌꺼기", origin: "2024년 영어권에서 스팸에 빗대어 쓰기 시작해 2025년 옥스퍼드·메리엄웹스터 올해의 단어 후보에 올랐다. 한국에서는 2026년 '슬롭'으로 그대로 들어왔다.",
      nuance: "콘텐츠를 향한 말이지 사람을 향한 욕은 아니다. 크리에이터 사이에서는 심한 평가로 받아들여진다.",
      plain: "AI가 찍어낸 저질 콘텐츠", gens: ["20s", "30s", "40s"], regions: ["US", "GB", "KR", "GLOBAL"], since: "2026-06-01" },
    en: { definition: "Low-quality, mass-produced AI-generated content — the digital equivalent of spam.", expansion: "slop, as in pig feed", origin: "Emerged in English-speaking tech circles in 2024 by analogy with spam; shortlisted for word-of-the-year lists in 2025. Entered Korean as 슬롭 in 2026.", nuance: "Aimed at content, not people, but creators take it as a harsh verdict.", plain: "junk AI content" },
    evidence: [
      ["news", "theguardian.com", "'Slop' — the word for the AI junk flooding the internet", "2025-11-20"],
      ["news", "harpersbazaar.co.kr", "2026년, 우리는 어떤 언어로 세상을 설명할까? 올해의 단어와 신조어 트렌드", "2026-01-10", "AI가 대량으로 생성한 저품질·반복적 콘텐츠"],
      ["web", "knowyourmeme.com", "AI Slop", "2026-02-01"],
    ],
    usage: [["US", "30s", "2024-05-01", 0.35], ["GB", "30s", "2024-08-01", 0.15], ["US", "20s", "2024-10-01", 0.2], ["KR", "30s", "2026-01-10", 0.2], ["KR", "20s", "2026-03-01", 0.1]],
    weekly: [33, 34, 32, 35, 34, 33, 36, 35, 34, 36, 35, 36],
  }),
  rec({
    id: "t_teto", canonical: "테토남", aliases: ["테토녀", "에겐남", "에겐녀", "테토", "에겐"], category: "meme", lifecycle: "declining", first: "2025-03-01",
    ko: { definition: "성격·분위기를 호르몬 이름으로 나눈 유형 밈. 테토(테스토스테론)는 활동적·주도적, 에겐(에스트로겐)은 섬세·감성적인 쪽.",
      expansion: "테스토스테론 남자 / 에스트로겐 남자·여자", origin: "2025년 봄 온라인 커뮤니티 성격 분류 놀이에서 시작해 예능·광고까지 갔다. MBTI 뒤를 잇는 유형 밈.",
      nuance: "과학적 근거는 없다. 2026년에는 유행이 지나 반어적으로 쓰이거나 '아직 이걸 쓰네' 취급을 받는다.",
      plain: "활동적인 스타일", gens: ["20s", "30s"], regions: ["KR"], verification: "verified_human", since: "2025-10-12" },
    en: { definition: "A personality-typing meme that sorts people by hormone name: 테토 (testosterone) = active and assertive, 에겐 (estrogen) = sensitive and emotional.", expansion: "testosterone man / estrogen man·woman", origin: "Started as an online-community typing game in spring 2025 and reached TV and ads — the successor to MBTI mania.", nuance: "No scientific basis. By 2026 it is dated; using it earnestly reads as behind the times.", plain: "the assertive type" },
    evidence: [
      ["news", "n.news.naver.com", "테토남·에겐녀… MBTI 잇는 유형 밈, 근거는?", "2025-08-12"],
      ["web", "namu.wiki", "테토남 - 나무위키", "2026-05-01"],
      ["datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13", "2025-07 피크 후 하락. 20대 → 30대 → 40대 순으로 확산 후 소멸 중"],
    ],
    usage: [["KR", "20s", "2025-03-05", 0.5], ["KR", "30s", "2025-04-20", 0.35], ["KR", "40s", "2025-08-01", 0.15]],
    weekly: [40, 38, 35, 33, 30, 28, 27, 25, 24, 22, 21, 20],
  }),
  rec({
    id: "t_yoonjunga", canonical: "윤정아 챌린지", aliases: ["윤정아 윤정아", "왜요 쌤", "윤정아"], category: "meme", lifecycle: "declining", first: "2026-01-05",
    ko: { definition: "\"윤정아 윤정아 / 왜요 쌤\"을 주고받는 상황극 챌린지. 2026년 상반기 가장 큰 밈.",
      expansion: null, origin: "2026년 1월 5일 초등학교 6학년 두 명이 올린 영상이 시작. 개그우먼 정이랑의 콩트 '쇼팽피아노학원'의 서윤정 선생님 캐릭터를 따라 만들었고, 아이린·효연·고윤정 등이 참여하며 연예계 놀이로 커졌다.",
      nuance: "따라 하기가 쉬워 폭발적으로 퍼졌고 그만큼 빨리 식었다. 가을에는 '한물간' 느낌.",
      plain: null, gens: ["10s", "20s"], regions: ["KR"], since: "2026-02-01" },
    en: { definition: "A call-and-response skit challenge — '윤정아 윤정아' / '왜요 쌤' ('Yoonjung-ah!' / 'What, teacher?'). The biggest Korean meme of the first half of 2026.", expansion: null, origin: "Started on 5 January 2026 with a video by two sixth-graders imitating a piano-teacher character from comedian 정이랑's sketch; idols and actors joined in.", nuance: "Spread explosively because anyone could do it, and cooled just as fast. By autumn it feels dated.", plain: null },
    evidence: [
      ["short", "youtube.com", "윤정아 윤정아 / 왜요 쌤 원본", "2026-01-05", "김지윤·편다은 원본 영상"],
      ["web", "kaderra.net", "2026 상반기 밈 결산 - 윤정아·나무 챌린지·난리자베스", "2026-07-10", "상반기 밈의 중심"],
      ["web", "oflouis.dev", "2026 상반기 유행 밈 총정리", "2026-07-05"],
    ],
    usage: [["KR", "10s", "2026-01-06", 0.6], ["KR", "20s", "2026-01-20", 0.3], ["KR", "30s", "2026-02-15", 0.1]],
    weekly: [90, 80, 70, 60, 50, 42, 36, 30, 26, 22, 18, 15],
  }),
  rec({
    id: "t_namu", canonical: "나무 챌린지", aliases: ["나무챌린지"], category: "dance", lifecycle: "declining", first: "2026-02-05",
    ko: { definition: "카더가든의 노래 '나무'에 맞춰 나무처럼 서서 팔을 허우적대며 흔드는 춤 챌린지.",
      expansion: null, origin: "2026년 2월 초 AIMERS 채널의 쇼츠가 원본. 정해진 안무가 없어 누구나 할 수 있어 2월 말부터 유튜브 쇼츠·틱톡에 퍼졌다.",
      nuance: "봄 밈. 가을에는 거의 보이지 않는다.",
      plain: null, gens: ["10s", "20s"], regions: ["KR"], since: "2026-03-01" },
    en: { definition: "A dance challenge to Car, the garden's song '나무' ('Tree'): stand like a tree and flail your arms.", expansion: null, origin: "Originated in early February 2026 with a Short on the AIMERS channel; spread on YouTube Shorts and TikTok from late February because there is no choreography to learn.", nuance: "A spring meme; nearly gone by autumn.", plain: null },
    evidence: [
      ["short", "youtube.com", "AIMERS — 나무 챌린지 원본", "2026-02-06"],
      ["news", "blog.hsad.co.kr", "이달의 트렌드 밈집 — 나무 챌린지, 아기 원숭이 펀치, 젓가락 워킹", "2026-03-30"],
    ],
    usage: [["KR", "20s", "2026-02-10", 0.5], ["KR", "10s", "2026-02-25", 0.5]],
    weekly: [30, 24, 18, 14, 10, 8, 6, 5, 4, 3, 2, 2],
  }),
  rec({
    id: "t_dujjonku", canonical: "두쫀쿠", aliases: ["두바이 쫀득 쿠키", "두바이 쫀득쿠키"], category: "product", lifecycle: "declining", first: "2025-08-01",
    ko: { definition: "피스타치오 스프레드와 카다이프를 넣어 쫀득하게 만든 '두바이 쫀득 쿠키'. 2025년 하반기 최고 히트 간식.",
      expansion: "두바이 쫀득 쿠키", origin: "두바이 초콜릿 유행(2024)의 후속. 2025년 여름 편의점·카페가 앞다퉈 출시했고 실패작을 '밤티'라고 놀리는 밈이 함께 돌았다.",
      nuance: "먹을 것 유행은 한 계절. 2026년 가을에는 '작년 거' 취급.",
      plain: "두바이 쫀득 쿠키", gens: ["10s", "20s", "30s"], regions: ["KR"], verification: "verified_human", since: "2025-10-12" },
    en: { definition: "'Dubai chewy cookie' — a cookie filled with pistachio spread and kadayif. The hit snack of late 2025.", expansion: "두바이 ('Dubai') 쫀득 ('chewy') 쿠키 ('cookie')", origin: "Follow-up to the 2024 Dubai-chocolate craze; convenience stores and cafés rushed it out in summer 2025, and failed versions were mocked as 밤티.", nuance: "Food fads last a season; by autumn 2026 it is 'last year's thing'.", plain: "Dubai chewy cookie" },
    evidence: [
      ["news", "n.news.naver.com", "편의점 '두쫀쿠' 전쟁… 하루 20만 개 팔린다", "2025-09-18"],
      ["web", "namu.wiki", "두바이 쫀득 쿠키 - 나무위키", "2026-01-15"],
      ["datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13", "2025-09 피크(100) → 2026-09 지수 12"],
    ],
    usage: [["KR", "20s", "2025-08-05", 0.4], ["KR", "10s", "2025-08-20", 0.35], ["KR", "30s", "2025-09-10", 0.25]],
    weekly: [45, 40, 36, 33, 30, 28, 25, 23, 21, 20, 18, 17],
  }),
  rec({
    id: "t_chugumi", canonical: "추구미", aliases: ["추구미다", "내 추구미"], category: "slang", lifecycle: "steady", first: "2024-02-01",
    ko: { definition: "내가 되고 싶은 모습, 지향하는 이미지·스타일. \"내 추구미는 청순\"처럼 쓴다.",
      expansion: "추구(하는) + 미(美)", origin: "2024년 아이돌 팬덤과 뷰티 커뮤니티에서 시작해 일반어가 됐다.",
      nuance: "부정적 뉘앙스 없음. 40대 이상에게는 낯설 수 있다.",
      plain: "지향하는 스타일", gens: ["10s", "20s", "30s"], regions: ["KR"], verification: "verified_human", since: "2025-10-12" },
    en: { definition: "The look or image you aspire to — 'my 추구미 is clean-girl', for example.", expansion: "추구 ('pursue') + 미 ('beauty')", origin: "Started in idol fandoms and beauty communities in 2024 and became everyday vocabulary.", nuance: "Neutral. Unfamiliar to many over 40.", plain: "the look I'm going for" },
    evidence: [
      ["web", "namu.wiki", "추구미 - 나무위키", "2026-03-01"],
      ["short", "youtube.com", "내 추구미 찾는 법 (퍼스널 컬러 X)", "2026-08-11"],
    ],
    usage: [["KR", "20s", "2024-02-05", 0.5], ["KR", "10s", "2024-04-01", 0.3], ["KR", "30s", "2024-09-01", 0.2]],
    weekly: [28, 27, 29, 28, 30, 29, 28, 30, 29, 28, 30, 29],
  }),
  rec({
    id: "t_neujot", canonical: "느좋", aliases: ["느낌 좋다", "느좋이다"], category: "slang", lifecycle: "steady", first: "2023-06-01",
    ko: { definition: "'느낌 좋다'의 줄임말. 분위기나 무드가 좋다는 뜻.",
      expansion: "느낌 좋다", origin: "2023년경 SNS 캡션에서 시작. 카페·사진·사람 어디에나 붙인다.",
      nuance: "칭찬. 구체적으로 뭐가 좋은지 말하지 않는 두루뭉술함이 특징.",
      plain: "느낌 좋다", gens: ["10s", "20s"], regions: ["KR"], verification: "verified_human", since: "2025-10-12" },
    en: { definition: "Short for '느낌 좋다' — 'good vibe'. Said of places, photos and people alike.", expansion: "느낌 좋다 ('the feeling is good')", origin: "Emerged in SNS captions around 2023.", nuance: "A compliment that deliberately doesn't say what exactly is good.", plain: "good vibe" },
    evidence: [
      ["web", "namu.wiki", "느좋 - 나무위키", "2026-01-20"],
      ["short", "youtube.com", "느좋 카페 브이로그", "2026-09-01"],
    ],
    usage: [["KR", "20s", "2023-06-05", 0.6], ["KR", "10s", "2023-09-01", 0.4]],
    weekly: [24, 25, 24, 26, 25, 24, 26, 25, 26, 25, 24, 25],
  }),
  rec({
    id: "t_jeommechu", canonical: "점메추", aliases: ["점메추좀"], category: "slang", lifecycle: "steady", first: "2017-01-01",
    ko: { definition: "점심 메뉴를 추천해 달라는 말. 저메추(저녁), 아메추(아침)의 원형.",
      expansion: "점심 메뉴 추천", origin: "2010년대 후반 직장인·대학생 커뮤니티에서 매일 반복되는 게시글 제목으로 굳었다.",
      nuance: "친한 사이의 구어. 매일 점심 무렵 검색량이 튀는 전형적인 생활 유행어.",
      plain: "점심 메뉴 추천", gens: ["20s", "30s"], regions: ["KR"], verification: "verified_human", since: "2025-10-12" },
    en: { definition: "Asking for a lunch recommendation. The original of 저메추 (dinner) and 아메추 (breakfast).", expansion: "점심 메뉴 추천 ('lunch menu recommendation')", origin: "Became a daily post title in office-worker and student communities in the late 2010s.", nuance: "Casual. Search volume spikes every day around noon.", plain: "a lunch suggestion" },
    evidence: [
      ["community", "theqoo.net", "점메추 좀", "2026-09-11", "매일 11시대 반복 게시글"],
      ["datalab", "datalab.naver.com", "검색 추이 · 연령대별", "2026-09-13", "요일·시간 주기성만 있음. 전 연령 평탄"],
    ],
    usage: [["KR", "20s", "2017-01-01", 0.5], ["KR", "30s", "2017-06-01", 0.5]],
    weekly: [21, 22, 21, 23, 22, 21, 23, 22, 23, 22, 21, 22],
  }),
  rec({
    id: "t_banosip", canonical: "반 오십", aliases: ["반오십"], category: "slang", lifecycle: "steady", first: "2024-01-01",
    ko: { definition: "스물다섯 살. 오십의 절반이라는 뜻으로, 자기 나이가 많다고 과장하는 자조 표현.",
      expansion: "50의 반 = 25", origin: "Z세대 사이에서 나이 많음을 강조하는 밈이 이어지는 흐름 속에서 굳었다. 늙크크와 같은 정서.",
      nuance: "농담. 실제 25세 이상인 사람 앞에서 쓰면 눈치 없어 보인다.",
      plain: "스물다섯", gens: ["20s"], regions: ["KR"], since: "2026-06-01" },
    en: { definition: "'Half of fifty' — twenty-five, said as a mock-dramatic way of calling yourself old.", expansion: "반 ('half') + 오십 ('fifty')", origin: "Part of a Gen Z streak of jokingly overstating one's age; same spirit as 늙크크.", nuance: "A joke. Sounds tone-deaf around people actually over 25.", plain: "twenty-five" },
    evidence: [
      ["news", "careet.net", "도대체 어디서 시작된 거야? 요즘 SNS에서 뜨는 밈 모음", "2026-08-20", "'반 오십' 등 자신의 나이가 많다는 점을 강조하는 밈"],
    ],
    usage: [["KR", "20s", "2024-01-05", 1]],
    weekly: [12, 12, 13, 12, 14, 13, 12, 13, 14, 13, 12, 13],
  }),
  rec({
    id: "t_tungtung", canonical: "Tung Tung Tung Sahur", lang: "en", aliases: ["퉁퉁퉁퉁 사후르", "퉁퉁 사후르", "tung tung sahur"], category: "meme", lifecycle: "declining", first: "2025-02-01",
    ko: { definition: "생성형 AI로 만든 기괴하고 귀여운 캐릭터에 이탈리아 억양 나레이션을 붙인 '이탈리안 브레인로트' 밈의 대표 캐릭터. 야구방망이를 든 나무 통 캐릭터가 \"퉁퉁퉁퉁 사후르\"를 반복한다.",
      expansion: null, origin: "2025년 초 인도네시아 틱톡에서 시작(사후르는 라마단 새벽 식사). 이탈리아풍 이름을 붙인 AI 캐릭터 시리즈로 전 세계에 퍼졌고, 한국 상반기 밈 TOP 10에도 들었다.",
      nuance: "10대 안에서만 통한다. 뜻이 없는 것이 핵심. 2026년 들어 급격히 식었다.",
      plain: null, gens: ["10s"], regions: ["ID", "US", "KR", "GLOBAL"], since: "2026-03-01" },
    en: { definition: "The flagship character of 'Italian brainrot' — AI-generated, absurd creatures with Italian-accented narration. A wooden log with a baseball bat chanting 'tung tung tung sahur'.", expansion: null, origin: "Started on Indonesian TikTok in early 2025 (sahur is the pre-dawn Ramadan meal), spread worldwide as a series of Italian-named AI characters.", nuance: "Teen in-group nonsense; the lack of meaning is the point. Cooled sharply in 2026.", plain: null },
    evidence: [
      ["web", "knowyourmeme.com", "Tung Tung Tung Sahur", "2025-06-01"],
      ["news", "letter.wepick.kr", "2026 트렌디한 밈 아카이브.ZIP", "2026-07-01", "해외발 브레인로트 밈 — \"퉁퉁퉁퉁 사후르~\""],
      ["short", "youtube.com", "Tung Tung Tung Sahur original", "2025-03-10"],
    ],
    usage: [["ID", "10s", "2025-02-05", 0.4], ["US", "10s", "2025-03-15", 0.3], ["KR", "10s", "2025-05-01", 0.3]],
    weekly: [12, 10, 8, 7, 6, 5, 4, 3, 3, 2, 2, 1],
  }),
];
