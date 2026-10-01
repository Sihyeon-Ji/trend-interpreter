// ===== page: 콘텐츠 스튜디오 (4-step flow) =====
var POST = { 3: '9월 17일 (목)', 14: '9월 28일 (월)', 28: '10월 12일 (월)' };
var POST_SHORT = { 3: '9/17', 14: '9/28', 28: '10/12' };
var STEP_DEFS = ['무엇을 알리나요', '기획 방향 고르기', '제작 키트', '점검·공유'];

function studioBrand() { var b = clone(brand()); if (S.studio.cat && S.studio.cat !== b.cat) { b.cat = S.studio.cat; b.kind = CAT_OPTIONS.filter(function (c) { return c.id === S.studio.cat; })[0].label; } return b; }
function studioProduct() { return (S.studio.product || '').trim() || brand().name; }
function studioConcepts() {
  var b = studioBrand(), p = studioProduct(), pinned = S.studio.pinned;
  var list;
  if (b.id === 'latte' && !S.studio.product && b.cat === 'food') {
    list = STUDIO.concepts.map(function (c) { return { id: c.id, memeId: c.memeId, title: c.title, format: c.format, hook: c.hook, effort: c.effort, effortNote: c.effortNote, idea: c.idea, authored: true }; });
  } else {
    list = MEMES.KR.filter(function (m) { return CONCEPT_LIB[m.id]; }).map(function (m) { return { m: m, j: J(m, b) }; })
      .filter(function (x) { return ['go', 'watch'].indexOf(x.j.v) >= 0; })
      .sort(function (a, c) { return c.j.score - a.j.score; }).slice(0, 3)
      .map(function (x) { var t = CONCEPT_LIB[x.m.id]; return fillConcept(x.m.id, t, p); });
  }
  if (pinned && BY_ID[pinned] && !list.some(function (c) { return c.memeId === pinned; })) {
    var t = CONCEPT_LIB[pinned] || { title: '"' + BY_ID[pinned].name + '"로 ' + '{p} 알리기', format: '15초 쇼츠', hook: '밈이 쓰이는 상황을 첫 자막으로', effort: '보통', effortNote: '구성에 따라 달라요', idea: BY_ID[pinned].gloss + ' — 이 뜻을 {p}와 연결해요.' };
    list = [fillConcept(pinned, t, p)].concat(list).slice(0, 3);
  }
  return list.map(function (c, i) { c.letter = 'ABC'[i]; c.m = BY_ID[c.memeId]; c.j = judge(c.m, b, S.lead); return c; });
}
function fillConcept(id, t, p) {
  var f = function (s) { return String(s).split('{p}').join(p); };
  return { id: id, memeId: id, title: f(t.title), format: t.format, hook: f(t.hook), effort: t.effort, effortNote: t.effortNote, idea: f(t.idea) };
}
function studioExcluded(concepts) {
  var b = studioBrand(), used = concepts.map(function (c) { return c.memeId; });
  var cands = MEMES.KR.map(function (m) { return { m: m, j: judge(m, b, S.lead) }; })
    .filter(function (x) { return used.indexOf(x.m.id) < 0 && (x.j.v === 'care' || x.j.v === 'late' || x.j.v === 'no'); })
    .sort(function (a, c) { return c.m.w[11] - a.m.w[11]; }).slice(0, 3);
  return cands.map(function (x) {
    var fix = x.j.v === 'care' && x.j.life.days !== null && x.j.life.days < S.lead ? '빨리 가려면: 기존 영상에 "' + x.m.name + '" 자막만 얹어 3일 안에 올리기' : '';
    return { m: x.m, j: x.j, fix: fix };
  });
}
function selConcept(concepts) { return concepts.filter(function (c) { return c.id === S.studio.sel; })[0] || concepts[0]; }
function hasKit(c) { return c && c.memeId === 'yar' && brand().id === 'latte' && !S.studio.product && studioBrand().cat === 'food'; }

function stepsHtml() {
  var st = S.studio;
  return '<ol class="steps" aria-label="진행 단계">' + STEP_DEFS.map(function (l, i) {
    var n = i + 1, done = n < st.step, now = n === st.step, reach = n <= (st.ran ? 4 : 1);
    return '<li class="' + (done ? 'done' : now ? 'now' : '') + '"><button ' + (reach && !now ? 'data-act="studioStep" data-arg="' + n + '"' : 'disabled') + (now ? ' aria-current="step"' : '') + '><span class="dot">' + n + '</span>' + l + '</button>' + (n < 4 ? '<span class="sep"></span>' : '') + '</li>';
  }).join('') + '</ol>';
}

