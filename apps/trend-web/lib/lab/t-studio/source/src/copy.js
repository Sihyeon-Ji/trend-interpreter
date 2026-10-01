// ===== plain-language copy for the web app (overrides the canvas wording) =====
VERDICT = {
  go:    { label: '지금 쓰세요',       short: '지금 쓰세요' },
  watch: { label: '조금 더 지켜봐요',  short: '지켜봐요' },
  care:  { label: '조심해서 쓰세요',   short: '조심해서' },
  late:  { label: '이미 늦었어요',     short: '늦었어요' },
  no:    { label: '쓰지 마세요',       short: '쓰지 마세요' }
};
STAGE.emerging.label = '막 뜨는 중'; STAGE.rising.label = '오르는 중'; STAGE.peak.label = '최고점'; STAGE.steady.label = '꾸준함'; STAGE.declining.label = '식는 중';
STAGE.emerging.timing = '먼저 쓰면 눈에 띄지만, 아직 확실하지 않아요';
STAGE.rising.timing = '지금 올라타기 좋아요';
STAGE.peak.timing = '가장 많이 보이는 때예요 — 곧 꺾일 수 있어요';
STAGE.steady.timing = '오래 가는 말이라 캠페인이 길어도 괜찮아요';
STAGE.declining.timing = '패러디가 아니면 피하는 게 좋아요';
GROUPS = [ { id: 'up', label: '뜨는 중' }, { id: 'peak', label: '최고점' }, { id: 'steady', label: '꾸준함' }, { id: 'down', label: '식는 중' } ];
DIFF = { underground: '아는 사람만 알아요', spreading: '퍼지는 중이에요', mainstream: '다들 알아요', fading: '잊혀 가요' };
DIFF_HINT = {
  underground: '쓰려면 뜻을 함께 알려 줘야 해요',
  spreading: '쇼츠에서 퍼지는 중이라 브랜드가 먼저 쓰기 좋은 때예요',
  mainstream: '뉴스에도 나왔어요. 다들 알지만 다른 브랜드도 쓰기 시작해요',
  fading: '언급이 줄고 있어서 새로 쓰면 늦어 보여요'
};
METHOD_NOTE = '지금 얼마나 뜨는지(40%), 우리 타깃 나이대가 쓰는 말인지(35%), 우리 분야·말투와 맞는지(25%)를 합쳐 어울림 점수를 내요. 쓰면 안 되는 말, 이미 식은 밈, 올리기 전에 식을 밈은 점수와 상관없이 먼저 걸러요.';
SOURCES_NOTE = '유튜브 쇼츠 인기 영상, 구글 트렌드, 네이버 데이터랩, 뉴스, 위키에서 모아요 (커뮤니티는 글 개수만 세요)';
STUDIO.kit.yar.checks = [
  { state: 'ok', k: '밈을 뜻대로 썼나', t: "'야르'를 신날 때 외치는 말로 썼어요 — 원래 쓰임과 같아요" },
  { state: 'ok', k: '쓰면 안 되는 말', t: '없어요' },
  { state: 'ok', k: '글자 수', t: 'X 안 27자 / 280자' },
  { state: 'fixed', k: '뺀 문구 1개', t: "'야르한 가격' — 감탄사를 꾸미는 말로 써서 어색해 뺐어요" },
  { state: 'ok', k: '출처', t: '3건 · 가장 최근 2026-08-09' }
];
function _wa(w) { var c = String(w).charCodeAt(String(w).length - 1); return c >= 0xAC00 && c <= 0xD7A3 && (c - 0xAC00) % 28 ? '과' : '와'; }

