/* 예시 데이터 (2026-09-14). 검색어·영상 제목은 09-14 실측(Google Trends BigQuery·RSS, YouTube mostPopular)에서 가져왔고,
   패션·뷰티와 일부 나라의 항목·주간 수치는 가정치. 전파 경로의 날짜는 공개 보도 기준, '가정' 표시가 있는 것은 추정. */
import { SAMPLE_RECORDS } from "./dictionary";
import type { Change, Text2, Topic, TopicVariant, TrendBoard, TrendCategory, TrendItem } from "../trends/types";

const idOf = (canonical: string) => SAMPLE_RECORDS.find((r) => r.term.canonical === canonical)?.term.term_id;

const up = (a: number, b: number) => Array.from({ length: 12 }, (_, i) => Math.round(a + ((b - a) * i) / 11));
const down = (a: number, b: number) => up(a, b);
const flat = (v: number) => Array.from({ length: 12 }, (_, i) => v + ((i * 7) % 3) - 1);
const spike = (base: number, peak: number) => [...flat(base).slice(0, 10), Math.round((base + peak) / 2), peak];

let n = 0;
function it(
  region: string,
  category: TrendCategory,
  term: string,
  rank: number,
  change: Change,
  weekly: number[],
  note: { ko: string; en: string },
  extra: { term?: string; term_id?: string; topic_id?: string; gain_pct?: number } = {},
): TrendItem {
  n += 1;
  return { id: `ti_${n}`, region, category, term, rank, change, weekly, note, term_id: extra.term_id ?? idOf(extra.term ?? term), topic_id: extra.topic_id, gain_pct: extra.gain_pct };
}

