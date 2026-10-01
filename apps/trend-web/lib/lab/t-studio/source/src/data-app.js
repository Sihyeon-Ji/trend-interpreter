// ===== web app content (adds to v2 data + screen content) =====
var DETAIL_YAR = {
  id: 'yar', aliases: ['꺄르', '할렐야루', '야르~'], plain: '앗싸',
  definition: "'앗싸', '오예' 같은 신남의 감탄사. 좋은 일이 생겼을 때 짧게 외쳐요.",
  origin: "예전부터 쓰이던 감탄사가 2026년 숏폼과 인스타 댓글에서 다시 유행했어요. '꺄르'(꺅+야르), '할렐야루'(할렐루야+야르) 같은 상위 버전이 붙었어요.",
  nuance: '가볍고 귀여운 톤. 뜻은 없고 기분만 전해요.',
  usage: [ { age: '10대', share: 70 }, { age: '20대', share: 30 } ],
  goodFor: ['음식·음료의 한 입, 한 모금 순간', '할인·당첨·오픈 소식 발표', '언박싱 리액션'],
  avoidFor: ['사과문·공지처럼 진지한 글', '30대 이상이 주 타깃인 광고 본문'],
  goodEx: { text: '흑당 라떼 한 모금이면 야르~', why: '좋은 순간에 짧게 외치는 감탄사 그대로예요' },
  badEx: { text: '야르한 가격, 지금 구매하세요', why: '감탄사를 꾸밈말로 쓰면 뜻이 어긋나 억지 밈으로 읽혀요' },
  sources: [
    { kind: '뉴스', domain: 'thetrippick.com', title: '밤티·야르·아자스가 뭐야? 인스타에서 유행하는 2026 밈 뜻', date: '2026-07-15' },
    { kind: '뉴스', domain: 'news.nate.com', title: "[카드뉴스] 2026 상반기 신조어 총정리…'신조어 활용 가이드'", date: '2026-07-24' },
    { kind: '쇼츠', domain: 'youtube.com', title: '할렐야루 모음', date: '2026-08-09' }
  ],
  angles: [
    { title: '한 모금 반전', t: '지친 순간 → 제품 → "야르~!" 한 번으로 기분 반전' },
    { title: '당첨 발표', t: '이벤트 당첨자 발표 자막을 "야르~"로 열기' },
    { title: '언박싱 리액션', t: '상자를 여는 순간의 감탄사로 한 번만 크게' }
  ]
};

// 표제어 말고 실제 글에 나오는 형태 (저장소 예시 사전의 aliases)
var ALIASES = {
  youngkk: ['영ㅋㅋ', '영크크다'], oldkk: ['늙ㅋㅋ', '올크크', '늙크크다'], bamti: ['밤티나다', '밤티난다', '밤티력'],
  jungti: ['중티나다', '중티난다'], yar: ['꺄르', '할렐야루'], shagal: ['아 샤갈', '샤갈이네'],
  nanri: ['슬프자베스', '행복자베스', '자베스'], temu: ['테무 인간'], gemmini: ['젬민', '젬민이형'],
  teto: ['테토녀', '에겐남', '에겐녀', '에겐'], yoonjung: ['윤정아 윤정아', '왜요 쌤'], namu: ['나무챌린지'],
  dujjonku: ['두바이 쫀득 쿠키', '두바이 쫀득쿠키'], chugumi: ['내 추구미'], neujo: ['느낌 좋다'], jeommechu: ['점메추좀'],
  luckyvicky: ['완전 럭키비키잖아', '럭키비키잖아'], wonyoung: ['원영적사고'], osalhim: ['오늘을 살아갈 힘', '오살힘 충전'],
  pierrot: ['선배삐', '개대박삐', '대박삐', '삐바삐', '정통삐', '삐출'], typo: ['모르는 개 산책', '노력이 숲으로 돌아갔다', '눈 가리고 야옹'],
  chaek: ['책임 없는 쾌락'], wegovy: ['천연위고비'], yarsong: ['야르 송']
};
// 쉬운 말 (저장소 예시 사전의 plain)
var PLAIN = {
  youngkk: '요즘 감각', oldkk: '옛날 감성', bamti: '촌스러운', jungti: '과하게 화려한', yar: '앗싸', nanri: '난리 났다',
  temu: '겉만 번지르르한 사람', gemmini: 'AI에 다 물어보는 사람', teto: '활동적인 스타일', dujjonku: '두바이 쫀득 쿠키',
  chugumi: '지향하는 스타일', neujo: '느낌 좋다', jeommechu: '점심 메뉴 추천', luckyvicky: '오히려 좋아',
  wonyoung: '긍정적으로 생각하기', osalhim: '오늘 버틸 힘', chaek: '책임 없는 즐거움', shagal: '(욕설 순화 감탄사)'
};