// same scoring as the canvas version; only the sentences are rewritten in plain words
function judge(m, brand, leadDays) {
  var d7 = pct(m.w, 1), life = lifespan(m);
  var tScore = { emerging: 55, rising: 95, peak: (d7 !== null && d7 < 0) ? 60 : 85, steady: 70, declining: 15 }[m.stage];
  var ba = brandAges(brand), ma = ageSet(m.ages);
  var inter = ma.filter(function (a) { return ba.indexOf(a) >= 0; }).length;
  var aScore = ma.length ? Math.round(Math.max(20, 100 * inter / Math.min(ba.length, ma.length))) : 20;
  var fits = m.fits || [];
  var fScore = fits.indexOf(brand.cat) >= 0 ? 100 : (fits.indexOf('any') >= 0 ? 70 : 30);
  var score = Math.round(tScore * 0.4 + aScore * 0.35 + fScore * 0.25);
  var voiceOk = (brand.voices || []).indexOf(m.voice) >= 0;
  var why = [], v;
  if (m.safety === 'avoid') { v = 'no'; why.push(m.note || '공개 글에 쓰면 안 되는 말이에요'); }
  else if (!voiceOk && m.safety === 'caution') { v = 'no'; why.push((m.note || '말이 거칠어요') + ' — 우리 말투(' + brand.tone + ')와 안 맞아요'); }
  else if (m.stage === 'declining') { v = 'late'; why.push('12주 새 관심도가 ' + m.w[0] + '에서 ' + m.w[11] + '로 줄었어요. 지금 쓰면 늦어 보여요'); }
  else if (m.safety === 'caution') { v = 'care'; why.push(m.note || '쓰기 전에 문맥을 확인하세요'); }
  else if (!voiceOk) { v = 'care'; why.push('우리 말투(' + brand.tone + ')와 조금 달라요'); }
  else if (life.days !== null && life.days < leadDays) { v = 'care'; why.push('올리기까지 ' + leadLabel(leadDays) + ' 걸리면 그사이 식을 수 있어요. 가볍게 빨리 가야 해요'); }
  else if (m.stage === 'emerging') { v = 'watch'; why.push('막 나온 밈이라 아직 확실하지 않아요'); }
  else if (fScore === 30) { v = 'care'; why.push(brand.kind + _wa(brand.kind) + '는 잘 안 어울려요'); }
  else if (score >= 70) { v = 'go'; }
  else { v = 'care'; why.push('주로 쓰는 나이대가 우리 타깃과 조금 달라요'); }
  if (m.tip) why.push(m.tip);
  if (v === 'no') score = Math.min(score, 20); else if (v === 'late') score = Math.min(score, 40); else if (v === 'care') score = Math.min(score, 69);
  var plus = [];
  if (m.stage === 'rising') plus.push('아직 오르는 중이에요');
  if (m.stage === 'peak' && tScore >= 85) plus.push('지금 가장 많이 보여요');
  if (m.stage === 'steady') plus.push('오래 가는 말이에요');
  if (aScore >= 100) plus.push('우리 타깃 나이대가 써요');
  else if (aScore >= 50) plus.push('우리 타깃과 나이대가 일부 겹쳐요');
  if (fScore === 100) plus.push(FIT_LABEL[brand.cat] + '에 잘 어울려요');
  return { v: v, label: VERDICT[v].label, score: score, timing: tScore, target: aScore, fit: fScore, life: life, why: why, plus: plus };
}
function alertFor(m) {
  var d7 = pct(m.w, 1), d4 = pct(m.w, 4);
  if (m.stage === 'declining') return { kind: 'down', text: '12주 새 ' + m.w[0] + ' → ' + m.w[11] + '. 쓰고 있다면 다른 밈으로 바꿀 때예요' };
  if (m.stage === 'peak' && d7 !== null && d7 < 0) return { kind: 'turn', text: '지난주보다 ' + fmtPct(d7) + '. 최고점을 지났을 수 있어요' };
  if (d7 !== null && d7 >= 30) return { kind: 'up', text: '지난주보다 ' + fmtPct(d7) + ' 올랐어요. 먼저 쓰기 좋은 때예요' };
  if (m.stage === 'peak') return { kind: 'peak', text: '지금 가장 많이 보여요. 이번 주에 올리는 게 좋아요' };
  return { kind: 'flat', text: '4주 동안 ' + fmtPct(d4) + '. 큰 변화는 없어요' };
}
// ===== end copy =====
DOSSIER.rule = "아무 말 뒤에 '삐'를 붙여 '삐에로'처럼 부르는 말놀이";
DOSSIER.nuance = "직업을 놀리는 게 아니라 'OO삐'로 부르는 말놀이 자체가 재미예요. 실제 삐에로로 일하는 분들 앞에서는 조심하세요.";
DOSSIER.goodEx.why = "'OO삐' 규칙 그대로라 밈을 아는 사람에게 바로 통해요";
DOSSIER.badEx.why = "'OO삐'가 아니라 직업을 빗댄 말이라 밈이 아니라 놀림으로 읽혀요";
DOSSIER.safety[0].t = '직업을 놀리는 맥락이면 문제 — 말놀이로만 쓰기';