function studioStep1() {
  var st = S.studio, b = brand();
  var modes = '<div class="tabs" role="tablist" aria-label="입력 방식">' + MODES.map(function (m) { return '<button role="tab" aria-selected="' + (m.id === st.mode) + '" data-act="studioMode" data-arg="' + m.id + '">' + m.label + '</button>'; }).join('') + '</div>';
  var fields = '';
  if (st.mode === 'product') {
    fields = '<label class="field" for="s-prod">상품명<input class="input" id="s-prod" data-in="studioProduct" value="' + esc(st.product) + '" placeholder="' + esc(b.name) + '"></label>' +
      '<label class="field" for="s-cat"><span>분야 <span class="hint">· 브랜드와 다른 상품이면 바꿔 주세요</span></span><select class="select" id="s-cat" data-ch="studioCat">' + CAT_OPTIONS.map(function (c) { return '<option value="' + c.id + '"' + (c.id === (st.cat || b.cat) ? ' selected' : '') + '>' + c.label + '</option>'; }).join('') + '</select></label>' +
      '<label class="field" for="s-one"><span>한 줄 소개 <span class="hint">· 이것만 써도 AI가 나머지를 채워요</span></span><textarea class="textarea" id="s-one" rows="2" data-in="studioOne" placeholder="예: 더운 오후, 한숨 돌리게 해 주는 달콤한 라떼">' + esc(st.oneLiner || (b.id === 'latte' ? '더운 오후, 한숨 돌리게 해 주는 달콤한 라떼' : '')) + '</textarea></label>';
  } else if (st.mode === 'shorts') {
    fields = '<label class="field" for="s-url">쇼츠 링크<input class="input" id="s-url" type="url" data-in="studioUrl" value="' + esc(st.shortsUrl) + '"></label>' +
      '<div class="field">이 영상은<div class="chips">' + [['mine', '내 영상 고치기'], ['ref', '잘된 영상 따라 하기']].map(function (k) { return '<button class="chip" aria-pressed="' + (st.shortsKind === k[0]) + '" data-act="studioKind" data-arg="' + k[0] + '">' + k[1] + '</button>'; }).join('') + '</div></div>' +
      '<label class="field" for="s-prod2">우리가 알릴 것<input class="input" id="s-prod2" data-in="studioProduct" value="' + esc(st.product) + '" placeholder="' + esc(b.name) + '"></label>' +
      '<p class="note">AI가 영상의 화면 글자·말·소리를 직접 보고, 쓰인 밈과 뜬 이유를 찾아요. 그 구조를 우리 상품으로 옮겨요.</p>';
  } else {
    fields = '<label class="drop' + (st.photo ? ' has' : '') + '" for="s-photo">' + icon('photo', 26) + '<b style="font-size:13.5px">' + (st.photo ? esc(st.photo) : '상품 사진을 고르거나 끌어다 놓으세요') + '</b><span class="note">JPG, PNG, WEBP · 5MB까지 · 사진은 분석에만 쓰고 저장하지 않아요</span>' +
      '<input id="s-photo" type="file" accept="image/jpeg,image/png,image/webp" data-ch="studioPhoto" class="sr"></label>' +
      '<label class="field" for="s-prod3">상품명<input class="input" id="s-prod3" data-in="studioProduct" value="' + esc(st.product) + '" placeholder="' + esc(b.name) + '"></label>';
  }
  var goal = '<div class="field">캠페인 목표<div class="chips">' + STUDIO.goals.map(function (g) { return '<button class="chip" aria-pressed="' + (g === st.goal) + '" data-act="studioGoal" data-arg="' + esc(g) + '">' + g + '</button>'; }).join('') + '</div></div>';
  var post = '<div class="field"><span>게시 예정일 <span class="hint">· 그때까지 밈이 살아 있는지 봐요</span></span><div class="row">' + leadSeg() + '<b>' + POST[S.lead] + '</b></div></div>';
  var ch = '<div class="field">채널<div class="chips">' + STUDIO.channels.map(function (c) { return '<button class="chip" aria-pressed="' + !!st.channels[c] + '" data-act="studioCh" data-arg="' + esc(c) + '">' + c + '</button>'; }).join('') + '</div></div>';
  var left = '<section class="card stack" aria-labelledby="in-h" style="gap:16px"><div class="row" style="justify-content:space-between"><h2 id="in-h" class="h3">무엇을 알리나요</h2><span class="note">브랜드 ' + esc(b.name) + ' · <a href="#settings">바꾸기</a></span></div>' + modes + fields + goal + post + ch + '</section>';
  var sb = studioBrand(); var preview = MEMES.KR.map(function (m) { return { m: m, j: judge(m, sb, S.lead) }; }).filter(function (x) { return x.j.v === 'go'; }).sort(function (a, c) { return c.j.score - a.j.score; }).slice(0, 4);
  var right = '<aside class="stack"><section class="card stack"><h2 class="h3">이렇게 진행돼요</h2>' +
    ['AI가 상품 설명·사진·영상을 읽어요', '모아 둔 밈 중에서 지금 뜨고, 우리 타깃이 쓰고, 안전한 것만 골라요', '고른 방향으로 대본·카피·썸네일을 만들고, 밈을 제대로 썼는지·쓰면 안 되는 말이 없는지 점검해요'].map(function (t, i) { return '<div class="row" style="align-items:flex-start;flex-wrap:nowrap"><span class="pin">' + (i + 1) + '</span><span class="sub" style="font-size:13px">' + t + '</span></div>'; }).join('') +
    '<p class="note">입력한 사진과 영상은 요청 처리에만 쓰고 저장하지 않아요.</p></section>' +
    '<section class="card stack"><div class="row" style="justify-content:space-between"><h2 class="h3">지금 ' + esc(studioProduct()) + '에 맞을 밈</h2><a href="#radar" style="font-size:12.5px">레이더 보기</a></div>' +
    preview.map(function (x) { return '<div class="row" style="justify-content:space-between;flex-wrap:nowrap;border-top:1px solid var(--line);padding-top:10px"><span style="min-width:0">' + memeLink(x.m, 'lib-name') + ' <span class="note">' + esc(x.j.life.label) + '</span></span>' + badge(x.j.v) + '</div>'; }).join('') +
    (st.pinned && BY_ID[st.pinned] ? '<p class="note" style="color:var(--ink)">고른 밈 <b>' + esc(BY_ID[st.pinned].name) + '</b>을 첫 번째 안에 넣어 드려요. <button class="btn sm" data-act="studioUnpin">빼기</button></p>' : '') + '</section></aside>';
  return '<div class="studio-1">' + left + right + '</div>' +
    '<div class="step-nav"><span class="note">매칭은 몇 초면 끝나요 · 예시 데이터로 동작해요</span><button class="btn lg primary" data-act="studioRun">밈 매칭 시작 ' + icon('arrow', 14) + '</button></div>';
}

