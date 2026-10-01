// ===================== v2 screen content (Studio · Meme brief · Report) =====================
// Example outputs as the pipeline would produce them (Gemini product read, concept draft, rule checks).
var MODES = [ { id: 'product', label: '상품' }, { id: 'shorts', label: '쇼츠 링크' }, { id: 'image', label: '사진' } ];
var SHORTS = {
  url: 'youtube.com/shorts/[영상 ID]', length: '0:18', scenes: 4, captions: '자막 없음', audio: '원본 소리',
  timeline: [
    { from: '0:00', to: '0:04', what: '매장 외관', kind: 'issue',  tip: '첫 2초에 훅이 없어요 — "오후 3시, 배터리 3%" 자막으로 시작하기' },
    { from: '0:04', to: '0:09', what: '음료 만드는 손', kind: 'keep',  tip: '얼음 소리를 키우면 시원함이 살아나요' },
    { from: '0:09', to: '0:14', what: '한 모금 마시는 장면', kind: 'meme', tip: '밈 포인트 — 여기서 "야르~!" 자막을 화면 가득 + 줌인' },
    { from: '0:14', to: '0:18', what: '로고', kind: 'issue', tip: '끝 컷이 밋밋해요 — "당 충전 완료" 한 줄로 마무리' }
  ]
};