// 브랜드마다 스튜디오가 만드는 기획 방향 틀 ({p} = 알릴 상품)
var CONCEPT_LIB = {
  yar:       { title: '"{p} 한 번이면 야르~!"', format: '15초 반전형 쇼츠', hook: '지친 순간을 보여 주는 첫 자막', effort: '쉬움', effortNote: '출연 1명 · 촬영 1곳', idea: '지친 순간 → {p} → "야르~!" 한 번으로 기분이 반전돼요. 감탄사 하나라 설명이 필요 없어요.' },
  typo:      { title: '속담 한 글자로 {p} 소개', format: '자막 말놀이 쇼츠', hook: '"티끌 모아 태산" 같은 익숙한 속담', effort: '쉬움', effortNote: '자막 편집만 · 반나절', idea: '익숙한 속담을 한 글자 바꿔 {p}의 장점으로 뒤집어요. 댓글에 "나도 하나" 참여가 붙기 좋아요.' },
  youngkk:   { title: '영크크 vs 늙크크, {p} 편', format: '비교형 쇼츠', hook: '"영크크는 이렇게 한다"', effort: '보통', effortNote: '같은 장면 두 번 촬영', idea: '같은 상황을 영크크·늙크크 두 버전으로 보여 주고 {p}로 영크크 쪽에 서요.' },
  oldkk:     { title: '늙크크 탈출기', format: '공감형 쇼츠', hook: '"나 혹시 늙크크?"', effort: '쉬움', effortNote: '출연 1명 · 셀프 촬영', idea: '스스로 늙크크라고 놀리는 상황을 {p}로 가볍게 해결하는 공감형 구성이에요.' },
  neujo:     { title: '말 없는 "느좋" 무드', format: '감성 무드 릴스', hook: '자막 한 줄 "느좋"', effort: '보통', effortNote: '조명·공간 연출', idea: '{p}를 쓰는 기분 좋은 순간을 설명 없이 무드로만 보여 줘요.' },
  osalhim:   { title: '나의 "오살힘" 시리즈', format: '15초 시리즈 + 참여 해시태그', hook: '"오늘을 살아갈 힘이 필요할 때"', effort: '보통', effortNote: '컷 3곳 · 시리즈 확장', idea: '하루를 버티게 하는 작은 것 = {p}. #나의오살힘 으로 이용자 참여를 이어 가요.' },
  wonyoung:  { title: '"{p}적 사고"', format: '상황극 쇼츠', hook: '안 좋은 일 → "오히려 좋아"', effort: '쉬움', effortNote: '출연 1명 · 상황 2컷', idea: '"원영적 사고"를 "{p}적 사고"로 바꿔 불편한 상황을 긍정으로 뒤집어요.' },
  ttogago:   { title: '"…지만 또 찾게 되는 {p}입니다"', format: '후기형 쇼츠 · 카피', hook: '"…하지만" 반전 자막', effort: '쉬움', effortNote: '기존 영상 재편집 가능', idea: '단점 같은 장점을 먼저 말하고 "또 찾게 되는"으로 뒤집는 말투 밈이에요. 20·30대에게 익숙해요.' },
  jeommechu: { title: '점메추 대신 {p}', format: '댓글 참여 포스트', hook: '"점메추 좀"', effort: '쉬움', effortNote: '이미지 1장 · 1시간', idea: '점심 메뉴를 고민하는 매일의 상황에 {p}를 답으로 끼워 넣어요.' },
  gemmini:   { title: '"젬민이도 이건 직접 한다"', format: '상황극 쇼츠', hook: '"AI한테 다 물어보는 친구"', effort: '보통', effortNote: '출연 2명 · 상황극', idea: 'AI에 다 물어보는 젬민이 친구도 {p}만은 직접 챙긴다는 반전이에요.' },
  chugumi:   { title: '내 추구미 = {p}', format: '비포·애프터 릴스', hook: '"내 추구미는…"', effort: '보통', effortNote: '비포·애프터 2컷', idea: '되고 싶은 모습(추구미)과 {p}를 연결하는 무드 영상이에요.' },
  chaek:     { title: '책없쾌 타임', format: '짧은 공감 쇼츠', hook: '"책임은 없고 재미만"', effort: '쉬움', effortNote: '셀프 촬영', idea: '부담 없이 즐기는 순간에 {p}를 곁들여요.' },
  pierrot:   { title: 'OO삐 릴레이', format: '15초 컷 전환', hook: '"출근삐, 야근삐…"', effort: '쉬움', effortNote: '컷 4개 · 자막 중심', idea: '상황마다 "삐"를 붙이다가 {p}에서 "개대박삐"로 반전해요.' }
};