function studioLoading() {
  var st = S.studio;
  return '<section class="card"><div class="loader" role="status"><b style="font-size:17px">밈을 맞춰 보는 중이에요</b><div class="ls">' + ['상품 읽기', '맞는 밈 고르기', '기획안 쓰기'].map(function (t, i) {
    return '<span class="' + (i < st.loadStep ? 'done' : i === st.loadStep ? 'now' : '') + '">' + (i < st.loadStep ? '완료 · ' : '') + t + '</span>';
  }).join('') + '</div><span class="note">' + esc(studioProduct()) + ' · ' + esc(brand().name) + ' 기준 · 게시일 ' + POST_SHORT[S.lead] + '</span></div></section>';
}

function studioStep2() {
  var st = S.studio, concepts = studioConcepts(), sel = selConcept(concepts), excl = studioExcluded(concepts);
  var read;
  if (st.mode === 'shorts') {
    var sh = STUDIO.shorts;
    var KIND = { issue: ['고칠 곳', 'var(--red-soft)', 'var(--red-ink)', 'var(--red)'], keep: ['살릴 곳', 'var(--sunk)', 'var(--ink-2)', 'var(--line-2)'], meme: ['밈 넣을 곳', 'var(--hl)', 'var(--on-hl)', 'var(--ink)'] };
    var sec = function (s) { var p = s.split(':'); return +p[0] * 60 + +p[1]; };
    read = '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">쇼츠 분해 — 이 영상은 왜 떴나</h2><span class="note">AI가 영상을 직접 봤어요 · 예시</span></div>' +
      '<div class="grid-2"><div class="stack" style="gap:8px;font-size:13.5px"><span><span class="muted">요약 · </span>' + esc(sh.summary) + '</span><span><span class="muted">뜬 이유 · </span>' + esc(sh.why) + '</span><span><span class="muted">보는 사람 · </span>' + esc(sh.target) + ' <span class="muted">· 위험 신호 </span>' + esc(sh.risk) + '</span></div>' +
      '<div class="stack" style="gap:8px"><span class="note" style="font-weight:600">영상에서 찾은 밈</span>' + sh.memes.map(function (m) { return '<div class="axis" style="grid-template-columns:76px minmax(0,1fr) 40px"><b>' + esc(m.name) + '</b><span class="bar"><i style="width:' + m.conf + '%"></i></span><span class="mono" style="text-align:right">' + m.conf + '%</span></div>'; }).join('') + '<span class="note">확신도 · 화면 자막 "' + esc(sh.memes[0].quote) + '"에서</span></div></div>' +
      '<div class="stack" style="gap:6px"><span class="note" style="font-weight:600">장면별로 고칠 곳 · 0:00–' + SHORTS.length + '</span><div class="row" style="gap:3px;flex-wrap:nowrap;overflow-x:auto">' + SHORTS.timeline.map(function (t) {
        var k = KIND[t.kind];
        return '<div style="flex:' + (sec(t.to) - sec(t.from)) + ' 0 150px;display:flex;flex-direction:column;gap:6px;padding:10px;border-radius:8px;background:var(--surface-2);border-top:3px solid ' + k[3] + '"><span class="mono" style="font-size:11px;color:var(--ink-2)">' + t.from + '–' + t.to + ' · ' + esc(t.what) + '</span><span class="badge" style="align-self:flex-start;background:' + k[1] + ';color:' + k[2] + '">' + k[0] + '</span><span style="font-size:12.5px;line-height:1.45">' + esc(t.tip) + '</span></div>';
      }).join('') + '</div></div><b style="font-size:13px">' + esc(sh.remake) + '</b></section>';
  } else {
    var r = STUDIO.read, p = studioProduct(), isLatte = brand().id === 'latte' && !st.product && studioBrand().cat === 'food';
    read = '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">AI가 이렇게 이해했어요</h2><span class="note">AI 분석 · 예시 · 틀리면 눌러서 고치세요</span></div>' +
      facts([['상품', esc(p) + ' · ' + esc(isLatte ? r.category : studioBrand().kind)], ['느낌', (isLatte ? r.feelings.join(' · ') : '분석 예시 없음')], ['장면', esc(isLatte ? r.scene : '—')], ['강조', esc(isLatte ? r.values.join(' · ') : '—')], ['타깃', esc(brand().ages.join('·')) + ' · ' + esc(brand().tone)]]) +
      (st.mode === 'image' && st.photo ? '<p class="note">사진 "' + esc(st.photo) + '"에서 색·분위기를 함께 읽었어요 (예시).</p>' : '') + '</section>';
  }
  var cards = concepts.map(function (c) {
    var on = c.id === sel.id, late = c.j.life.days !== null && c.j.life.days < S.lead;
    return '<article class="concept' + (on ? ' on' : '') + '"><div class="row" style="justify-content:space-between"><b class="mono">' + c.letter + '안</b>' + badge(c.j.v) + '</div>' +
      '<div class="stack" style="gap:3px;min-height:60px"><b style="font-size:16px;line-height:1.4">' + esc(c.title) + '</b><span class="note">' + esc(c.format) + '</span></div>' +
      '<p class="sub" style="font-size:12.5px;min-height:56px">' + esc(c.idea) + '</p>' +
      '<dl><dt>밈</dt><dd>' + memeLink(c.m, 'disp') + '</dd><dt>첫 2초</dt><dd>' + esc(c.hook) + '</dd><dt>쓸 수 있는 기간</dt><dd style="font-weight:600;color:' + (late ? 'var(--amber-ink)' : 'var(--ink)') + '">' + esc(c.j.life.label) + (late ? ' — 게시일 전에 꺾일 수 있어요' : c.j.life.days === 999 ? '' : ' — 게시일까지 괜찮아요') + '</dd>' +
      '<dt>제작</dt><dd>' + esc(c.effort) + ' · ' + esc(c.effortNote) + '</dd><dt>어울림</dt><dd class="mono">' + c.j.score + '점</dd></dl>' +
      '<button class="btn ' + (on ? 'primary' : '') + '" data-act="studioSel" data-arg="' + c.id + '" aria-pressed="' + on + '">' + (on ? '고른 안' : '이 안 고르기') + '</button></article>';
  }).join('');
  var exHtml = excl.map(function (x) { return '<div class="excl"><b' + lang(x.m) + '>' + memeLink(x.m) + '</b><span>' + badge(x.j.v) + '</span><span class="sub">' + esc(x.j.why[0] || '') + (x.fix ? '<br><b style="color:var(--blue-ink)">' + esc(x.fix) + '</b>' : '') + '</span></div>'; }).join('');
  return read + '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">기획 방향 ' + concepts.length + '안 — 하나를 고르세요</h2><span class="note">게시일 ' + POST_SHORT[S.lead] + '에 올린다고 보고 골랐어요</span></div>' +
    (concepts.length ? '<div class="concepts">' + cards + '</div>' : emptyState('지금 쓸 만한 밈이 없어요', '제작 기간을 줄이거나 우리 브랜드 설정의 타깃·말투를 바꿔 보세요.')) +
    (exHtml ? '<div class="stack" style="gap:0"><b style="font-size:12.5px;margin-bottom:4px">이번엔 뺀 밈과 이유</b>' + exHtml + '</div>' : '') + '</section>' +
    '<div class="step-nav"><button class="btn" data-act="studioStep" data-arg="1">' + icon('back', 14) + ' 입력 고치기</button><button class="btn lg primary" data-act="studioStep" data-arg="3"' + (concepts.length ? '' : ' disabled') + '>' + (sel ? sel.letter + '안으로 제작 키트 만들기 ' : '제작 키트 만들기 ') + icon('arrow', 14) + '</button></div>';
}

