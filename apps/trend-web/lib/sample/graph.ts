/* 예시 '콘텐츠 → 나라마다 파생된 밈'. 조사 에이전트(pipeline/content_agent.py)가 오징어 게임으로 찾은 결과를
   GET /graph/content/{key} 모양 그대로 옮긴 것(2026-10-01). */
import type { GraphContent, GraphContentSummary } from "../types";

export const SAMPLE_GRAPH_CONTENTS: GraphContentSummary[] = [{"key": "squid-game", "name": "Squid Game", "labels": {"en": "Squid Game", "zh": "魷魚遊戲", "ko": "오징어 게임", "vi": "Trò chơi con mực", "ja": "イカゲーム", "th": "สควิดเกม เล่นลุ้นตาย", "id": "Squid Game"}, "memes": 48, "regions": ["KR", "ID", "VN", "GLOBAL"], "updated_at": "2026-10-01T01:31:17.939311+00:00"}];

export const SAMPLE_GRAPH: Record<string, GraphContent> = {
 "squid-game": {
  "content": {
   "key": "squid-game",
   "name": "Squid Game",
   "labels": {
    "en": "Squid Game",
    "zh": "魷魚遊戲",
    "ko": "오징어 게임",
    "vi": "Trò chơi con mực",
    "ja": "イカゲーム",
    "th": "สควิดเกม เล่นลุ้นตาย",
    "id": "Squid Game"
   }
  },
  "regions": [
   "KR",
   "ID",
   "VN",
   "GLOBAL"
  ],
  "memes": [
   {
    "variants": [
     {
      "name": "나는 이 게임을 해 봤어요!",
      "region": "KR",
      "description": "온라인 게임의 고인물 유저 상황이나 N수생의 상황에 비유하여 사용됨.",
      "quote": "나는 이 게임을 해 봤어요!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "본편 3화에서 성기훈이 \"나는 이 게임을 해 봤어요!\"라고 외치나 곧이어 100번 참가자 에게 \"그런 놈이 여기를 왜 다시 기어들어 와?\"라고 반박당하는 장면(약 1분 4초 경)이 마치 밸런스나 운영이 개판인 온라인 게임 을 욕하면서도 접지 못하고 다시 돌아오게 되는 고인물 유저들의 상황과 절묘하게 맞아 떨어져 밈이 되었다.",
      "term_id": null
     },
     {
      "name": "I've Played These Games Before!",
      "region": "GLOBAL",
      "description": "무궁화 꽃이 피었습니다 모드에서 성기훈을 따라 하며 외치는 말",
      "quote": "I've played these games before",
      "evidence_url": "https://knowyourmeme.com/memes/ive-played-these-games-before",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": "성기훈의 대사를 활용하여 고인물이나 N수생 상황을 비유하는 밈임."
   },
   {
    "variants": [
     {
      "name": "얼음!",
      "region": "KR",
      "description": "성기훈의 대사를 활용한 밈이 국내외 여러 곳에서 사용됨.",
      "quote": "얼음!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "성기훈의 \"얼음!\"을 이용한 밈이 국내외 가릴 것 없이 여러 곳에서 쓰이고 있다.",
      "term_id": null
     },
     {
      "name": "Freeze!",
      "region": "GLOBAL",
      "description": "무궁화 꽃이 피었습니다 모드에서 성기훈을 따라 하며 외치는 말",
      "quote": "Freeze!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "또한 무궁화 꽃이 피었습니다 모드에서는 성기훈을 따라 하면서 \"Freeze!\", \"I've played these games before\"를 외치는 장면들도 많이 나온다.",
      "term_id": null
     }
    ],
    "same_scene": "무궁화 꽃이 피었습니다 게임에서 성기훈의 대사를 활용한 밈임."
   },
   {
    "variants": [
     {
      "name": "깐부",
      "region": "KR",
      "description": "작중 일남이 사용한 단어로 해외 밈이나 패러디에서도 자주 등장함.",
      "quote": "깐부",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "해외의 오징어 게임 밈이나 패러디 등에도 깐부(gganbu)라는 용어가 매우 자주 등장한다.",
      "term_id": "t_2cac635e40"
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "달고나 패러디",
      "region": "KR",
      "description": "배우 류승룡이 달고나 패러디를 하는 짤방이 화제가 됨.",
      "quote": "",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "배우 류승룡 이 달고나 패러디를 하는 짤방도 화제가 되었다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "덕수 씨, 이제 왔어?",
      "region": "KR",
      "description": "미녀가 한 대사로 많이 쓰임.",
      "quote": "덕수 씨, 이제 왔어?",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "덕수 의 \"그 동안 즐거웠다, 개새끼야!\", 미녀 의 \"덕수 씨, 이제 왔어?\", \"개새끼야!\" 등도 많이 쓰였다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "도시락",
      "region": "KR",
      "description": "시즌 3에서 가장 큰 반응을 얻으며 커뮤니티와 유튜브 등에서 언급됨.",
      "quote": "도시락",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "국내에서는 '도시락' 대사가 시즌 3에서 가장 큰 반응을 얻어 커뮤니티, 유튜브 등에서 많은 언급을 받고 있다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "딱지치기",
      "region": "KR",
      "description": "외국의 길거리에서 정장 차림의 남자가 행인들과 딱지치기를 하는 영상이 다수 업로드됨.",
      "quote": "",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "외국의 길거리에서 딱지치기를 패러디하여 정장 차림의 남자의 코스튬을 한 후 행인들과 딱지치기를 하는 영상이 다수 업로드되고 있다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "무궁화 꽃이 피었습니다",
      "region": "KR",
      "description": "TFN이 발매한 오징어 게임 모티브의 디지털 싱글",
      "quote": "무궁화 꽃이 피었습니다",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "아이돌 그룹 TFN 이 무궁화 꽃이 피었습니다 게임에서 모티브를 얻은 디지털 싱글 앨범 ' '무궁화 꽃이 피었습니다 '를 발매했다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "미쳤어? 개소리하지 마~",
      "region": "KR",
      "description": "알리가 한 대사로 유튜브 밈으로 사용됨.",
      "quote": "미쳤어? 개소리하지 마~",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "성기훈의 \"이러면 안 되는 거잖아!\", 일남의 \"제발 그만해... 나 무서워... 이러다가는 다 죽어!\", 알리 의 \"미쳤어? 개소리하지 마~\", 상우 의 \" 하... 씨발, 기훈이 형! \"이 밈으로 쓰였다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "얼음 리믹스",
      "region": "KR",
      "description": "성기훈의 명대사인 \"얼음~\"을 이용해 패러디한 중독성 있는 리믹스 곡",
      "quote": "얼음~",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "유튜버 제프프 는 성기훈의 명대사인 \"얼음~\"을 이용해 패러디한 얼음 리믹스 를 만들며 큰 인기를 끌고 있다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "영희 로봇",
      "region": "KR",
      "description": "진이 콘서트에서 수행한 오징어 게임 캐릭터 패러디",
      "quote": "영희 로봇",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "진은 영희 로봇, 뷔는 진행 요원(관리자).",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "영희 로봇 패러디",
      "region": "KR",
      "description": "미야자키 미호가 축제에서 선보인 오징어 게임 캐릭터 패러디",
      "quote": "영희 로봇",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "AKB48 의 멤버 미야자키 미호 가 호리NS 축제에서 오징어 게임의 영희 로봇 패러디를 했다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "이러다간 다 죽어...!",
      "region": "KR",
      "description": "원신의 페이몬이 오징어 게임 대사를 치는 아카콘에 포함된 대사.",
      "quote": "이러다간 다 죽어...!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "\"이러다간 다 죽어...!\" 등 실제로 쓰기 쉬운 일남의 대사가 많이 쓰이며, 실제로 오징어 게임을 캡처한 아카콘도 많이 쓴다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "이러면 안 되는 거잖아!",
      "region": "KR",
      "description": "성기훈이 한 대사로 유튜브 밈으로 사용됨.",
      "quote": "이러면 안 되는 거잖아!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "성기훈의 \"이러면 안 되는 거잖아!\", 일남의 \"제발 그만해... 나 무서워... 이러다가는 다 죽어!\", 알리 의 \"미쳤어? 개소리하지 마~\", 상우 의 \" 하... 씨발, 기훈이 형! \"이 밈으로 쓰였다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "제발 그만해... 나 무서워... 이러다가는 다 죽어!",
      "region": "KR",
      "description": "일남이 한 대사로 유튜브 밈으로 사용됨.",
      "quote": "제발 그만해... 나 무서워... 이러다가는 다 죽어!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "성기훈의 \"이러면 안 되는 거잖아!\", 일남의 \"제발 그만해... 나 무서워... 이러다가는 다 죽어!\", 알리 의 \"미쳤어? 개소리하지 마~\", 상우 의 \" 하... 씨발, 기훈이 형! \"이 밈으로 쓰였다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "참가자 1905번 탈락!",
      "region": "KR",
      "description": "페네르바흐체 팬들이 갈라타사라이의 창단 연도를 활용해 도발하는 슬로건",
      "quote": "참가자 1905번 탈락!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "페네르바흐체가 승리한 뒤 갈라타사라이에게 역으로 창단 년도 번호를 부르면서 \"참가자 1905번 탈락!\" 으로 슬로건을 달아 역관광으로 도발하는 장면도 정말 압권이었다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "참가자 1907번 탈락!",
      "region": "KR",
      "description": "갈라타사라이 팬들이 페네르바흐체의 창단 연도를 활용해 도발하는 슬로건",
      "quote": "참가자 1907번 탈락!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "갈라타사라이의 팬들이 오징어 게임을 패러디하는 슬로건으로 페네르바흐체의 창단 년도를 번호로 부르면서 \"참가자 1907번 탈락!\" 이라고 도발하는 화려한 카드섹션을 보여서 화제가 되었다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "타노스의 대사",
      "region": "KR",
      "description": "타노스의 여러 대사와 랩을 활용한 밈 및 노래 제작.",
      "quote": "빨주노초 I'm a legend 타노스, 경수, You Out!, 우리 경수 얻다 두고 왔어?, 너한테 벌이 앉았어, 놉, 약 하면 저러지 않아, 땡~~, 레츠 기릿!!",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "타노스 의 \"빨주노초 I'm a legend 타노스\", \"경수, You Out!\", \"우리 경수 얻다 두고 왔어?\", \"너한테 벌이 앉았어\", \"놉, 약 하면 저러지 않아\", \"땡~~, 레츠 기릿!!\"이랑 타노스의 랩 그리고 ○노스 등이 명대사로 많이 쓰고 있고 작년 유행했던 창팝 처럼 이 타노스의 대사를 이용해 노래를 만드는 영상들이 생겨나고 있다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Lampu merah, Lampu Hijau",
      "region": "ID",
      "description": "소셜 미디어 사용자들이 '무궁화 꽃이 피었습니다' 게임을 인터넷 챌린지로 채택함.",
      "quote": "Lampu merah, Lampu Hijau",
      "evidence_url": "https://id.wikipedia.org/wiki/Squid_Game",
      "sentence": "pengguna media sosial mengadaptasi beberapa game yang ditampilkan dalam Squid Game sebagai tantangan Internet, termasuk game \"Lampu merah, Lampu Hijau\" pertama dan game kue sarang lebah kedua.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "game kue sarang lebah",
      "region": "ID",
      "description": "소셜 미디어 사용자들이 '달고나' 게임을 인터넷 챌린지로 채택함.",
      "quote": "game kue sarang lebah",
      "evidence_url": "https://id.wikipedia.org/wiki/Squid_Game",
      "sentence": "pengguna media sosial mengadaptasi beberapa game yang ditampilkan dalam Squid Game sebagai tantangan Internet, termasuk game \"Lampu merah, Lampu Hijau\" pertama dan game kue sarang lebah kedua.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Đèn xanh, đèn đỏ",
      "region": "VN",
      "description": "서구권에서 한국 드라마가 주목받게 된 계기가 된 '무궁화 꽃이 피었습니다' 게임의 번역명.",
      "quote": "Đèn xanh, đèn đỏ",
      "evidence_url": "https://vi.wikipedia.org/wiki/Trò_chơi_con_mực",
      "sentence": "Các bộ phim truyền hình Hàn Quốc (K-drama) chính thức được \"bật đèn xanh\" tại phương Tây sau trò Đèn xanh, đèn đỏ trong Squid Game \".",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "\"Unnie\" / Kim Young-mi Behind the Door",
      "region": "GLOBAL",
      "description": "문 사이로 서로를 바라보며 대화하다 비극적으로 죽게 되는 두 인물의 감동적인 장면을 뜻합니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/unnie-kim-young-mi-behind-the-door",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Dalgona Candy Challenge",
      "region": "GLOBAL",
      "description": "달고나에서 모양을 뽑아내는 장면을 따라 하는 틱톡 챌린지입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/dalgona-candy-challenge",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Gi-hun Bunny",
      "region": "GLOBAL",
      "description": "성기훈 역의 배우 이정재가 토끼 옷을 입은 사진이 2025년 틱톡에서 '브레인롯' 스타일의 편집과 결합되어 유행함.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/gi-hun-bunny",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Hoyeon Jung, Squid Game Star, Reveals In a Recent Interview to Vogue Korea",
      "region": "GLOBAL",
      "description": "정호연 배우의 인터뷰를 빌려 자신이 최근 푹 빠져 있는 것을 과장해서 표현하는 문구입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/hoyeon-jung-squid-game-star-reveals-in-a-recent-interview-to-vogue-korea",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "I'm a Legend, Thanos",
      "region": "GLOBAL",
      "description": "캐릭터 '타노스'가 여성에게 플러팅하며 랩을 하는 장면에서 나온 대사가 댓글 스팸으로 유행한 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/im-a-legend-thanos",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Little Squid Game Guard Dancing",
      "region": "GLOBAL",
      "description": "분홍색 가드가 특정 음악에 맞춰 춤추는 애니메이션이 틱톡 등에서 유행한 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/little-squid-game-guard-dancing",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Mingle Game (Squid Game)",
      "region": "GLOBAL",
      "description": "시즌 2에서 회전하는 회전목마를 배경으로 생존을 위해 팀을 나누는 긴박한 게임 장면을 말합니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/mingle-game-squid-game",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Oh-Il Nam Standing and Sitting",
      "region": "GLOBAL",
      "description": "오일남의 기쁨과 우울한 감정 변화를 대비시켜 상황의 변화를 표현할 때 쓰입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/oh-il-nam-standing-and-sitting",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "One More Game",
      "region": "GLOBAL",
      "description": "100번 참가자가 시즌 2, 3의 지속을 촉구하며 '한 게임 더'를 외치는 장면이 틱톡 등에서 밈으로 활용됨.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/one-more-game",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Papa Squid Game",
      "region": "GLOBAL",
      "description": "프런트맨의 얼굴을 합성한 캐릭터가 아기 성기훈을 안고 'papa'라고 말하는 소리와 결합된 밈.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/papa-squid-game",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Red Light, Green Light / Squid Game Doll",
      "region": "GLOBAL",
      "description": "무궁화 꽃이 피었습니다 게임의 긴장감이나 움직이면 안 되는 상황을 묘사할 때 쓰입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/red-light-green-light-squid-game-doll",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "SQUID GAMES❗❗",
      "region": "GLOBAL",
      "description": "어떤 캐릭터가 패배하거나 쓰러지는 장면에 'SQUID GAMES❗❗' 문구를 붙여 작품의 인기를 풍자하는 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/squid-games❗❗",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Seong Gi-hun Staring At Dae-ho (Squid Game)",
      "region": "GLOBAL",
      "description": "시즌 3에서 성기훈이 겁을 먹고 보급품을 전달하지 못한 강대호를 분노 섞인 시선으로 노려보는 장면.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/seong-gi-hun-staring-at-dae-ho-squid-game",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Seong Gi-hun's ID Photo",
      "region": "GLOBAL",
      "description": "성기훈의 무표정하거나 웃는 사진을 활용해 특정 상황에 대한 반응을 표현합니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/seong-gi-huns-id-photo",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Smiling and Unsmiling Seong Gi-hun",
      "region": "GLOBAL",
      "description": "",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/smiling-and-unsmiling-seong-gi-hun",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Squid Game Celebration",
      "region": "GLOBAL",
      "description": "시즌 2에서 성기훈이 다른 참가자들과 함께 환호하며 기뻐하는 장면이 이미지 매크로로 활용됨.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/squid-game-celebration",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Squid Game Edit Reaction Images",
      "region": "GLOBAL",
      "description": "틱톡 등에서 편집된 오징어 게임 장면에 특정 대사나 문구를 자막으로 입힌 반응 이미지들.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/squid-game-edit-reaction-images",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Squid Game Loading Screen Edits",
      "region": "GLOBAL",
      "description": "시즌 3에서 성기훈이 카메라를 응시하는 특정 장면이 게임 로딩 화면과 유사하다는 점에서 유머 소재로 쓰임.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/squid-game-loading-screen-edits",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Squid Game Mods / Real-Life Games",
      "region": "GLOBAL",
      "description": "로블록스나 GTA 등 다른 게임이나 현실에서 오징어 게임의 규칙을 재현하는 활동을 뜻합니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/squid-game-mods-real-life-games",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "The Recruiter Smiling",
      "region": "GLOBAL",
      "description": "고용 담당자가 웃는 표정을 활용해 겉으로는 웃고 있지만 속으로는 고통을 참는 상황을 풍자하는 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/the-recruiter-smiling",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "We Are Not Horses. We Are Humans and Humans Are...",
      "region": "GLOBAL",
      "description": "시즌 3 마지막에 성기훈이 죽기 전 프런트맨의 대사를 인용하며 남긴 비장한 유언 대사.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/we-are-not-horses-we-are-humans-and-humans-are",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Why Are You Here? I Thought You Were Financially Stable",
      "region": "GLOBAL",
      "description": "무언가 비싼 물건이나 수집품을 자랑할 때 사용하는 반어법적인 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/why-are-you-here-i-thought-you-were-financially-stable",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "Your Next Task Is...",
      "region": "GLOBAL",
      "description": "어려운 과제가 발표되는 순간의 긴장감을 담은 369번 참가자의 정지 화면을 활용한 밈입니다.",
      "quote": "",
      "evidence_url": "https://knowyourmeme.com/memes/your-next-task-is",
      "sentence": "Part of a series on Squid Game",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "player 456, passed",
      "region": "GLOBAL",
      "description": "라라 나키 구트만의 쇼트 프로그램 곡 중 클라이막스 이후 나오는 대사",
      "quote": "player 456, passed",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "'무궁화 꽃이 피었습니다'라는 한국어로 시작해 클라이막스에서 무궁화 대사가 반복되며 휘몰아치다 'player 456, passed'로 끝나는 편곡 또한 호평받았다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   },
   {
    "variants": [
     {
      "name": "unnie",
      "region": "GLOBAL",
      "description": "현주와 영미의 장면을 패러디하거나 따라하며 채팅으로 치는 말",
      "quote": "unnie",
      "evidence_url": "https://namu.wiki/w/오징어 게임/흥행 및 파급력",
      "sentence": "해당 방에 들어가지 못한 플레이어는 \"unnie\"라는 채팅을 치며 현주와 영미의 장면을 패러디하거나 따라하는 장면 들이 SNS나 유튜브를 통해 자주 보인다.",
      "term_id": null
     }
    ],
    "same_scene": ""
   }
  ],
  "updated_at": "2026-10-01T01:31:17.939311+00:00"
 }
};
