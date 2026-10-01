// =====================================================================
// SHARED DATA + HELPERS — paste this whole block into each artboard's
// <script type="text/x-dc" data-dc-script> ABOVE `class Component extends DCLogic`.
// Classic JS only (no import/export). Data comes from the repo's sample mode
// (apps/trend-web/lib/sample/*.ts): weekly index series are the real sample values.
// Weeks (week start): 6/22 … 9/7. Data timestamp: 2026. 9. 14 (월) 기준 · 예시 데이터
// You may trim fields an artboard doesn't use (e.g. mobile boards can drop DETAIL),
// but never change the values.
// =====================================================================

var WEEKS = ['6/22','6/29','7/6','7/13','7/20','7/27','8/3','8/10','8/17','8/24','8/31','9/7'];
var AS_OF = '2026. 9. 14 (월) 기준';

// lifecycle stage → label, colour group, marketer timing hint
var STAGE = {
  emerging:  { label: '태동', group: 'up',     timing: '선점 기회 — 아직 검증 전이에요' },
  rising:    { label: '상승', group: 'up',     timing: '지금 올라타기 좋은 때예요' },
  peak:      { label: '정점', group: 'peak',   timing: '노출이 가장 큰 구간 — 곧 꺾일 수 있어요' },
  steady:    { label: '유지', group: 'steady', timing: '오래 가는 말 — 캠페인 기간이 길어도 안전해요' },
  declining: { label: '하락', group: 'down',   timing: '패러디가 아니면 피하는 게 좋아요' }
};
var GROUPS = [
  { id: 'up',     label: '뜨는 중' },
  { id: 'peak',   label: '정점' },
  { id: 'steady', label: '꾸준함' },
  { id: 'down',   label: '식는 중' }
];
var SAFETY = { safe: '안전', caution: '주의', avoid: '사용 자제' };
var CATS = [
  { id: 'all',    label: '전체' },
  { id: 'word',   label: '말·유행어' },
  { id: 'sound',  label: '챌린지·사운드' },
  { id: 'visual', label: '영상·이미지' },
  { id: 'goods',  label: '음식·상품·패션' }
];
var REGIONS = [ { id: 'KR', label: '한국' }, { id: 'JP', label: '일본' }, { id: 'GLOBAL', label: '글로벌' } ];
var MORE_REGIONS = '대만 · 홍콩 · 태국 · 베트남 · 인도네시아 · 필리핀 · 말레이시아 · 싱가포르';
var PERIODS = [ { id: '7d', label: '7일', back: 1 }, { id: '30d', label: '30일', back: 4 }, { id: '90d', label: '90일', back: 11 } ];