function kitHtml(kit, concept) {
  var st = S.studio;
  var frames = kit.scenes.map(function (s, i) {
    var none = s.caption.indexOf('(') === 0;
    return '<div class="stack" style="gap:8px"><div class="frame' + (s.meme ? ' meme' : '') + '"><span class="fn">#' + (i + 1) + ' · ' + s.t + '</span><span class="fv">장면 · ' + esc(s.visual) + '</span><span class="cap' + (s.meme ? ' big' : none ? ' none' : '') + '">' + esc(s.caption) + '</span></div>' +
      '<dl class="frame-meta"><dt>소리</dt><dd>' + esc(s.sound) + '</dd><dt>촬영</dt><dd>' + esc(s.shot) + '</dd></dl></div>';
  }).join('');
  var ruler = '<div class="ruler">' + kit.scenes.map(function (s) { return '<div class="' + (s.meme ? 'meme' : '') + '" style="flex-grow:' + (s.e - s.s) + '">' + s.t + (s.meme ? ' · 밈 포인트' : '') + '</div>'; }).join('') + '</div>';
  var copies = kit.copies.map(function (c, i) {
    var full = c.text + (c.tags ? '\n' + c.tags : '');
    return '<div class="copy"><div class="row" style="justify-content:space-between"><b class="note" style="color:var(--ink-2)">' + c.ch + '</b><span class="row" style="gap:8px"><span class="mono note">' + full.length + ' / ' + c.limit + '자</span><button class="btn sm" data-act="copy" data-text="' + esc(full) + '" data-ok="' + c.ch + ' 카피를 복사했어요" aria-label="' + c.ch + ' 카피 복사">' + icon('copy', 12) + ' 복사</button></span></div>' +
      '<span style="font-size:14px">' + esc(c.text) + '</span>' + (c.tags ? '<span style="font-size:13px;color:var(--blue-ink)">' + esc(c.tags) + '</span>' : '') + '</div>';
  }).join('');
  var th = kit.thumb;
  var thumb = '<div class="stack" style="gap:10px"><b style="font-size:13px">썸네일</b><div class="thumb"><div style="position:absolute;left:6%;bottom:17%;width:32%;height:42%;border-radius:8px;background:#6B3F22;display:grid;place-items:center;color:#F4E9DA;font-size:11px">제품</div>' +
    '<div style="position:absolute;left:42%;top:42%;right:6%;height:34%;border-radius:8px;border:1.5px dashed #6B3F22;display:grid;place-items:center;text-align:center;font-size:11px;line-height:1.4;color:#6B3F22;padding:6px">' + esc(th.subject) + '</div>' +
    '<span class="disp" style="position:absolute;right:5%;top:6%;font-size:clamp(28px,4vw,44px);line-height:1;color:#141412;background:#FFE14D;padding:4px 8px;border-radius:4px">' + esc(th.headline) + '</span>' +
    '<span style="position:absolute;left:6%;bottom:4%;font-size:12px;font-weight:700;color:#6B3F22">' + esc(studioProduct()) + '</span></div>' +
    '<span class="sub" style="font-size:12px">' + esc(th.layout) + '</span>' + th.colors.map(function (c) { return '<span class="row" style="gap:8px;font-size:12px"><span style="width:16px;height:16px;border-radius:4px;border:1px solid var(--line-2);background:' + c.hex + '"></span>' + c.name + ' <span class="mono muted">' + c.hex + '</span></span>'; }).join('') + '</div>';
  var prep = '<div class="stack" style="gap:10px"><b style="font-size:13px">촬영 준비물</b>' + kit.prep.map(function (p, i) {
    return '<label class="row" style="flex-wrap:nowrap;align-items:flex-start;gap:10px;font-size:13px;cursor:pointer;min-height:30px"><input type="checkbox" id="prep-' + i + '" data-ch="studioPrep" data-arg="' + i + '"' + (st.prep[i] ? ' checked' : '') + ' style="width:18px;height:18px;margin:1px 0 0;accent-color:var(--ink);flex-shrink:0"><span style="' + (st.prep[i] ? 'color:var(--ink-3);text-decoration:line-through' : '') + '">' + esc(p) + '</span></label>';
  }).join('') + '<div class="vbox go" style="margin-top:4px"><b style="font-size:12px">게시 타이밍</b><span style="font-size:13px;line-height:1.5">' + esc(S.lead > 21 ? '게시일(' + POST_SHORT[S.lead] + ')엔 야르가 정점을 지났을 수 있어요 — 제작을 2주 안으로 줄이거나 B안을 고르세요' : POST_SHORT[S.lead] + ' 오후 3시 전후 — 장면 속 시간과 맞추면 공감이 커요') + '</span></div></div>';
  return '<div class="vbox" style="background:var(--surface-2);border-color:var(--line);color:var(--ink);flex-direction:row;gap:14px;flex-wrap:wrap"><b style="font-size:12px;color:var(--ink-2);min-width:120px">첫 2초 훅</b><span style="font-size:14px"><b>' + esc(concept.hook) + '</b> — ' + esc(kit.hookWhy) + '</span></div>' +
    '<div class="stack" style="gap:6px"><div class="row" style="justify-content:space-between"><span class="note">스토리보드 · 15초 세로 영상</span><span class="note">' + esc(kit.captionStyle) + '</span></div>' + ruler + '</div>' +
    '<div class="frames">' + frames + '</div><div class="kit-row" style="border-top:1px solid var(--line);padding-top:16px"><div class="stack" style="gap:10px"><b style="font-size:13px">채널별 카피</b>' + copies + '</div>' + thumb + prep + '</div>';
}