const ITEMS: TrendItem[] = [
  // ── 한국 ──
  it("KR", "slang_meme", "삐에로 밈", 1, "new", spike(0, 95), { ko: "'선배삐·개대박삐' 식으로 말끝에 삐를 붙이는 놀이. 8월 13일 결혼 고민글에서", en: "Sticking 삐 (clown) onto any word; from an Aug 13 community post" }),
  it("KR", "slang_meme", "영크크", 2, "flat", flat(60), { ko: "젊은 감각을 뜻하는 말. 반대는 늙크크", en: "'Young creator crew' vibe; the opposite is 늙크크" }),
  it("KR", "slang_meme", "라을라", 3, "down", down(40, 10), { ko: "하품 소리를 성악 톤으로 내는 밈", en: "An operatic yawn sound" }),
  it("KR", "song_challenge", "야르송", 1, "down", down(60, 26), { ko: "'야르~'를 반복하는 노래. 알람·커버로 퍼짐", en: "A song that yodels 야르; alarms and covers" }),
  it("KR", "song_challenge", "자려고 누웠는데 양의지", 2, "down", down(80, 16), { ko: "아이오아이 노래와 야구 응원가를 합친 말장난", en: "A pun merging an I.O.I lyric with a baseball chant" }),
  it("KR", "fashion_beauty", "발레코어", 1, "flat", flat(30), { ko: "리본·레그워머·새틴 플랫으로 발레 무드를 내는 옷차림 (가정)", en: "Ballet-inspired ribbons, leg warmers and satin flats (assumed)" }),
  it("KR", "fashion_beauty", "밤티 룩", 2, "up", up(8, 22), { ko: "일부러 촌스럽게 입는 반어적 스타일링. 유행어 밤티에서 (가정)", en: "Deliberately dated styling, from the slang 밤티 (assumed)" }, { term: "밤티" }),
  it("KR", "food", "두쫀쿠", 1, "down", down(70, 25), { ko: "두바이 쫀득 쿠키. 2025년 하반기 히트 간식", en: "Dubai chewy cookie, the hit snack of late 2025" }, { topic_id: "t_dujjonku" }),
  it("KR", "food", "천연 위고비", 2, "flat", flat(15), { ko: "삶은 달걀·올리브오일 조합을 다이어트 약에 빗댄 말", en: "Eggs with olive oil, nicknamed after the weight-loss drug" }),
  it("KR", "food", "두바이 초콜릿", 3, "down", down(30, 10), { ko: "피스타치오·카다이프가 든 초콜릿. 2025년 품절 대란", en: "Pistachio-kataifi chocolate; sold out through 2025" }, { topic_id: "t_dubaichoc" }),
  it("CN", "product", "拉布布", 1, "flat", flat(60), { ko: "라부부. 팝마트 블라인드 박스 대표 상품", en: "Labubu, Pop Mart's flagship blind-box toy" }, { topic_id: "t_labubu" }),
  it("AE", "food", "Dubai chocolate", 1, "flat", flat(30), { ko: "원조 피스타치오·카다이프 초콜릿 바", en: "The original pistachio-kataifi bar" }, { topic_id: "t_dubaichoc" }),
  it("KR", "product", "라부부", 1, "down", down(50, 20), { ko: "팝마트 키링 인형. 2025년 세계적 품절", en: "Pop Mart keychain doll, a 2025 global sellout" }, { topic_id: "t_labubu" }),
  it("KR", "product", "기아 스포티지", 2, "up", spike(10, 40), { ko: "9월 13일 급상승 검색어 12위", en: "No. 12 rising search on Sep 13" }, { gain_pct: 2700 }),
  it("KR", "people_content", "오징어 게임", 1, "flat", flat(45), { ko: "넷플릭스 시리즈. 시즌3(2025-06) 뒤에도 밈이 이어짐", en: "The Netflix series; memes continued after season 3 (Jun 2025)" }, { topic_id: "t_squid" }),
  it("KR", "people_content", "케데헌", 2, "down", down(90, 40), { ko: "'케이팝 데몬 헌터스'. 2025년 넷플릭스 최다 시청 애니메이션", en: "'KPop Demon Hunters', Netflix's most-watched animated film of 2025" }),
  it("KR", "people_content", "배용준", 3, "new", spike(2, 65), { ko: "9월 13일 급상승 3위", en: "No. 3 rising search on Sep 13" }, { gain_pct: 6500 }),
  it("KR", "sports_event", "토트넘 대 에버턴", 1, "new", spike(0, 55), { ko: "프리미어리그. 9월 13일 급상승 4위", en: "Premier League; No. 4 rising search on Sep 13" }, { gain_pct: 5350 }),
  it("KR", "sports_event", "한화 대 KIA", 2, "up", up(20, 40), { ko: "KBO 순위 싸움", en: "KBO pennant race" }),
  // ── 일본 ──
  it("JP", "slang_meme", "推し活", 1, "flat", flat(50), { ko: "좋아하는 대상을 응원하는 활동 전반", en: "Fan activities for one's favorite" }),
  it("JP", "slang_meme", "シックスセブン", 2, "up", up(10, 30), { ko: "미국 '6-7' 밈의 일본 표기", en: "Japanese rendering of the US '6-7' meme" }, { term: "6-7", topic_id: "t_sixseven" }),
  it("JP", "song_challenge", "時空超えてユニバース", 1, "new", spike(0, 42), { ko: "M!LK 신곡 티저. 9월 14일 인기 영상", en: "M!LK teaser, trending video on Sep 14" }),
  it("JP", "fashion_beauty", "地雷系", 1, "flat", flat(20), { ko: "검정·핑크 프릴, 창백한 메이크업의 스타일 (가정)", en: "Black-and-pink frills with pale makeup (assumed)" }),
  it("JP", "food", "ドバイチョコ", 1, "down", down(35, 12), { ko: "두바이 초콜릿", en: "Dubai chocolate" }, { topic_id: "t_dubaichoc" }),
  it("JP", "food", "韓国もちクッキー", 2, "up", up(5, 18), { ko: "한국 두쫀쿠의 일본 이름 (가정)", en: "Japanese name for Korea's 두쫀쿠 (assumed)" }, { topic_id: "t_dujjonku" }),
  it("JP", "product", "ラブブ", 1, "down", down(40, 15), { ko: "라부부", en: "Labubu" }, { topic_id: "t_labubu" }),
  it("JP", "people_content", "八つ墓村", 1, "new", spike(0, 38), { ko: "9월 18일 개봉 영화 예고. 인기 영상 3위", en: "Film opening Sep 18; No. 3 trending video" }),
  it("JP", "people_content", "森本レオ", 2, "new", spike(0, 70), { ko: "9월 13일 급상승 1위", en: "No. 1 rising search on Sep 13" }, { gain_pct: 12850 }),
  it("JP", "people_content", "イカゲーム", 3, "flat", flat(25), { ko: "오징어 게임", en: "Squid Game" }, { topic_id: "t_squid" }),
  it("JP", "sports_event", "沖縄県知事選挙", 1, "new", spike(0, 100), { ko: "오키나와 지사 선거. 9월 13일 상위 1위", en: "Okinawa governor election; No. 1 search on Sep 13" }),
  it("JP", "sports_event", "巨人 対 阪神", 2, "up", up(20, 45), { ko: "프로야구", en: "Pro baseball" }),
  it("JP", "sports_event", "花火大会", 3, "down", down(60, 20), { ko: "불꽃놀이. 여름이 끝나며 하락", en: "Fireworks festivals, fading with summer" }),
  // ── 인도네시아 ──
  it("ID", "slang_meme", "Tung Tung Tung Sahur", 1, "down", down(50, 15), { ko: "이탈리안 브레인로트 대표. 인도네시아 사후르 문화에서", en: "Italian-brainrot icon rooted in the sahur tradition" }, { topic_id: "t_tung" }),
  it("ID", "slang_meme", "galau", 2, "flat", flat(35), { ko: "마음이 복잡하고 우울한 상태", en: "Restless, gloomy indecision" }),
  it("ID", "slang_meme", "aura farming", 3, "down", down(45, 20), { ko: "멋 부리는 행동. 파쿠 잘루르 보트 소년 영상에서 세계로", en: "Posing for 'aura'; went global from the Pacu Jalur boat-kid clip" }, { topic_id: "t_aura" }),
  it("ID", "food", "Dubai chocolate", 1, "down", down(30, 10), { ko: "두바이 초콜릿", en: "Dubai chocolate" }, { topic_id: "t_dubaichoc" }),
  it("ID", "product", "Labubu", 1, "down", down(45, 18), { ko: "라부부", en: "Labubu" }, { topic_id: "t_labubu" }),
  it("ID", "sports_event", "persija jakarta vs persib bandung", 1, "new", spike(0, 98), { ko: "리가 1 더비. 9월 13일 급상승 1위", en: "Liga 1 derby; No. 1 rising search on Sep 13" }, { gain_pct: 9800 }),
  it("ID", "sports_event", "okultasi venus", 2, "new", spike(0, 30), { ko: "금성 엄폐 천문 현상. 9월 14일 지금 뜨는 검색어", en: "Venus occultation; trending on Sep 14" }),
  // ── 미국 ──
  it("US", "slang_meme", "6-7", 1, "flat", flat(70), { ko: "뜻 없는 감탄사. 2025년 하반기 최대 밈", en: "A meaningless exclamation, the biggest meme of late 2025" }, { topic_id: "t_sixseven" }),
  it("US", "slang_meme", "La Peace", 2, "new", spike(0, 72), { ko: "카이 세넛의 '라피스' 발음 밈", en: "Kai Cenat's mispronounced 'lapis'" }),
  it("US", "slang_meme", "Ronaldo Pasta", 3, "up", up(10, 44), { ko: "MrBeast 영상 속 파스타 장면 편집물", en: "Edits of the pasta scene from a MrBeast video" }, { topic_id: "t_ronaldo" }),
  it("US", "slang_meme", "skibidi", 4, "down", down(30, 8), { ko: "뜻 없이 붙이는 감탄·수식어", en: "A filler word with no fixed meaning" }),
  it("US", "song_challenge", "Three Layer Dip Stack", 1, "up", up(5, 80), { ko: "프링글스 광고 대사를 노래로 만든 브레인로트", en: "Brainrot song from a Pringles ad line" }),
  it("US", "song_challenge", "Remember November 2026 Is Coming", 2, "new", spike(0, 40), { ko: "AI 북극곰이 부르는 '미래에서 온 밈'", en: "An AI polar bear's 'meme from the future'" }),
  it("US", "song_challenge", "Wow okay", 3, "down", down(50, 18), { ko: "같은 말을 네 가지 톤으로 연기하는 챌린지", en: "Say one line in four tones" }),
  it("US", "song_challenge", "I forgot my AirPods", 4, "down", down(55, 12), { ko: "옆 사람이 노래를 대신 불러 주는 상황극", en: "Your friend sings in place of your earbuds" }),
  it("US", "fashion_beauty", "office siren", 1, "flat", flat(25), { ko: "얇은 안경·펜슬 스커트의 사무실 룩 (가정)", en: "Thin glasses and pencil skirts (assumed)" }),
  it("US", "food", "viral Crumbl Labubu cookie", 1, "down", down(70, 16), { ko: "유행 먹거리를 전부 한 이름에 넣은 풍자 시식 밈. '한국 쫀득 쿠키'도 들어 있다", en: "Satirical taste-test cramming every food trend into one name, Korean chewy cookie included" }, { topic_id: "t_dujjonku" }),
  it("US", "food", "Dubai chocolate", 2, "down", down(40, 15), { ko: "두바이 초콜릿", en: "Dubai chocolate" }, { topic_id: "t_dubaichoc" }),
  it("US", "product", "Labubu", 1, "down", down(60, 22), { ko: "라부부", en: "Labubu" }, { topic_id: "t_labubu" }),
  it("US", "product", "GTA 6", 2, "new", spike(10, 60), { ko: "배우 캐스팅 소식으로 9월 14일 급상승", en: "Trending Sep 14 on a casting confirmation" }),
  it("US", "people_content", "Pluribus", 1, "new", spike(0, 45), { ko: "시즌 2 소식으로 9월 14일 지금 뜨는 검색어", en: "Trending Sep 14 on season 2 news" }),
  it("US", "people_content", "Squid Game", 2, "flat", flat(30), { ko: "오징어 게임", en: "Squid Game" }, { topic_id: "t_squid" }),
  // ── 영국 ──
  it("GB", "slang_meme", "six seven", 1, "down", down(60, 30), { ko: "6-7", en: "6-7" }, { term: "6-7", topic_id: "t_sixseven" }),
  it("GB", "sports_event", "leeds vs newcastle", 1, "new", spike(0, 50), { ko: "프리미어리그. 9월 14일 지금 뜨는 검색어", en: "Premier League; trending Sep 14" }),
  it("GB", "sports_event", "man utd vs man city", 2, "new", spike(0, 90), { ko: "맨체스터 더비. 9월 13일 상위 1위", en: "Manchester derby; No. 1 search on Sep 13" }),
  it("GB", "food", "Dubai chocolate", 1, "down", down(35, 12), { ko: "두바이 초콜릿", en: "Dubai chocolate" }, { topic_id: "t_dubaichoc" }),
  // ── 독일 ──
  it("DE", "song_challenge", "Du Bist Gut Genug", 1, "down", down(85, 18), { ko: "블루멘가르텐 노래의 팔세토 구절. 6월 틱톡 밈", en: "Blumengarten's falsetto line; a June TikTok meme" }, { topic_id: "t_gutgenug" }),
  it("DE", "slang_meme", "Doobie Scoot Canoe", 2, "down", down(30, 8), { ko: "위 노래를 영어권이 잘못 들은 가사", en: "The English-speaking mishearing of that line" }, { term: "Du Bist Gut Genug", topic_id: "t_gutgenug" }),
  // ── 브라질 ──
  it("BR", "people_content", "Round 6", 1, "flat", flat(28), { ko: "오징어 게임의 브라질 제목. 밈도 이 이름으로", en: "Brazil's title for Squid Game; memes use this name" }, { term: "오징어 게임", topic_id: "t_squid" }),
  it("BR", "slang_meme", "Tung Tung Tung Sahur", 1, "down", down(40, 12), { ko: "이탈리안 브레인로트", en: "Italian brainrot" }, { topic_id: "t_tung" }),
  it("BR", "song_challenge", "Come To Brazil", 1, "flat", flat(22), { ko: "해외 스타 댓글마다 달리는 '브라질로 와' 밈", en: "The 'come to Brazil' comment meme" }),
  // ── 호주 ──
  it("AU", "slang_meme", "6-7", 1, "down", down(50, 25), { ko: "6-7", en: "6-7" }, { topic_id: "t_sixseven" }),
  it("AU", "sports_event", "AFL finals", 1, "up", up(20, 60), { ko: "호주식 축구 결승 시리즈 (9월)", en: "Australian football finals series (September)" }),
  // ── 인도 ──
  it("IN", "slang_meme", "6-7", 1, "down", down(45, 20), { ko: "6-7", en: "6-7" }, { topic_id: "t_sixseven" }),
  it("IN", "people_content", "Squid Game", 1, "flat", flat(20), { ko: "오징어 게임. 현지 더빙 대사 밈", en: "Squid Game; memes from the local dub" }, { term: "오징어 게임", topic_id: "t_squid" }),
  // ── 대만 · 베트남 · 태국 · 필리핀 · 멕시코 ──
  it("TW", "people_content", "魷魚遊戲", 1, "flat", flat(18), { ko: "오징어 게임", en: "Squid Game" }, { term: "오징어 게임", topic_id: "t_squid" }),
  it("VN", "slang_meme", "Tung Tung Tung Sahur", 1, "down", down(35, 10), { ko: "이탈리안 브레인로트", en: "Italian brainrot" }, { topic_id: "t_tung" }),
  it("TH", "product", "ลาบูบู้", 1, "down", down(70, 30), { ko: "라부부. 리사 효과로 태국이 첫 폭발 지역", en: "Labubu; Thailand was ground zero thanks to Lisa" }, { topic_id: "t_labubu" }),
  it("TH", "people_content", "ธี่หยด", 1, "new", spike(0, 48), { ko: "공포 영화 신작 예고. 9월 14일 인기 영상", en: "Horror sequel trailer, trending video Sep 14" }),
  it("TH", "song_challenge", "I forgot my AirPods", 1, "down", down(40, 10), { ko: "태국 크리에이터 버전이 많이 나온 상황극", en: "Skit with many Thai creator versions" }),
  it("PH", "song_challenge", "Wow okay", 1, "down", down(45, 15), { ko: "필리핀 배구 팬 버전이 화제였던 챌린지", en: "The challenge; the Filipino volleyball-fan version went viral" }),
  it("MX", "slang_meme", "Wilson! Lo siento!", 1, "down", down(40, 10), { ko: "스페인어권 1월 밈", en: "A January meme in Spanish-speaking TikTok" }),
];