var STUDIO = {
  goals: ['인지도', '참여 (댓글·공유)', '구매 전환'],
  goal: '참여 (댓글·공유)',
  postDate: '9월 28일 (월)',     // 게시 예정일 = 오늘(9/14) + 제작 기간 2주
  channels: ['릴스·쇼츠·틱톡', '인스타 피드', 'X'],
  read: {                     // Gemini가 상품 설명·사진을 읽은 결과 (ProductBrief)
    product: '아이스 흑당 라떼', category: '음료', feelings: ['기쁨', '공감', '위로'],
    scene: '더운 오후, 한숨 돌릴 때', values: ['시원함', '달콤함'], colors: ['흑당 갈색', '흰색'], avoid: '없음'
  },
  concepts: [
    { id: 'yar', memeId: 'yar', title: '오후 3시 당 충전 → "야르~!"', format: '15초 반전형 쇼츠',
      hook: '"오후 3시, 배터리 3%"', effort: '쉬움', effortNote: '출연 1명 · 촬영 1곳 · 반나절',
      idea: '지친 오후 → 한 모금 → "야르~!" 한 번으로 기분이 반전되는 구조. 감탄사 하나라 설명이 필요 없어요.' },
    { id: 'osalhim', memeId: 'osalhim', title: '나의 "오살힘" 시리즈', format: '15초 시리즈 + 참여 해시태그',
      hook: '"오늘을 살아갈 힘이 필요할 때"', effort: '보통', effortNote: '컷 3곳 · 하루 · 시리즈로 확장',
      idea: '하루를 버티게 하는 작은 것 = 흑당 라떼. #나의오살힘 으로 이용자 참여를 이어 가기 좋아요.' },
    { id: 'ttogago', memeId: 'ttogago', title: '"줄 서야 하지만 또 마시고 싶은 흑당 라떼입니다"', format: '후기형 쇼츠 · 카피',
      hook: '"줄 서야 하지만…" 반전 자막', effort: '쉬움', effortNote: '기존 매장 영상 재편집 가능 · 2시간',
      idea: '단점 같은 장점(줄 서는 가게)을 먼저 말하고 "또 마시고 싶은"으로 뒤집는 말투 밈. 20·30대에게 익숙해요.' }
  ],
  excluded: [
    { memeId: 'pierrot', fix: '빨리 가려면: 기존 영상에 "흑당삐" 자막만 얹어 3일 안에 올리기' },
    { memeId: 'luckyvicky', fix: '' },
    { memeId: 'wegovy', fix: '' }
  ],
  kit: {
    yar: {
      hookWhy: '첫 2초에 공감 상황을 자막으로 보여 줘야 넘기지 않아요.',
      scenes: [
        { t: '0–3초', s: 0, e: 3, visual: '책상에 엎드린 직장인, 모니터 시계 오후 3:00', caption: '오후 3시, 배터리 3%', sound: '긴 한숨', shot: '정면 고정 · 조금 어둡게' },
        { t: '3–7초', s: 3, e: 7, visual: '흑당 라떼 컵을 드는 손, 얼음 클로즈업', caption: '(자막 없음)', sound: '얼음 달그락 — 크게', shot: '접사 · 슬로모션' },
        { t: '7–11초', s: 7, e: 11, visual: '한 모금 → 벌떡 일어나며 줌인', caption: '야르~!', sound: '짧은 환호 효과음', shot: '빠른 줌인 · 밝게', meme: true },
        { t: '11–15초', s: 11, e: 15, visual: '제품 컷 + 로고', caption: '당 충전 완료. 아이스 흑당 라떼', sound: '—', shot: '제품 정면 · 위쪽 여백' }
      ],
      captionStyle: '1컷 자막은 작게, 3컷 "야르~!"만 화면 70% 크기로 굵게 — 밈은 한 번만 크게 써요.',
      copies: [
        { ch: '릴스·인스타', text: '오후 3시 배터리 3%… 흑당 라떼 한 모금이면 야르~', tags: '#야르 #흑당라떼 #오후3시', limit: 2200 },
        { ch: '틱톡', text: '배터리 3% → 100% 걸린 시간: 한 모금', tags: '#야르 #흑당라떼', limit: 2200 },
        { ch: 'X', text: '당 떨어지는 오후 = 흑당 라떼 한 모금 = 야르', tags: '', limit: 280 }
      ],
      thumb: { headline: '야르~!', layout: '제품 왼쪽 1/3 · 큰 문구 오른쪽 위', colors: [ { hex: '#6B3F22', name: '흑당 갈색' }, { hex: '#F4E9DA', name: '크림' }, { hex: '#FFE14D', name: '밝은 노랑' } ], subject: '한 모금 직후 눈이 커진 표정' },
      prep: ['흑당 라떼 — 얼음 가득, 컵 로고가 정면', '사무실 책상 + 모니터에 오후 3:00 시계 화면', '출연자 1명 (표정 연기)', '환호 효과음 — 자체 녹음 (원곡 음원 쓰지 않기)'],
      posting: '9/28 (월) 오후 3시 전후 — 장면 속 시간과 맞추면 공감이 커요',
      checks: [
        { state: 'ok', k: '사전 대조', t: "'야르'를 감탄사로 썼어요 — 사전의 뜻·쓰임과 맞아요" },
        { state: 'ok', k: '사용 자제 단어', t: '없음' },
        { state: 'ok', k: '글자 수', t: 'X 안 27자 / 280자' },
        { state: 'fixed', k: '뺀 안 1개', t: "'야르한 가격' — 감탄사를 꾸밈말로 써서 뜻과 어긋나 뺐어요" },
        { state: 'ok', k: '근거', t: '출처 3건 · 가장 최근 2026-08-09' }
      ]
    }
  },
  shorts: {
    url: 'youtube.com/shorts/[영상 ID]',
    summary: '사무실에서 간식 하나로 기분이 반전되는 15초 상황극',
    memes: [ { name: '야르', conf: 86, quote: '야르~!' }, { name: '오살힘', conf: 52, quote: '오살힘 충전' } ],
    target: '10대 · 20대', why: '첫 2초 공감 자막 → 감탄사 한 번으로 반전 — 끝까지 보게 만드는 구조예요.', risk: '없음',
    remake: '이 구조를 흑당 라떼로 옮긴 게 A안이에요.'
  }
};