var CAT_OPTIONS = [ { id: 'food', label: '음식·음료' }, { id: 'beauty', label: '뷰티' }, { id: 'fashion', label: '패션' }, { id: 'app', label: '앱·서비스' }, { id: 'place', label: '공간·여행' }, { id: 'ent', label: '여가·엔터' } ];
var TONE_VOICES = { '친근하게': ['wholesome', 'playful'], '위트 있게': ['wholesome', 'playful', 'edgy'], '산뜻하게': ['wholesome'], '고급스럽게': ['wholesome'] };
var AGE_OPTIONS = ['10대', '20대', '30대', '40대'];

// 나라를 건너는 밈 (저장소 예시 트렌드 보드의 같은 주제)
var CROSS = [
  { from: { id: 'dujjonku', region: 'KR' }, to: { id: 'mochicookie', region: 'JP' }, note: '한국에선 식었지만 일본에선 "韓国もちクッキー"로 오르는 중이에요.' },
  { from: { id: 'sixseven', region: 'GLOBAL' }, to: { id: 'sixsevenjp', region: 'JP' }, note: '미국의 "6-7"이 일본에서 가타카나 표기로 오르는 중이에요.' },
  { from: { id: 'dubaichoco', region: 'JP' }, to: { id: 'crumbl', region: 'GLOBAL' }, note: '두바이 초콜릿은 여러 나라에서 함께 식는 중이에요. 영어권에선 풍자 밈의 재료가 됐어요.' }
];

var PLAN_SEED = [
  { id: 'p1', title: 'A안 · 오후 3시 당 충전 → "야르~!"', memeId: 'yar', brandId: 'latte', status: '승인 대기', due: '9/28', sample: true },
  { id: 'p2', title: '나의 "오살힘" 시리즈', memeId: 'osalhim', brandId: 'latte', status: '초안', due: '10월 첫 주', sample: true }
];
var PLAN_STATUS = ['초안', '승인 대기', '승인', '게시 완료'];
var DECODER_SAMPLE = '오늘 출근삐 인정… 근데 흑당 라떼 한 모금 마시니까 야르~ 이게 바로 오살힘. 완전 럭키비키잖아';
// ===== end web app content =====