// w = 12 weekly interest-index values (0–100 scale, relative), oldest → newest
var MEMES = {
  KR: [
    { id: 'pierrot',   name: '삐에로 밈', cat: 'word', stage: 'peak', safety: 'safe', ages: '20·30대', since: '2026-08', w: [0,0,0,0,0,0,0,5,60,90,95,92], gloss: "온갖 말에 '삐'를 붙이는 말놀이 (선배삐·개대박삐·삐바삐)", note: '직업 자체를 놀리는 맥락은 피하기' },
    { id: 'youngkk',   name: '영크크', cat: 'word', stage: 'steady', safety: 'safe', ages: '10·20대', since: '2026-02', w: [52,50,54,51,53,50,52,49,51,50,52,51], gloss: '젊고 트렌디한 감성, 또는 그런 사람. 반대말은 늙크크' },
    { id: 'yar',       name: '야르', cat: 'word', stage: 'peak', safety: 'safe', ages: '10대', since: '2026-03', w: [30,34,38,42,45,47,50,52,51,53,52,54], gloss: "'앗싸·오예' 같은 신남의 감탄사" },
    { id: 'bamti',     name: '밤티', cat: 'word', stage: 'rising', safety: 'caution', ages: '10·20대', since: '2020-03', w: [20,22,25,24,28,30,33,35,38,40,44,47], gloss: "촌스럽고 엉성하다는 평가. 요즘은 '엉성한데 정감 간다'까지", note: '실존 인물의 별명에서 온 말 — 사람 외모에 쓰면 비하' },
    { id: 'oldkk',     name: '늙크크', cat: 'word', stage: 'steady', safety: 'safe', ages: '20·30대', since: '2026-02', w: [44,46,45,47,46,48,47,46,48,47,46,47], gloss: "옛날 감성, 이른바 '아재 감성'. 영크크의 반대말" },
    { id: 'typo',      name: '속담 오타 밈', cat: 'word', stage: 'rising', safety: 'safe', ages: '10·20대', since: '2026', w: [6,7,8,9,10,11,12,13,14,16,18,28], gloss: '속담을 한 글자 틀려 엉뚱한 장면을 만드는 말장난 (모르는 개 산책)' },
    { id: 'chaek',     name: '책없쾌', cat: 'word', stage: 'rising', safety: 'safe', ages: '10·20대', since: '2026-05', w: [8,9,10,11,12,13,14,15,16,17,18,28], gloss: '책임 없는 쾌락 — 부담 없이 재미만 보는 상황' },
    { id: 'gemmini',   name: '젬민이', cat: 'word', stage: 'rising', safety: 'safe', ages: '20·30대', since: '2026-02', w: [10,11,13,14,16,17,19,21,22,24,26,28], gloss: '모든 결정을 AI에게 맡기는 사람' },
    { id: 'nanri',     name: '난리자베스', cat: 'word', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-01', w: [70,66,60,55,50,46,42,40,36,33,30,28], gloss: "'난리 났다'를 늘인 말. 슬프자베스·행복자베스로 응용" },
    { id: 'shagal',    name: '샤갈', cat: 'word', stage: 'steady', safety: 'caution', ages: '10·20대', since: '2025-11', w: [26,25,27,26,28,27,26,27,28,27,26,27], gloss: "욕설을 순화한 감탄사 ('아 샤갈')", note: '순화했어도 어른에겐 욕으로 들려요' },
    { id: 'yarsong',   name: '야르송', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10대', since: '2026-04', w: [60,64,62,58,50,45,40,36,32,30,28,26], gloss: "'야르~'를 요들처럼 반복하는 노래. 알람·배경음으로 재사용" },
    { id: 'ttogago',   name: '또 가고 싶은 OO입니다', cat: 'word', stage: 'steady', safety: 'safe', ages: '20·30대', since: '2025-11', w: [18,19,20,22,21,23,22,24,23,25,24,25], gloss: "'비싸지만 또 가고 싶은 OO입니다' 식 소개 말투" },
    { id: 'temu',      name: '테무인간', cat: 'word', stage: 'steady', safety: 'caution', ages: '20·30대', since: '2025-10', w: [22,23,22,24,23,22,24,23,25,24,23,24], gloss: '겉만 번지르르하고 실속 없는 사람', note: '남을 깎아내리는 말 — 자조로만 쓰기' },
    { id: 'jungti',    name: '중티', cat: 'word', stage: 'rising', safety: 'avoid', ages: '10·20대', since: '2026-01', w: [8,9,10,12,12,14,15,17,18,20,22,24], gloss: "'중국 티 난다'. 과하게 화려한 디자인을 두고 하는 말", note: '국적 고정관념 — 공개 카피에 쓰지 않기' },
    { id: 'chugumi',   name: '추구미', cat: 'word', stage: 'steady', safety: 'safe', ages: '10~30대', since: '2024-02', w: [28,27,29,28,30,29,28,30,29,28,30,29], gloss: "내가 지향하는 모습·스타일 ('내 추구미는 청순')" },
    { id: 'neujo',     name: '느좋', cat: 'word', stage: 'steady', safety: 'safe', ages: '10·20대', since: '2023-06', w: [24,25,24,26,25,24,26,25,26,25,24,25], gloss: "'느낌 좋다'의 줄임말" },
    { id: 'osalhim',   name: '오살힘', cat: 'word', stage: 'steady', safety: 'safe', ages: '10~30대', since: '2025-06', w: [20,21,20,22,21,23,22,21,23,22,21,22], gloss: '오늘을 살아갈 힘 — 하루를 버티게 하는 작은 것' },
    { id: 'jeommechu', name: '점메추', cat: 'word', stage: 'steady', safety: 'safe', ages: '20·30대', since: '2017', w: [21,22,21,23,22,21,23,22,23,22,21,22], gloss: '점심 메뉴 추천. 저메추·아메추의 원형' },
    { id: 'teto',      name: '테토남', cat: 'word', stage: 'declining', safety: 'safe', ages: '20·30대', since: '2025-03', w: [40,38,35,33,30,28,27,25,24,22,21,20], gloss: '성격을 호르몬 이름으로 나누는 유형 놀이', note: '진지하게 쓰면 뒤처진 느낌' },
    { id: 'yoonjung',  name: '윤정아 챌린지', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-01', w: [90,80,70,60,50,42,36,30,26,22,18,15], gloss: "'윤정아 윤정아 / 왜요 쌤'을 주고받는 상황극 챌린지" },
    { id: 'yangeuiji', name: '자려고 누웠는데 양의지', cat: 'sound', stage: 'declining', safety: 'safe', ages: '20·30대', since: '2026-05', w: [80,72,64,56,48,42,36,30,26,22,18,16], gloss: '아이오아이 노래와 야구 응원가를 합친 말장난' },
    { id: 'dujjonku',  name: '두쫀쿠', cat: 'goods', stage: 'declining', safety: 'safe', ages: '10~30대', since: '2025-08', w: [45,40,36,33,30,28,25,23,21,20,18,17], gloss: '두바이 쫀득 쿠키. 2025년 하반기 히트 간식' },
    { id: 'luckyvicky',name: '럭키비키', cat: 'word', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2024-04', w: [40,36,30,27,22,20,17,15,13,12,10,9], gloss: "나쁜 상황도 '오히려 좋아'로 뒤집는 말", note: '유행이 지나 브랜드가 진지하게 쓰면 촌스러워요' },
    { id: 'wonyoung',  name: '원영적 사고', cat: 'word', stage: 'steady', safety: 'safe', ages: '10~30대', since: '2024-04', w: [21,22,20,23,22,24,21,22,23,22,21,22], gloss: '무슨 일이든 유리하게 해석하는 초긍정 사고' },
    { id: 'wegovy',    name: '천연 위고비', cat: 'goods', stage: 'steady', safety: 'caution', ages: '20·30대', since: '2026-04', w: [15,14,16,15,14,16,15,14,15,16,15,15], gloss: '포만감 주는 달걀·올리브오일 조합을 비만치료제에 빗댄 말', note: '의약품 이름 — 광고 문구엔 부적합 (표시·광고 규제)' },
    { id: 'raeulla',   name: '라을라', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-04', w: [40,36,32,28,24,20,18,16,14,12,11,10], gloss: '하품이나 실수를 성악 톤으로 넘기는 소리' },
    { id: 'namu',      name: '나무 챌린지', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-02', w: [30,24,18,14,10,8,6,5,4,3,2,2], gloss: '나무처럼 서서 팔을 흔드는 춤 챌린지' }
  ],
  JP: [
    { id: 'oshikatsu', name: '推し活', lang: 'ja', cat: 'word', stage: 'steady', safety: 'safe', ages: '10~30대', since: '2020', w: [49,50,51,49,50,51,49,50,51,49,50,51], gloss: '좋아하는 대상을 응원하는 활동 전반 (오시카츠)' },
    { id: 'sixsevenjp',name: 'シックスセブン', lang: 'ja', cat: 'word', stage: 'rising', safety: 'safe', ages: '10대', since: '2025', w: [10,12,14,15,17,19,21,23,25,26,28,30], gloss: "미국 '6-7' 밈의 일본 표기" },
    { id: 'universe',  name: '時空超えてユニバース', lang: 'ja', cat: 'sound', stage: 'emerging', safety: 'safe', ages: '10·20대', since: '2026-09', w: [0,0,1,0,0,1,0,0,1,0,21,42], gloss: 'M!LK 신곡 티저 구절. 9월 인기 영상' },
    { id: 'jiraikei',  name: '地雷系', lang: 'ja', cat: 'goods', stage: 'steady', safety: 'safe', ages: '10·20대', since: '2020', w: [19,20,21,19,20,21,19,20,21,19,20,21], gloss: '검정·핑크 프릴에 창백한 메이크업을 한 스타일' },
    { id: 'mochicookie',name: '韓国もちクッキー', lang: 'ja', cat: 'goods', stage: 'rising', safety: 'safe', ages: '10·20대', since: '2026', w: [5,6,7,9,10,11,12,13,14,16,17,18], gloss: '한국 두쫀쿠의 일본 이름' },
    { id: 'dubaichoco',name: 'ドバイチョコ', lang: 'ja', cat: 'goods', stage: 'declining', safety: 'safe', ages: '10~30대', since: '2025', w: [35,33,31,29,27,25,22,20,18,16,14,12], gloss: '두바이 초콜릿' },
    { id: 'labubujp',  name: 'ラブブ', lang: 'ja', cat: 'goods', stage: 'declining', safety: 'safe', ages: '10~30대', since: '2025', w: [40,38,35,33,31,29,26,24,22,20,17,15], gloss: '라부부 — 팝마트 키링 인형' }
  ],
  GLOBAL: [
    { id: 'dipstack',  name: 'Three Layer Dip Stack', lang: 'en', cat: 'sound', stage: 'peak', safety: 'safe', ages: '10·20대', since: '2026-07', w: [2,3,8,14,20,28,35,60,70,75,78,80], gloss: '프링글스 광고 대사를 노래처럼 만든 브레인로트' },
    { id: 'argentina', name: 'Argentina AI Muscle Dancing', lang: 'en', cat: 'visual', stage: 'peak', safety: 'safe', ages: '10·20대', since: '2026-07', w: [0,0,0,0,0,0,5,10,20,40,60,75], gloss: 'AI로 만든 근육질 선수들이 응원가에 맞춰 추는 춤' },
    { id: 'lapeace',   name: 'La Peace', lang: 'en', cat: 'visual', stage: 'peak', safety: 'safe', ages: '10·20대', since: '2026-08', w: [0,0,0,0,0,0,0,20,55,70,74,72], gloss: "평온한 노인 사진에 얹는 '라 피스' 철학자 톤 밈" },
    { id: 'sixseven',  name: '6-7', lang: 'en', cat: 'word', stage: 'steady', safety: 'safe', ages: '10대', since: '2025', w: [69,70,71,69,70,71,69,70,71,69,70,71], gloss: '뜻 없는 감탄사. 2025년 하반기 최대 밈' },
    { id: 'ronaldo',   name: 'Ronaldo Pasta', lang: 'en', cat: 'visual', stage: 'steady', safety: 'safe', ages: '10·20대', since: '2026-07', w: [10,12,30,45,55,60,58,55,50,48,45,44], gloss: '호날두 파스타 장면을 과장 편집한 브레인로트' },
    { id: 'november',  name: 'Remember November 2026 Is Coming', lang: 'en', cat: 'sound', stage: 'emerging', safety: 'safe', ages: '10·20대', since: '2026-09', w: [0,0,0,0,0,0,0,0,0,0,12,40], gloss: "AI 북극곰이 부르는 '미래에서 온 밈'" },
    { id: 'ptpa',      name: 'Ptpa Ptpe Ptpi Ptpo Ptpu', lang: 'en', cat: 'sound', stage: 'emerging', safety: 'safe', ages: '10대', since: '2026-08', w: [0,0,0,0,0,0,0,0,0,3,10,24], gloss: '발성 연습 영상을 펑크 비트에 얹은 브레인로트' },
    { id: 'aislop',    name: 'AI slop', lang: 'en', cat: 'word', stage: 'steady', safety: 'caution', ages: '20~40대', since: '2024-05', w: [33,34,32,35,34,33,36,35,34,36,35,36], gloss: 'AI가 대량으로 찍어낸 저품질 콘텐츠', note: 'AI를 쓰는 브랜드라면 역풍 주의' },
    { id: 'wowokay',   name: 'Wow okay', lang: 'en', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-05', w: [50,52,48,44,40,36,32,28,25,22,20,18], gloss: '한 마디를 네 가지 톤으로 연기하는 챌린지' },
    { id: 'airpods',   name: 'I forgot my AirPods', lang: 'en', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-05', w: [55,58,52,46,40,34,28,24,20,16,14,12], gloss: '옆 사람이 노래를 대신 불러 주는 상황극' },
    { id: 'crumbl',    name: 'viral Crumbl Labubu cookie', lang: 'en', cat: 'goods', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026', w: [70,66,60,52,44,38,32,28,24,20,18,16], gloss: '유행 먹거리를 한 이름에 몰아넣은 가짜 시식 밈' },
    { id: 'gutgenug',  name: 'Du Bist Gut Genug', lang: 'de', cat: 'sound', stage: 'declining', safety: 'safe', ages: '10·20대', since: '2026-06', w: [85,80,70,60,50,42,36,30,26,22,20,18], gloss: '독일 노래의 팔세토 구절로 만든 편집 밈' },
    { id: 'tungtung',  name: 'Tung Tung Tung Sahur', lang: 'en', cat: 'visual', stage: 'declining', safety: 'safe', ages: '10대', since: '2025-02', w: [12,10,8,7,6,5,4,3,3,2,2,1], gloss: '이탈리안 브레인로트의 대표 캐릭터' },
    { id: 'skibidi',   name: 'skibidi', lang: 'en', cat: 'word', stage: 'declining', safety: 'safe', ages: '10대', since: '2023', w: [30,28,26,24,22,20,18,16,14,12,10,8], gloss: '뜻 없이 붙이는 감탄·수식어' }
  ]
};
var DEFAULT_PICK = { KR: 'pierrot', JP: 'universe', GLOBAL: 'dipstack' };

// ---------- helpers ----------
function pct(w, back) { var base = w[11 - back]; if (!base) return null; return Math.round((w[11] - base) / base * 100); }
function fmtPct(p) { return p === null ? 'NEW' : (p > 0 ? '+' : '') + p + '%'; }
function trendDir(p) { return p === null || p > 5 ? 'up' : (p < -5 ? 'down' : 'flat'); }
// polyline points for a sparkline; scaleMax: null = per-series max, or a fixed number (e.g. 100)
function sparkPoints(w, W, H, pad, scaleMax) {
  var max = scaleMax || Math.max.apply(null, w.concat([1]));
  return w.map(function (v, i) {
    var x = pad + i * (W - 2 * pad) / 11;
    var y = H - pad - (v / max) * (H - 2 * pad);
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
}
// closed area polygon under the same line (for a filled sparkline)
function sparkArea(w, W, H, pad, scaleMax) {
  return pad + ',' + (H - pad) + ' ' + sparkPoints(w, W, H, pad, scaleMax) + ' ' + (W - pad) + ',' + (H - pad);
}
function estWidth(text, fs) {
  var w = 0;
  for (var i = 0; i < text.length; i++) {
    var ch = text[i];
    if (/[ᄀ-ᇿ㄰-㆏가-힯぀-ヿ㐀-鿿]/.test(ch)) w += fs * 1.0;
    else if (ch === ' ') w += fs * 0.28;
    else if (/[A-Z0-9]/.test(ch)) w += fs * 0.64;
    else w += fs * 0.54;
  }
  return w;
}
// Spiral word-cloud layout. items need { name, weight }. Returns placed copies with
// x, y (top-left px inside a W×H box), bw, bh (box size incl. padding), fs (font px), rank.
// A word that doesn't fit is retried smaller (up to 5 times, x0.85 each); if it still
// doesn't fit it is dropped — tune min/max/pad (and opt.limit) so every word you show fits.
function layoutCloud(items, W, H, opt) {
  var o = { min: 14, max: 60, padX: 10, padY: 6, widthFactor: 1, lineH: 1.2, xStretch: 1.35, yStretch: 0.75, limit: 999 };
  for (var k in (opt || {})) o[k] = opt[k];
  var sorted = items.slice().sort(function (a, b) { return b.weight - a.weight; }).slice(0, o.limit);
  var top = Math.max.apply(null, sorted.map(function (s) { return s.weight; }).concat([1]));
  var boxes = [], out = [];
  sorted.forEach(function (it, idx) {
    var fs = Math.round(o.min + (o.max - o.min) * Math.sqrt(it.weight / top));
    for (var attempt = 0; attempt < 6; attempt++) {
      var w = estWidth(it.name, fs) * o.widthFactor + o.padX * 2;
      while (w > W - 4 && fs > 10) { fs = Math.floor(fs * 0.9); w = estWidth(it.name, fs) * o.widthFactor + o.padX * 2; }
      var h = fs * o.lineH + o.padY * 2;
      var placed = false;
      for (var i = 0; i < 2600; i++) {
        var a = i * 0.28, r = 3.2 * a;
        var x = W / 2 + r * Math.cos(a) * o.xStretch - w / 2;
        var y = H / 2 + r * Math.sin(a) * o.yStretch - h / 2;
        if (x < 0 || y < 0 || x + w > W || y + h > H) continue;
        var hit = false;
        for (var j = 0; j < boxes.length; j++) { var b = boxes[j]; if (x < b.x + b.w && b.x < x + w && y < b.y + b.h && b.y < y + h) { hit = true; break; } }
        if (hit) continue;
        boxes.push({ x: x, y: y, w: w, h: h });
        var copy = {}; for (var kk in it) copy[kk] = it[kk];
        copy.x = Math.round(x); copy.y = Math.round(y); copy.bw = Math.round(w); copy.bh = Math.round(h); copy.fs = fs; copy.rank = idx;
        out.push(copy);
        placed = true;
        break;
      }
      if (placed) break;
      fs = Math.max(10, Math.floor(fs * 0.85));
    }
  });
  return out;
}


// ===================== v2: marketer decision layer =====================
// Tags the pipeline's fit step (local Gemma) would attach to each meme:
// voice = 말의 결 (wholesome 순함 · playful 장난 · edgy 날 섬 · crude 거침)
// fits  = 잘 붙는 분야 (food 음식·음료 · beauty 뷰티 · fashion 패션 · app 앱·서비스 · place 공간·여행 · ent 여가·엔터 · any 가리지 않음)
// diff  = 확산 단계 (underground 아는 사람만 · spreading 퍼지는 중 · mainstream 대중화 · fading 식는 중)
// fmt   = 쓰는 형식 (자막·카피로 쓰는 말 / 말놀이 / 챌린지·춤 / 노래·소리 / 영상 편집 / 상품)
var TAGS = {
  pierrot:   { voice: 'playful',   fits: ['any'], diff: 'mainstream', fmt: '말놀이' },
  youngkk:   { voice: 'playful',   fits: ['fashion', 'beauty', 'any'], diff: 'mainstream', fmt: '자막·카피' },
  yar:       { voice: 'playful',   fits: ['food', 'any'], diff: 'mainstream', fmt: '감탄사' },
  bamti:     { voice: 'edgy',      fits: ['fashion', 'food'], diff: 'spreading', fmt: '평가하는 말' },
  oldkk:     { voice: 'playful',   fits: ['any'], diff: 'mainstream', fmt: '자막·카피' },
  typo:      { voice: 'playful',   fits: ['any'], diff: 'spreading', fmt: '말놀이' },
  chaek:     { voice: 'playful',   fits: ['ent'], diff: 'spreading', fmt: '줄임말' },
  gemmini:   { voice: 'playful',   fits: ['app'], diff: 'spreading', fmt: '별명' },
  nanri:     { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '말놀이' },
  shagal:    { voice: 'crude',     fits: [], diff: 'mainstream', fmt: '감탄사' },
  yarsong:   { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '노래·소리' },
  ttogago:   { voice: 'wholesome', fits: ['food', 'place'], diff: 'mainstream', fmt: '말투' },
  temu:      { voice: 'edgy',      fits: [], diff: 'mainstream', fmt: '별명' },
  jungti:    { voice: 'crude',     fits: [], diff: 'spreading', fmt: '평가하는 말' },
  chugumi:   { voice: 'wholesome', fits: ['beauty', 'fashion'], diff: 'mainstream', fmt: '자막·카피' },
  neujo:     { voice: 'wholesome', fits: ['beauty', 'place', 'any'], diff: 'mainstream', fmt: '줄임말' },
  osalhim:   { voice: 'wholesome', fits: ['any'], diff: 'mainstream', fmt: '줄임말' },
  jeommechu: { voice: 'wholesome', fits: ['food'], diff: 'mainstream', fmt: '줄임말' },
  teto:      { voice: 'playful',   fits: ['beauty', 'fashion'], diff: 'fading', fmt: '유형 놀이' },
  yoonjung:  { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '챌린지' },
  yangeuiji: { voice: 'playful',   fits: ['ent'], diff: 'fading', fmt: '노래·소리' },
  dujjonku:  { voice: 'wholesome', fits: ['food'], diff: 'fading', fmt: '상품' },
  luckyvicky:{ voice: 'wholesome', fits: ['any'], diff: 'fading', fmt: '자막·카피' },
  wonyoung:  { voice: 'wholesome', fits: ['any'], diff: 'mainstream', fmt: '자막·카피' },
  wegovy:    { voice: 'playful',   fits: ['food'], diff: 'mainstream', fmt: '별명' },
  raeulla:   { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '노래·소리' },
  namu:      { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '챌린지·춤' },
  oshikatsu: { voice: 'wholesome', fits: ['ent', 'any'], diff: 'mainstream', fmt: '자막·카피' },
  sixsevenjp:{ voice: 'playful',   fits: ['any'], diff: 'spreading', fmt: '감탄사' },
  universe:  { voice: 'playful',   fits: ['ent'], diff: 'underground', fmt: '노래·소리' },
  jiraikei:  { voice: 'edgy',      fits: ['fashion', 'beauty'], diff: 'mainstream', fmt: '스타일' },
  mochicookie:{ voice: 'wholesome', fits: ['food'], diff: 'spreading', fmt: '상품' },
  dubaichoco:{ voice: 'wholesome', fits: ['food'], diff: 'fading', fmt: '상품' },
  labubujp:  { voice: 'wholesome', fits: ['ent'], diff: 'fading', fmt: '상품' },
  dipstack:  { voice: 'playful',   fits: ['food'], diff: 'mainstream', fmt: '노래·소리', tip: '다른 과자 브랜드 광고에서 나온 밈 — 식품 브랜드가 쓰면 그 브랜드를 홍보하게 돼요' },
  argentina: { voice: 'playful',   fits: ['ent'], diff: 'spreading', fmt: '영상 편집', tip: '실존 선수 얼굴을 AI로 합성한 영상 — 광고에 쓰면 초상권 문제가 생겨요' },
  lapeace:   { voice: 'playful',   fits: ['any'], diff: 'mainstream', fmt: '이미지 밈' },
  sixseven:  { voice: 'playful',   fits: ['any'], diff: 'mainstream', fmt: '감탄사' },
  ronaldo:   { voice: 'playful',   fits: ['food', 'ent'], diff: 'mainstream', fmt: '영상 편집', tip: '실존 인물 장면을 편집한 밈 — 원본 장면을 쓰면 초상권 문제가 생겨요' },
  november:  { voice: 'playful',   fits: ['any'], diff: 'underground', fmt: '노래·소리' },
  ptpa:      { voice: 'playful',   fits: ['any'], diff: 'underground', fmt: '노래·소리' },
  aislop:    { voice: 'edgy',      fits: [], diff: 'mainstream', fmt: '평가하는 말' },
  wowokay:   { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '챌린지' },
  airpods:   { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '챌린지' },
  crumbl:    { voice: 'playful',   fits: ['food'], diff: 'fading', fmt: '영상 편집' },
  gutgenug:  { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '노래·소리', tip: '원곡 음원을 쓰면 저작권 허락이 필요해요' },
  tungtung:  { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '캐릭터' },
  skibidi:   { voice: 'playful',   fits: ['any'], diff: 'fading', fmt: '감탄사' }
};
(function () { for (var r in MEMES) MEMES[r].forEach(function (m) { var t = TAGS[m.id] || {}; for (var k in t) m[k] = t[k]; }); })();

var DIFF = { underground: '아는 사람만', spreading: '퍼지는 중', mainstream: '대중화', fading: '식는 중' };
var DIFF_HINT = {
  underground: '아직 일부만 알아요 — 쓰면 설명이 필요해요',
  spreading: '쇼츠에서 퍼지는 중 — 브랜드가 먼저 쓰기 좋은 때예요',
  mainstream: '뉴스에도 나왔어요 — 다들 알지만 브랜드 사용도 늘어나요',
  fading: '언급이 줄고 있어요 — 새로 쓰면 늦어 보여요'
};
var FIT_LABEL = { food: '음식·음료', beauty: '뷰티', fashion: '패션', app: '앱·서비스', place: '공간·여행', ent: '여가·엔터', any: '분야 무관' };

// 브랜드 프로필 — 설정에서 만들고, 모든 판정의 기준이 된다
var BRANDS = [
  { id: 'latte', name: '아이스 흑당 라떼', kind: '음료', cat: 'food',   ages: ['10대', '20대'], region: 'KR', tone: '친근하게',   voices: ['wholesome', 'playful'] },
  { id: 'app',   name: '가계부 앱',        kind: '앱·서비스', cat: 'app', ages: ['20대', '30대'], region: 'KR', tone: '위트 있게', voices: ['wholesome', 'playful', 'edgy'] },
  { id: 'sun',   name: '비건 선크림',      kind: '뷰티', cat: 'beauty', ages: ['20대'], region: 'KR', tone: '산뜻하게',   voices: ['wholesome'] }
];
var LEADS = [ { days: 3, label: '3일' }, { days: 14, label: '2주' }, { days: 28, label: '4주' } ]; // 기획~게시까지 걸리는 기간

function ageSet(s) {
  // '20·30대' → [20,30] · '10~30대' → [10,20,30] · '10대' → [10] · '40대 이상' → [40]
  var nums = (String(s).match(/\d+/g) || []).map(Number);
  if (/~/.test(s) && nums.length === 2) { var out = []; for (var a = nums[0]; a <= nums[1]; a += 10) out.push(a); return out; }
  return nums;
}
function brandAges(b) { var o = []; b.ages.forEach(function (a) { o = o.concat(ageSet(a)); }); return o; }

// 쓸 수 있는 기간 추정 (규칙): 수명 단계 + 최근 1주 변화
function lifespan(m) {
  var d7 = pct(m.w, 1);
  if (m.stage === 'declining') return { days: 0, label: '지났어요' };
  if (m.stage === 'emerging') return { days: null, label: '아직 몰라요' };
  if (m.stage === 'rising') return { days: 42, label: '약 4~6주' };
  if (m.stage === 'peak') return d7 !== null && d7 < 0 ? { days: 10, label: '약 1~2주' } : { days: 21, label: '약 2~3주' };
  return { days: 999, label: '기간 제약 없음' };
}

var VERDICT = {
  go:    { label: '지금 쓰기',   short: 'GO' },
  watch: { label: '지켜보기',   short: '관찰' },
  care:  { label: '조건부',     short: '조건부' },
  late:  { label: '늦었어요',   short: '늦음' },
  no:    { label: '쓰지 마세요', short: '금지' }
};

// 판정: 먼저 거르는 규칙(자제·결·하락·주의·기간) → 점수(타이밍 40 · 타깃 35 · 분야 25)
function judge(m, brand, leadDays) {
  var d7 = pct(m.w, 1);
  var life = lifespan(m);
  var tScore = { emerging: 55, rising: 95, peak: (d7 !== null && d7 < 0) ? 60 : 85, steady: 70, declining: 15 }[m.stage];
  var ba = brandAges(brand), ma = ageSet(m.ages);
  var inter = ma.filter(function (a) { return ba.indexOf(a) >= 0; }).length;
  var aScore = ma.length ? Math.round(Math.max(20, 100 * inter / Math.min(ba.length, ma.length))) : 20;
  var fits = m.fits || [];
  var fScore = fits.indexOf(brand.cat) >= 0 ? 100 : (fits.indexOf('any') >= 0 ? 70 : 30);
  var score = Math.round(tScore * 0.4 + aScore * 0.35 + fScore * 0.25);
  var voiceOk = brand.voices.indexOf(m.voice) >= 0;
  var why = [];
  var v;
  if (m.safety === 'avoid') { v = 'no'; why.push(m.note || '공개 카피에 쓰면 안 되는 말이에요'); }
  else if (!voiceOk && m.safety === 'caution') { v = 'no'; why.push((m.note || '말의 결이 거칠어요') + ' — ' + brand.tone + ' 톤과 안 맞아요'); }
  else if (m.stage === 'declining') { v = 'late'; why.push('12주 새 관심도 ' + m.w[0] + ' → ' + m.w[11] + ' — 지금 쓰면 늦어 보여요'); }
  else if (m.safety === 'caution') { v = 'care'; why.push(m.note || '쓰기 전에 문맥을 확인하세요'); }
  else if (!voiceOk) { v = 'care'; why.push('말의 결이 ' + brand.tone + ' 톤과 조금 달라요'); }
  else if (life.days !== null && life.days < leadDays) { v = 'care'; why.push('제작 기간(' + leadLabel(leadDays) + ') 안에 꺾일 수 있어요 — 가볍게 빨리 가야 해요'); }
  else if (m.stage === 'emerging') { v = 'watch'; why.push('막 나온 밈이라 아직 검증 전이에요'); }
  else if (fScore === 30) { v = 'care'; why.push(brand.kind + ' 분야와 연결이 약해요'); }
  else if (score >= 70) { v = 'go'; }
  else { v = 'care'; why.push('타깃 연령이 조금 달라요'); }
  if (m.tip) why.push(m.tip);
  // 적합도는 판정과 맞춘다: 금지 ≤ 20 · 늦음 ≤ 40 · 조건부 ≤ 69 (기획 적기 = 70 이상은 지금 쓰기·지켜보기만)
  if (v === 'no') score = Math.min(score, 20); else if (v === 'late') score = Math.min(score, 40); else if (v === 'care') score = Math.min(score, 69);
  // 긍정 이유 (지금 쓰기일 때 먼저 보여 줌)
  var plus = [];
  if (m.stage === 'rising') plus.push('아직 오르는 중');
  if (m.stage === 'peak' && tScore >= 85) plus.push('정점 구간');
  if (m.stage === 'steady') plus.push('오래 가는 말');
  if (aScore >= 100) plus.push('타깃 연령 일치');
  else if (aScore >= 50) plus.push('타깃 연령 일부 겹침');
  if (fScore === 100) plus.push(FIT_LABEL[brand.cat] + '에 잘 붙음');
  return { v: v, label: VERDICT[v].label, score: score, timing: tScore, target: aScore, fit: fScore, life: life, why: why, plus: plus };
}
function leadLabel(d) { for (var i = 0; i < LEADS.length; i++) if (LEADS[i].days === d) return LEADS[i].label; return d + '일'; }

// 워치리스트 알림 (규칙으로 만든 문장)
var WATCH_IDS = ['yar', 'pierrot', 'typo', 'nanri'];
function alertFor(m) {
  var d7 = pct(m.w, 1), d4 = pct(m.w, 4);
  if (m.stage === 'declining') return { kind: 'down', text: '12주 새 ' + m.w[0] + ' → ' + m.w[11] + ' — 쓰고 있다면 다음 밈으로 바꿀 때예요' };
  if (m.stage === 'peak' && d7 !== null && d7 < 0) return { kind: 'turn', text: '지난주보다 ' + fmtPct(d7) + ' — 정점을 지났을 수 있어요' };
  if (d7 !== null && d7 >= 30) return { kind: 'up', text: '지난주보다 ' + fmtPct(d7) + ' 급등 — 선점 기회예요' };
  if (m.stage === 'peak') return { kind: 'peak', text: '정점 구간 — 이번 주가 게시 적기예요' };
  return { kind: 'flat', text: '4주 변화 ' + fmtPct(d4) + ' — 큰 변화 없어요' };
}

var SOURCES_NOTE = '유튜브 쇼츠 인기 영상 · 구글 트렌드 · 네이버 데이터랩 · 뉴스 · 위키 (커뮤니티는 개수만 셉니다)';
var METHOD_NOTE = '판정 = 수명 단계 40 + 타깃 연령 겹침 35 + 분야·톤 25. 사용 자제·하락·제작 기간 초과는 점수 전에 먼저 걸러요. 수명 단계는 주간 언급량과 출처가 나온 순서(커뮤니티 → 쇼츠 → 뉴스)로 규칙 코드가 정해요.';
// ===================== end v2 logic =====================