function studioStep3() {
  var st = S.studio, concepts = studioConcepts(), c = selConcept(concepts);
  var body;
  if (hasKit(c) || st.showExample) {
    body = (hasKit(c) ? '' : '<p class="vbox care" style="margin:0">예시: 아이스 흑당 라떼 × 야르 키트를 보여 드리고 있어요. 고른 안의 키트는 실제 서비스에서 AI가 만들어요.</p>') + kitHtml(STUDIO.kit.yar, hasKit(c) ? c : STUDIO.concepts[0]);
  } else {
    body = '<div class="stack" style="align-items:center;text-align:center;padding:40px 16px;border:1px dashed var(--line-2);border-radius:12px;gap:10px"><b style="font-size:15px">' + c.letter + '안 "' + esc(c.title) + '" 키트는 실제 서비스에서 만들어져요</b>' +
      '<span class="sub" style="font-size:13px;max-width:560px">AI가 이 안으로 대본·카피·썸네일을 한 번에 쓰고, 밈 뜻과 쓰면 안 되는 말을 점검해요. 예시 데이터에는 아이스 흑당 라떼 × 야르 키트만 들어 있어요.</span>' +
      '<button class="btn" data-act="studioExample">예시 키트 보기</button></div>';
  }
  return '<section class="card stack" style="gap:16px"><div class="card-head" style="margin:0"><h2 class="h3">제작 키트 — ' + c.letter + '안 ' + esc(c.title) + '</h2><span class="note">AI가 만들고 자동으로 점검했어요 · 예시</span></div>' + body + '</section>' +
    '<div class="step-nav"><button class="btn" data-act="studioStep" data-arg="2">' + icon('back', 14) + ' 방향 다시 고르기</button><button class="btn lg primary" data-act="studioStep" data-arg="4">점검하고 공유하기 ' + icon('arrow', 14) + '</button></div>';
}