var DOSSIER = {
  id: 'pierrot', name: '삐에로 밈', aliases: ['선배삐', '개대박삐', '대박삐', '삐바삐', '정통삐', '삐출'],
  rule: "아무 말 뒤에 '삐'를 붙여 '삐에로'처럼 부르는 조어 놀이",
  definition: "온갖 말에 '삐(에로)'를 붙여 부르는 놀이. 선배 삐에로는 '선배삐', 잘 나가는 삐에로는 '개대박삐', 삐에로마다 다르다는 '삐바삐', 삐에로 출신은 '삐출'.",
  origin: "2026년 8월 13일 커뮤니티에 올라온 결혼 고민글에서 시작. 삐에로로 일하는 남자친구와의 결혼을 부모가 반대한다는 내용인데, 글쓴이가 쓴 '삐에로 업계 용어'가 웃기다며 퍼졌어요. 이어 '삐출' 연예인 찾기로 번졌어요.",
  nuance: "직업을 놀리는 게 아니라 'OO삐' 조어 자체가 놀이예요. 실제 삐에로 종사자 앞에서는 조심하세요.",
  reviewed: '사람 검수 완료',
  path: [
    { date: '8/13', kind: '커뮤니티', title: '결혼 고민 원글 — 댓글 수백 개', note: '첫 등장 · 사이트 이름은 표시하지 않아요' },
    { date: '8/13', kind: '뉴스', domain: 'insight.co.kr', title: "'삐에로 남친과 결혼하고파'… 커뮤니티 고민글 화제", note: '같은 날 기사화' },
    { date: '8/25', kind: '뉴스', domain: 'careet.net', title: '삐에로가 왜 갑자기 화제지? SNS에서 자주 보이는 밈 모음', note: "'OO삐' 호칭 자체가 유행" },
    { date: '8/28', kind: '웹', domain: 'gogumafarm.kr', title: '대박삐? 삐바삐? 밈잘알삐 만들어 주는 [2026년 8월 최신 밈 모음]', note: '마케팅 뉴스레터에 정리 — 브랜드 사용이 늘어날 신호' },
    { date: '8/29', kind: '뉴스', domain: 'v.daum.net', title: "“월수입 700만원?”…'삐에로 남친' 사연에 2030 열광한 이유", note: '주류 매체 진입' }
  ],
  usage: [ { age: '20대', share: 50 }, { age: '30대', share: 45 }, { age: '40대', share: 5 } ],
  goodFor: ["제품·상황에 '삐'를 붙이는 댓글 놀이 — \"너는 무슨 삐야?\"", '직장인 공감 시리즈 — 출근삐 · 야근삐', '팀·직원 소개 콘텐츠 — 우리 팀 개대박삐'],
  avoidFor: ['삐에로라는 직업 자체를 놀리는 장면', '원글 사연(결혼 반대)을 그대로 재현하기 — 실제 당사자가 있어요', '10대가 주 타깃인 캠페인 — 20·30대 밈이에요'],
  goodEx: { text: '출근삐, 야근삐… 오늘은 흑당삐로 버틴다', why: "'OO삐' 조어 규칙 그대로 — 밈을 아는 사람에게 바로 통해요" },
  badEx: { text: '삐에로처럼 웃기는 가격!', why: '조어가 아니라 직업 비유라 밈이 아니라 놀림으로 읽혀요' },
  safety: [
    { k: '비하·혐오', state: 'care', t: '직업을 놀리는 맥락이면 문제 — 조어 놀이로만 쓰기' },
    { k: '실존 인물·사연', state: 'care', t: '원글 사연의 당사자가 있어요 — 사연을 재현하지 않기' },
    { k: '음원 저작권', state: 'ok', t: '말놀이라 해당 없음' },
    { k: '정치·젠더 갈등', state: 'ok', t: '관련 없음' },
    { k: '광고 규제 표현', state: 'ok', t: '해당 없음' }
  ],
  angles: [
    { title: 'OO삐 릴레이', t: '출근삐 → 야근삐 → 흑당삐, 컷마다 삐를 붙여 반전' },
    { title: '댓글 이벤트 · 너는 무슨 삐?', t: '고정 댓글에 예시 3개를 먼저 달아 참여를 끌어내기' },
    { title: '우리 팀 개대박삐', t: '직원·매장 소개를 삐 호칭으로 — 브랜드 친근감' }
  ],
  fastLane: '쓸 수 있는 기간이 약 1~2주예요. 제작 2주짜리 영상은 늦어요 → 기존 영상에 자막만 얹는 3일짜리 안으로 가세요.'
};

var REPORT = {
  week: '9월 셋째 주 (9/14 ~ 9/20)',
  plans: [
    { title: 'A안 · 오후 3시 당 충전 → "야르~!"', meme: '야르', status: '승인 대기', due: '9/28 게시' },
    { title: '나의 "오살힘" 시리즈', meme: '오살힘', status: '초안', due: '10월 첫 주' }
  ]
};
// ===================== end v2 screen content =====================