const T = (ko: string, en: string): Text2 => ({ ko, en });
const v = (
  region: string, local_name: string, since: string, heat: number, what_changed: Text2,
  local_memes: { label: string; note: Text2 }[], linked: { label: string; note: Text2; term_id?: string }[] = [], term?: string,
): TopicVariant => ({ region, local_name, since, heat, what_changed, local_memes, linked, term_id: idOf(term ?? local_name) });

/* 나라를 건너간 트렌드 — 같은 주제가 나라마다 무엇으로 바뀌었는지. 날짜는 공개 보도 기준, '(가정)' 은 추정. */
const TOPICS: Topic[] = [
  {
    id: "t_squid", category: "people_content", name: T("오징어 게임", "Squid Game"),
    summary: T("2021년 한국 드라마가 나라마다 다른 것으로 번역됐다. 한국에서는 대사와 캐릭터가 말투로 남고, 미국에서는 '진짜로 해보는 것'이 됐고, 브라질에서는 제목부터 다르다.", "A 2021 Korean drama that each country translated into something else: lines and characters became everyday speech in Korea, 'doing it for real' in the US, and in Brazil even the title is different."),
    variants: [
      v("KR", "오징어 게임", "2021-09-17", 70, T("드라마 대사가 일상 말투로 남았다. 시즌2(2024-12)·3(2025-06) 뒤에는 성기훈을 부르는 '기훈이 형' 계열 대사가 댓글·짤로 돌고, 딱지치기·달고나가 다시 놀이가 됐다.", "The lines stayed in everyday speech. After seasons 2 and 3, 'Gi-hun hyung' catchphrases fill comments and image macros; ddakji and dalgona became games again."),
        [{ label: "기훈이 형 대사 밈", note: T("시즌2 이후 커뮤니티에서 성기훈에게 말을 거는 식의 댓글·짤", "Comment and image-macro format addressing Gi-hun, after season 2") }, { label: "무궁화 꽃이 피었습니다", note: T("술래 노래 재현 챌린지", "Re-enacting the game's chant") }, { label: "달고나 뽑기", note: T("편의점·노점 달고나 재유행", "Dalgona candy comeback") }],
        [{ label: "케데헌", note: T("2025년 넷플릭스 한국 콘텐츠 열풍의 다음 주자", "The next Netflix K-content wave in 2025") }]),
      v("US", "Squid Game", "2021-10-01", 100, T("'보는 것'이 아니라 '진짜로 해보는 것'으로 바뀌었다. 유튜버 MrBeast 가 상금 45만 6천 달러짜리 실사판을 만들었고(2021-11, 조회 7억 회 이상), 넷플릭스 리얼리티 '오징어 게임: 더 챌린지'(2023)와 MrBeast 의 'Beast Games'(2024)로 이어졌다.", "Turned from something you watch into something you do: MrBeast built a $456,000 real-life version (Nov 2021, 700M+ views), followed by Netflix's reality show 'Squid Game: The Challenge' (2023) and MrBeast's 'Beast Games' (2024)."),
        [{ label: "Red Light, Green Light challenge", note: T("첫 게임을 따라 하는 틱톡 챌린지", "TikTok challenge re-enacting the first game") }, { label: "Squid Game guard costume", note: T("2021년 핼러윈 최다 코스튬 중 하나", "One of the most-worn Halloween costumes of 2021") }],
        [{ label: "MrBeast — $456,000 Squid Game In Real Life!", note: T("2021-11-24 공개. 실사판 유행의 시작", "Posted 24 Nov 2021; the start of the real-life-version trend") }, { label: "Beast Games", note: T("MrBeast 의 아마존 상금 리얼리티 (2024-12)", "MrBeast's Amazon prize reality show (Dec 2024)") }]),
      v("BR", "Round 6", "2021-10-05", 62, T("브라질 제목이 'Round 6'라 밈 이름부터 다르다. 첫 게임은 더빙 이름 'Batatinha frita 1, 2, 3'로 불리고, 펑크 리믹스와 축구 클럽 패러디로 퍼졋다.", "The Brazilian title is 'Round 6', so the memes carry a different name. The first game goes by its dub name 'Batatinha frita 1, 2, 3', spread through funk remixes and football-club parodies."),
        [{ label: "Batatinha frita 1, 2, 3", note: T("'무궁화 꽃이 피었습니다'의 브라질 더빙", "Brazilian dub of the game's chant") }, { label: "Round 6 funk", note: T("주제곡 펑크 리믹스", "Funk remixes of the theme") }],
        [{ label: "Come To Brazil", note: T("해외 스타 댓글마다 달리는 브라질 밈", "The comment meme under any celebrity post") }]),
      v("JP", "イカゲーム", "2021-10-08", 48, T("첫 게임이 일본 놀이 'だるまさんがころんだ'와 같아서 비교 밈이 먹혔고, 달고나는 일본 과자 '型抜き'로 읽혔다. '카이지' 같은 일본 데스게임 작품과 비교하는 논쟁이 따라붙었다.", "The first game is the Japanese 'daruma-san ga koronda', so comparison memes landed, and dalgona was read as the Japanese candy 'katanuki'. Debates comparing it with Japanese death-game titles like 'Kaiji' followed."),
        [{ label: "だるまさんがころんだ 비교", note: T("같은 놀이라는 비교 영상", "Comparison videos with the identical game") }, { label: "型抜き 재현", note: T("달고나 뽑기의 일본판", "The Japanese counterpart of dalgona carving") }],
        [{ label: "カイジ", note: T("함께 언급된 일본 데스게임 만화", "The Japanese death-game manga it was compared with") }]),
      v("TW", "魷魚遊戲", "2021-10-10", 40, T("첫 게임은 대만 이름 '一二三木頭人'으로 불렸고, 달고나 대신 대만 전통 사탕 '椪糖'이 재유행했다. 학교 운동회 재현 영상이 많았다.", "The first game went by its Taiwanese name '一二三木頭人', and instead of dalgona the traditional candy '椪糖' came back. Lots of school sports-day re-enactments."),
        [{ label: "一二三木頭人", note: T("'무궁화 꽃이 피었습니다'의 대만 놀이 이름", "Taiwanese name of the same game") }, { label: "椪糖", note: T("달고나와 같은 대만 전통 사탕", "Traditional Taiwanese candy like dalgona") }]),
      v("IN", "Squid Game", "2021-11-01", 35, T("힌디 더빙 대사가 밈이 됐고, 크리켓·볼리우드와 섞인 '인도 버전' 패러디가 많았다.", "Hindi-dub lines became memes, and 'Indian version' parodies mixed it with cricket and Bollywood."),
        [{ label: "힌디 더빙 대사 밈", note: T("더빙판 특유의 억양을 따라 하는 영상", "Videos imitating the dub's delivery") }, { label: "인도 버전 캐스팅 밈", note: T("볼리우드 배우로 배역을 상상하는 밈", "Casting Bollywood actors in the roles") }]),
    ],
  },
  {
    id: "t_sixseven", category: "slang_meme", name: T("6-7", "6-7"),
    summary: T("뜻 없는 숫자 감탄사가 미국 초·중학생에게서 시작해 영어권을 돌고 한국·일본 초등학교까지 왔다. 나라마다 '무엇을 하며 외치는가'가 다르다.", "A meaningless number-exclamation that started with US schoolkids, toured the English-speaking world and reached Korean and Japanese primary schools. What you shout it during differs by country."),
    variants: [
      v("US", "6-7", "2025-09-01", 100, T("Skrilla 의 'Doot Doot (6 7)' 가사와 키 6피트 7인치 농구 선수 LaMelo Ball 편집 영상에서. 양손을 저울처럼 흔드는 동작이 세트. 2025년 Dictionary.com 올해의 단어.", "From Skrilla's 'Doot Doot (6 7)' and edits of 6'7\" basketball player LaMelo Ball, with the hands-as-scales gesture. Dictionary.com's 2025 word of the year."),
        [{ label: "67 Kid", note: T("경기장에서 6-7을 외친 소년 영상", "The boy shouting it at a game") }, { label: "hands-as-scales", note: T("양손을 저울처럼 흔드는 동작", "The scale gesture") }],
        [{ label: "Skrilla — Doot Doot (6 7)", note: T("원곡", "The source track") }], "6-7"),
      v("GB", "six seven", "2025-10-01", 55, T("학교에서 외치는 유행. 교사들이 수업 방해로 금지어로 삼기 시작했다.", "Shouted in classrooms; teachers began banning it as a disruption."), [{ label: "six seven ban", note: T("교실 금지 공지 밈", "Classroom-ban notices") }], [], "6-7"),
      v("AU", "6-7", "2025-11-01", 40, T("영국과 비슷하게 학교 중심. 스포츠 중계 자막에 등장하기도.", "School-centred like the UK; it even surfaced in sports broadcast captions."), [], [], "6-7"),
      v("IN", "6-7", "2026-01-05", 30, T("크리켓 편집 영상으로 퍼졌다. 점수 6·7과 맞물려 중계 밈으로.", "Spread via cricket edits, playing on scores of 6 and 7."), [{ label: "크리켓 6-7 편집", note: T("6점·7점 장면에 소리를 얹은 영상", "Sound placed over 6- and 7-run moments") }], [], "6-7"),
      v("KR", "식스 세븐", "2026-01-15", 60, T("초등생이 '식스 세븐'이라 외치며 놀고, 교사들이 뜻을 묻는 글이 커뮤니티에 올라온다. 숫자보다 영어 발음 그대로 쓴다.", "Primary-school kids shout it as '식스 세븐'; teachers ask online what it means. Used in the English pronunciation rather than as digits."), [{ label: "식스 세븐 외치기", note: T("교실·급식실에서 외치는 놀이", "Shouted in classrooms and cafeterias") }], [], "6-7"),
      v("JP", "シックスセブン", "2026-02-01", 35, T("'シックスセブン' 표기로 초등생 사이에 퍼졌다. 일본 예능 자막에 등장하며 어른들에게 알려졌다.", "Written 'シックスセブン' among schoolchildren; variety-show captions introduced it to adults."), [], [], "6-7"),
    ],
  },
  {
    id: "t_tung", category: "slang_meme", name: T("Tung Tung Tung Sahur", "Tung Tung Tung Sahur"),
    summary: T("인도네시아 라마단 문화에서 나온 AI 캐릭터가 '이탈리안 브레인로트' 세계관에 흡수돼 전 세계 초등생 밈이 됐다. 원래 뜻(사후르를 깨우는 북소리)은 인도네시아 밖에서는 거의 사라졌다.", "An AI character rooted in Indonesian Ramadan culture was absorbed into the 'Italian brainrot' universe and became a worldwide schoolkid meme. Its original meaning, the drum that wakes people for sahur, mostly vanished outside Indonesia."),
    variants: [
      v("ID", "Tung Tung Tung Sahur", "2025-02-28", 100, T("라마단 새벽 식사(사후르)를 깨우는 북소리 '퉁퉁퉁'에서. 나무 북 모양 캐릭터가 세 번 불러도 안 일어나면 찾아온다는 설정.", "From the 'tung tung tung' drum that wakes people for sahur. The wooden-drum character comes for you if you ignore three calls."),
        [{ label: "sahur 깨우기 영상", note: T("실제 사후르 북 영상과 합친 패러디", "Parodies spliced with real sahur drumming") }], []),
      v("US", "Tung Tung Tung Sahur", "2025-04-10", 80, T("종교적 맥락은 사라지고 Tralalero Tralala·Bombardiro Crocodilo 와 함께 '이탈리안 브레인로트' 캐릭터 대전의 한 명이 됐다.", "Stripped of its religious context, it became one fighter in the 'Italian brainrot' roster alongside Tralalero Tralala and Bombardiro Crocodilo."),
        [{ label: "brainrot tier list", note: T("캐릭터 등급표 영상", "Character tier-list videos") }],
        [{ label: "Italian brainrot", note: T("AI 캐릭터 밈 세계관", "The AI-character meme universe") }]),
      v("BR", "Tung Tung Tung Sahur", "2025-05-05", 55, T("펑크 리믹스와 축구 세리머니 흉내로 퍼졌다.", "Spread through funk remixes and football-celebration imitations."), [{ label: "Tung Tung funk", note: T("펑크 리믹스", "Funk remix") }], []),
      v("VN", "Tung Tung Tung Sahur", "2025-05-20", 40, T("짤과 스티커로. 초등생 필통·문구 그림으로 번졌다.", "Stickers and image macros; drawn on kids' pencil cases and stationery."), [], []),
      v("KR", "퉁퉁퉁 사후르", "2025-06-01", 65, T("'퉁퉁퉁 사후르'로 표기. 초등생이 캐릭터 이름을 줄줄 외우는 것이 부모 세대에게 '이게 뭐냐'는 질문거리가 됐다.", "Written '퉁퉁퉁 사후르'. Kids reciting the character names became the thing parents asked about."), [{ label: "브레인로트 이름 외우기", note: T("캐릭터 이름 빨리 말하기 놀이", "Rapid-fire naming game") }], []),
      v("JP", "トゥントゥントゥンサフール", "2025-06-10", 45, T("가타카나 표기로 굿즈와 노래 커버까지 나왔다.", "Katakana spelling, with merchandise and song covers."), [], []),
    ],
  },
  {
    id: "t_dujjonku", category: "food", name: T("두쫀쿠", "Dubai chewy cookie"),
    summary: T("두바이 초콜릿 속을 넣은 한국의 쫀득 쿠키가, 미국에서는 '유행 먹거리 전부 넣은 이름' 풍자 밈의 한 조각이 됐다. 음식이 국경을 넘으면 이름이 붙는 방식이 바뀐다.", "A Korean chewy cookie with Dubai-chocolate filling became, in the US, one ingredient of a satirical 'every-food-trend-in-one-name' meme. When food crosses borders, the way it gets named changes."),
    variants: [
      v("KR", "두쫀쿠", "2025-10-15", 100, T("편의점·베이커리 오픈런. '두바이 쫀득 쿠키'의 줄임말 자체가 유행어가 됐다.", "Queues at bakeries and convenience stores; the abbreviation itself became slang."), [{ label: "두쫀쿠 오픈런", note: T("개점 전 줄 서기 영상", "Pre-opening queue videos") }], [{ label: "두바이 초콜릿", note: T("한 해 앞선 원조 유행", "The original craze a year earlier") }]),
      v("JP", "韓国もちクッキー", "2026-03-01", 30, T("'한국 모찌 쿠키'라는 설명형 이름으로 소개됐다 (가정).", "Introduced under the descriptive name 'Korean mochi cookie' (assumed)."), [], []),
      v("US", "Korean chewy cookie", "2026-06-16", 60, T("크리에이터 @moteaeats 의 'viral CRUMBL labubu Ube dot cake Dubai chocolate matcha Korean chewy cookie' — 유행 먹거리를 전부 한 이름에 넣은 풍자 시식 밈 속 재료가 됐다.", "Became an ingredient of @moteaeats' 'viral CRUMBL labubu Ube dot cake Dubai chocolate matcha Korean chewy cookie', a satirical taste-test cramming every trend into one name."),
        [{ label: "I ain't reading all that", note: T("긴 이름에 대한 반응 밈", "Reaction meme to the long name") }],
        [{ label: "viral Crumbl Labubu cookie", note: T("풍자 밈 원본", "The satire itself"), term_id: idOf("viral Crumbl Labubu cookie") }], "viral Crumbl Labubu cookie"),
    ],
  },
  {
    id: "t_labubu", category: "product", name: T("라부부", "Labubu"),
    summary: T("홍콩 출신 작가 카싱 룽의 캐릭터를 중국 팝마트가 키링 인형으로 내놨고, 블랙핑크 리사가 든 사진 한 장으로 태국에서 폭발한 뒤 세계 품절이 됐다. 나라마다 '왜 사는가'가 다르다.", "A character by Hong Kong-born artist Kasing Lung, sold by China's Pop Mart as a keychain doll; one photo of BLACKPINK's Lisa set Thailand alight and the world sold out. Why people buy it differs by country."),
    variants: [
      v("CN", "拉布布", "2024-06-01", 70, T("팝마트 블라인드 박스 문화의 대표 상품. 2025년 희귀판이 경매에서 수억 원에 팔렸다.", "Flagship of Pop Mart's blind-box culture; a rare edition sold for six figures at a 2025 auction."), [{ label: "盲盒 개봉", note: T("블라인드 박스 개봉 영상", "Blind-box unboxing videos") }], []),
      v("TH", "ลาบูบู้", "2024-04-15", 100, T("블랙핑크 리사가 가방에 단 사진으로 시작. 태국 관광청이 '관광 홍보대사'로 임명(2024-07)할 만큼 국가적 현상이 됐다.", "Started with a photo of BLACKPINK's Lisa wearing one on her bag; the Tourism Authority even named it an ambassador (Jul 2024)."), [{ label: "Lisa Labubu", note: T("리사 착용 사진 재현", "Recreating Lisa's photo") }], [{ label: "Lisa", note: T("태국 출신 블랙핑크 멤버", "Thai-born BLACKPINK member") }]),
      v("KR", "라부부", "2025-04-01", 65, T("팝마트 매장 오픈런과 품절, 가짜 상품을 부르는 '라푸푸'라는 말까지 생겼다.", "Queues and sellouts at Pop Mart stores, and a word for fakes: '라푸푸' (Lafufu)."), [{ label: "라푸푸", note: T("가짜 라부부를 부르는 말", "Nickname for fake Labubus") }], []),
      v("US", "Labubu", "2025-05-01", 80, T("리셀 가격과 '어른의 장난감' 논쟁. 셀럽이 명품 가방에 단 사진이 유행을 키웠다.", "Resale prices and the 'toys for adults' debate; celebrities clipping it to luxury bags fuelled it."), [{ label: "Labubu on a Birkin", note: T("명품 가방 키링 사진", "Luxury-bag keychain photos") }], []),
      v("JP", "ラブブ", "2025-06-01", 40, T("팝마트 일본 매장 추첨 판매. 애니 굿즈 문화와 만나 '痛バ'(굿즈 가방)에 다는 식으로.", "Lottery sales at Pop Mart Japan; met anime-goods culture as something you pin to an 'ita-bag'."), [], []),
    ],
  },
  {
    id: "t_dubaichoc", category: "food", name: T("두바이 초콜릿", "Dubai chocolate"),
    summary: T("두바이의 한 초콜릿 가게 제품이 틱톡 먹방으로 세계에 퍼졌고, 나라마다 '어떻게 구하나'가 화제였다. 한국은 편의점 제품과 두쫀쿠로, 독일은 린트 대란으로, 미국은 코스트코·크럼블 밈으로.", "A single Dubai chocolatier's bar went global via TikTok mukbang, and each country argued about how to get one: convenience-store versions and 두쫀쿠 in Korea, a Lindt frenzy in Germany, Costco and Crumbl memes in the US."),
    variants: [
      v("AE", "Dubai chocolate", "2023-12-01", 50, T("Fix Dessert Chocolatier 의 피스타치오·카다이프 바. 하루 두 번 한정 판매가 품절 신화를 만들었다.", "Fix Dessert Chocolatier's pistachio-kataifi bar; two limited drops a day created the sellout legend."), [{ label: "Can't Get Knafeh Of It", note: T("원조 제품 이름", "The original bar's name") }], []),
      v("KR", "두바이 초콜릿", "2024-07-01", 90, T("편의점 3사가 유사 제품을 내며 품절 대란. 이어 쫀득 쿠키 버전 '두쫀쿠'로 변형됐다.", "Convenience-store chains released look-alikes and sold out; then it mutated into the chewy-cookie version 두쫀쿠."), [{ label: "편의점 두바이 초콜릿", note: T("품절 매대 인증", "Empty-shelf photos") }], [{ label: "두쫀쿠", note: T("한국식 후속 유행", "The Korean follow-up craze"), term_id: idOf("두쫀쿠") }]),
      v("DE", "Dubai-Schokolade", "2024-11-01", 70, T("린트가 한정판을 내자 매장 앞에 줄이 섰고, 세관이 개인 수입을 단속하는 뉴스까지 나왔다.", "Lindt's limited edition drew queues, and customs cracking down on personal imports made the news."), [{ label: "Lindt Dubai Schokolade", note: T("린트 한정판 대란", "The Lindt limited-edition frenzy") }], []),
      v("US", "Dubai chocolate", "2024-12-01", 75, T("코스트코·트레이더조 입점 소식이 뉴스가 됐고, 크럼블 등 체인이 '두바이' 이름을 붙인 메뉴를 냈다.", "Costco and Trader Joe's stocking it made news, and chains like Crumbl put 'Dubai' on menu items."), [], [{ label: "viral Crumbl Labubu cookie", note: T("유행 이름 전부 넣은 풍자 밈", "The all-trends-in-one-name satire"), term_id: idOf("viral Crumbl Labubu cookie") }]),
      v("JP", "ドバイチョコ", "2025-02-01", 45, T("'ドバイチョコ' 줄임말로 편의점·백화점 한정 상품.", "Shortened to 'ドバイチョコ'; limited items at convenience stores and department stores."), [], []),
    ],
  },
  {
    id: "t_gutgenug", category: "song_challenge", name: T("Du Bist Gut Genug", "Du Bist Gut Genug"),
    summary: T("독일어 노래의 팔세토 한 구절이, 독일에서는 위로 문구로, 영어권에서는 잘못 들은 가사 놀이로, 한국에서는 편집물 소재로 각각 다르게 쓰였다.", "One falsetto line from a German song: a comforting phrase in Germany, a misheard-lyrics game in the English-speaking world, edit fodder in Korea."),
    variants: [
      v("DE", "Du Bist Gut Genug", "2026-05-22", 100, T("블루멘가르텐·키치크리크·시린 다비드의 'Gut Genug'. 뜻은 '너는 충분히 괜찷아'라 위로 문구로도, 놀림으로도 쓰인다. '올해의 청소년 단어' 후보 거론.", "'Gut Genug' by Blumengarten, Kitschkrieg and Shirin David. Meaning 'you are good enough', it works as comfort and as teasing; floated as youth word of the year."), [{ label: "Blumengarten Only", note: T("시린 다비드 파트를 뺀 편집", "Edits cutting Shirin David's part") }], []),
      v("US", "Doobie Scoot Canoe", "2026-06-07", 70, T("독일어를 모르는 이용자들이 'Doobie Scoot Canoe'로 듣고 놀았다. 클리블랜드 주니어 편집물이 폭발의 계기.", "Non-German speakers heard it as 'Doobie Scoot Canoe'; Cleveland Jr. edits set it off."), [{ label: "Cleveland Jr. edit", note: T("더 클리블랜드 쇼 장면 편집", "Edits of The Cleveland Show") }], []),
      v("KR", "두 비스트 굿 게눅", "2026-07-01", 35, T("영어권 편집물을 통해 들어와 '뜻 모르고 따라 부르는 노래'로 소비됐다.", "Arrived via English-language edits as a song you sing along to without knowing the words."), [], []),
    ],
  },
  {
    id: "t_aura", category: "slang_meme", name: T("aura farming", "aura farming"),
    summary: T("인도네시아 전통 보트 경주의 뱃머리 소년 영상 하나가 '멋 부리기'를 뜻하는 영어 표현을 세계에 퍼뜨렸다.", "One clip of a boy dancing on the bow of a traditional Indonesian racing boat carried the English phrase for 'posing for cool points' around the world."),
    variants: [
      v("ID", "aura farming", "2025-07-01", 100, T("리아우주 파쿠 잘루르 경주에서 11살 소년 라이얀 디카가 뱃머리에서 무표정으로 춤춘 영상. 소년은 관광 홍보대사가 됐다.", "Eleven-year-old Rayyan Dikha dancing deadpan on the bow at the Pacu Jalur races in Riau; he was made a tourism ambassador."), [{ label: "Pacu Jalur boat kid", note: T("원본 영상", "The original clip") }], []),
      v("US", "aura farming", "2025-07-10", 85, T("운동선수와 스트리머들이 세리머니로 따라 했다. 원래 게임·애니 커뮤니티 말이던 'aura'가 대중어가 됐다.", "Athletes and streamers copied it as a celebration; 'aura', once gaming and anime slang, went mainstream."), [{ label: "boat kid celebration", note: T("골 세리머니 버전", "Goal-celebration versions") }], []),
      v("KR", "아우라 파밍", "2025-08-01", 45, T("'아우라 파밍'으로 표기. 게임 용어 '파밍'이 익숙해 뜻이 바로 통했다.", "Written '아우라 파밍'; the gaming word '파밍' (farming) made the meaning click instantly."), [], []),
    ],
  },
  {
    id: "t_ronaldo", category: "slang_meme", name: T("Ronaldo Pasta", "Ronaldo Pasta"),
    summary: T("MrBeast 영상 속 파스타 한 접시가 2년 뒤 브레인로트 편집물로 되살아났다. 축구 팬 문화가 있는 나라에서 더 크게 돌았다.", "A plate of pasta from a MrBeast video came back two years later as brainrot edits, travelling furthest where football fandom runs deep."),
    variants: [
      v("US", "Ronaldo Pasta", "2026-07-09", 100, T("카이 세넛이 아이쇼스피드에게 '호날두 파스타'를 내놓고 5점을 받은 장면(2024-07 MrBeast 영상)이 2026년 7월 틱톡 편집물로 재발굴됐다.", "Kai Cenat serving IShowSpeed 'Ronaldo Pasta' for a 5/10 (a July 2024 MrBeast video) was rediscovered as TikTok edits in July 2026."), [{ label: "Who is the best soccer player of all time?", note: T("장면의 대사", "The line from the scene") }], [{ label: "MrBeast", note: T("원본 영상 채널", "The source channel") }]),
      v("GB", "Ronaldo Pasta", "2026-07-20", 60, T("축구 팬 계정들이 호날두·메시 논쟁에 얹어 편집물을 만들었다.", "Football-fan accounts folded it into the Ronaldo-versus-Messi debate."), [], []),
      v("KR", "호날두 파스타", "2026-08-05", 30, T("'호날두 파스타'로 표기. 축구 커뮤니티에서 짤로.", "Written '호날두 파스타'; image macros in football communities."), [], []),
    ],
  },
];

export const SAMPLE_BOARD: TrendBoard = { generated_at: "2026-09-14T12:00:00Z", items: ITEMS, topics: TOPICS, why: [] };