function studioStep4() {
  var st = S.studio, concepts = studioConcepts(), c = selConcept(concepts), b = brand();
  var kitOk = hasKit(c) || st.showExample;
  var checks = kitOk ? STUDIO.kit.yar.checks : [
    { state: c.j.v === 'go' ? 'ok' : 'fixed', k: '밈 상태', t: c.m.name + ' · ' + c.j.label + ' (어울림 ' + c.j.score + '점)' },
    { state: 'ok', k: '쓰면 안 되는 말', t: '초안이 나오면 점검해요' }, { state: 'ok', k: '글자 수', t: '초안이 나오면 점검해요' }];
  var chk = '<div class="checks">' + checks.map(function (x) { return '<div class="chk' + (x.state === 'fixed' ? ' fixed' : '') + '"><b class="row" style="gap:6px;font-size:12.5px">' + icon(x.state === 'ok' ? 'ok' : 'warn', 14) + esc(x.k) + '</b><span>' + esc(x.t) + '</span></div>'; }).join('') + '</div>';
  var summary = [b.name + ' 기획안 — ' + c.letter + '안 ' + c.title, '밈: ' + c.m.name + ' (' + c.j.label + ', 어울림 ' + c.j.score + '점, 쓸 수 있는 기간 ' + c.j.life.label + ')', '게시 예정: ' + POST[S.lead], '형식: ' + c.format + ' · 첫 2초: ' + c.hook, '트렌드 통역 · ' + AS_OF + ' · 예시 데이터'].join('\n');
  var srcs = c.memeId === 'yar' ? DETAIL_YAR.sources : c.memeId === 'pierrot' ? DOSSIER.path.map(function (p) { return { kind: p.kind, domain: p.domain || '커뮤니티', title: p.title, date: '2026-' + p.date.replace('/', '-') }; }) : [];
  var doc = '<article class="onepager"><div class="row" style="justify-content:space-between"><span class="note">기획안 미리보기 · 한 장</span><span class="tag-ex">예시 데이터</span></div>' +
    '<h3 style="font-size:20px">' + esc(c.title) + '</h3>' + facts([['브랜드', esc(b.name)], ['밈', esc(c.m.name)], ['써도 될까', badge(c.j.v)], ['게시 예정', POST[S.lead]]]) + '' +
    '<p class="sub" style="font-size:13.5px"><b style="color:var(--ink)">왜 이 밈인가 · </b>' + esc(reasonsOf(c.j).join(' / ')) + '</p><p class="sub" style="font-size:13.5px"><b style="color:var(--ink)">아이디어 · </b>' + esc(c.idea) + '</p>' +
    (srcs.length ? '<div class="stack" style="gap:4px"><b style="font-size:12.5px">출처</b>' + srcs.map(function (s) { return '<span class="note">' + esc(s.kind) + ' · ' + esc(s.domain) + ' · ' + esc(s.title) + ' · ' + esc(s.date) + '</span>'; }).join('') + '</div>' : '') + '</article>';
  return '<section class="card stack" style="gap:14px"><div class="card-head" style="margin:0"><h2 class="h3">올리기 전 자동 점검</h2><span class="note">밈 뜻과 주의할 점에 맞춰 확인했어요</span></div>' + chk + '<p class="note">AI 제작안은 초안이에요. 게시 전에 한 번 더 확인해 주세요.</p></section>' +
    '<div class="grid-2" style="align-items:start">' + doc + '<section class="card stack"><h2 class="h3">공유하고 승인받기</h2>' +
    '<button class="btn lg ' + (st.saved ? 'on' : 'primary') + '" data-act="studioSave">' + (st.saved ? '내 기획안에 저장됨 · 보러 가기' : '내 기획안에 저장') + '</button>' +
    '<button class="btn" data-act="studioApprove"' + (st.approved ? ' disabled' : '') + '>' + (st.approved ? '팀장에게 승인 요청을 보냈어요' : '팀장에게 승인 요청') + '</button>' +
    '<button class="btn" data-act="copy" data-text="' + esc(summary) + '" data-ok="기획안 요약을 복사했어요">' + icon('copy', 14) + ' 요약 복사 (메신저에 붙여 넣기)</button>' +
    '<p class="note">PDF·슬라이드 내보내기는 실제 서비스에서 제공돼요. 이 예시에서는 파일을 만들지 않아요.</p></section></div>' +
    '<div class="step-nav"><button class="btn" data-act="studioStep" data-arg="3">' + icon('back', 14) + ' 제작 키트</button><button class="btn" data-act="studioNew">새 기획 시작</button></div>';
}

PAGES.studio = function () {
  var st = S.studio;
  var body = st.phase === 'loading' ? studioLoading() : st.step === 1 ? studioStep1() : st.step === 2 ? studioStep2() : st.step === 3 ? studioStep3() : studioStep4();
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">콘텐츠 스튜디오 · ' + STEP_DEFS[st.step - 1] + '</span><h1 class="h1">알릴 것을 넣으면, <span class="hl">지금 뜨는 밈</span>으로 만드는 법까지</h1></div></header>' +
    stepsHtml() + body;
};

var studioTimers = [];
ACT.studioRun = function () {
  var st = S.studio;
  studioTimers.forEach(clearTimeout); studioTimers = [];
  st.phase = 'loading'; st.loadStep = 0; render();
  studioTimers.push(setTimeout(function () { st.loadStep = 1; render(); }, 500));
  studioTimers.push(setTimeout(function () { st.loadStep = 2; render(); }, 1000));
  studioTimers.push(setTimeout(function () { st.phase = 'idle'; st.ran = true; st.step = 2; st.sel = null; st.saved = false; st.approved = false; st.showExample = false; render(); window.scrollTo(0, 0); }, 1500));
};
ACT.studioStep = function (n) { S.studio.step = +n; if (+n === 3 && !S.studio.sel) { var c = studioConcepts()[0]; S.studio.sel = c && c.id; } render(); window.scrollTo(0, 0); };
ACT.studioMode = function (m) { S.studio.mode = m; render(); };
ACT.studioKind = function (k) { S.studio.shortsKind = k; render(); };
ACT.studioGoal = function (g) { S.studio.goal = g; render(); };
ACT.studioCh = function (c) { S.studio.channels[c] = !S.studio.channels[c]; render(); };
ACT.studioSel = function (id) { S.studio.sel = id; S.studio.showExample = false; S.studio.saved = false; render(); };
ACT.studioUnpin = function () { S.studio.pinned = null; render(); };
ACT.studioExample = function () { S.studio.showExample = true; render(); };
ACT.studioNew = function () { S.studio = Object.assign(S.studio, { step: 1, ran: false, sel: null, pinned: null, product: '', oneLiner: '', saved: false, approved: false, showExample: false, prep: {} }); render(); window.scrollTo(0, 0); };
ACT.studioApprove = function () { S.studio.approved = true; var p = S.plans.filter(function (x) { return x.fromStudio; })[0]; if (p) p.status = '승인 대기'; persist(); toast('팀장에게 승인 요청을 보냈어요 (예시)'); render(); };
ACT.studioSave = function () {
  if (S.studio.saved) { go('plans'); return; }
  var c = selConcept(studioConcepts());
  S.plans.unshift({ id: 'p' + Date.now(), title: c.letter + '안 · ' + c.title, memeId: c.memeId, brandId: S.brandId, status: S.studio.approved ? '승인 대기' : '초안', due: POST_SHORT[S.lead], fromStudio: true });
  S.studio.saved = true; persist(); toast('내 기획안에 저장했어요'); render();
};
IN.studioProduct = function (v) { S.studio.product = v; render(); };
IN.studioCat = function (v) { S.studio.cat = v; render(); };
IN.studioOne = function (v) { S.studio.oneLiner = v; };
IN.studioUrl = function (v) { S.studio.shortsUrl = v; };
IN.studioPhoto = function (v, el) { var f = el.files && el.files[0]; if (!f) return; if (f.size > 5 * 1024 * 1024) { toast('5MB보다 큰 사진은 올릴 수 없어요'); return; } S.studio.photo = f.name; render(); };
IN.studioPrep = function (v, el) { S.studio.prep[el.getAttribute('data-arg')] = v; render(); };
// ===== end studio =====
