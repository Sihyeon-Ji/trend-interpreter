// ===== page: 트렌드 레이더 =====
var WORD_CLS = { go: 'w-go', watch: 'w-watch', care: 'w-care', late: 'w-late', no: 'w-no', up: 'w-up', peak: 'w-peak', steady: 'w-steady', down: 'w-down' };
var SW_COLOR = { go: 'var(--blue)', watch: 'var(--violet)', care: 'var(--amber)', late: 'var(--gray)', no: 'var(--red)', up: 'var(--blue)', peak: 'var(--pink)', steady: 'var(--ink-2)', down: 'var(--gray)' };

function radarData() {
  var R = S.radar, b = brand(), per = periodObj();
  var all = MEMES[R.region].map(function (m) {
    var j = J(m, b);
    return { m: m, j: j, p: pct(m.w, per.back), d7: pct(m.w, 1), group: R.colorBy === 'verdict' ? j.v : STAGE[m.stage].group };
  });
  var q = R.query.trim();
  var base = all.filter(function (x) { return (R.cat === 'all' || x.m.cat === R.cat) && (!q || x.m.name.toLowerCase().indexOf(q.toLowerCase()) >= 0 || (ALIASES[x.m.id] || []).some(function (a) { return a.indexOf(q) >= 0; })); });
  var shown = base.filter(function (x) { return !R.off[x.group]; });
  var ranked = all.slice().sort(function (a, c) { return V_ORDER.indexOf(a.j.v) - V_ORDER.indexOf(c.j.v) || c.j.score - a.j.score; });
  var byId = {}; all.forEach(function (x) { byId[x.m.id] = x; });
  var sel = R.sel && byId[R.sel] ? byId[R.sel] : ranked[0];
  return { all: all, base: base, shown: shown, ranked: ranked, byId: byId, sel: sel, per: per, b: b };
}

PAGES.radar = function () {
  var R = S.radar, D = radarData(), b = D.b;
  // ---- this week ----
  var gos = D.ranked.filter(function (x) { return x.j.v === 'go'; });
  var t1 = gos[0];
  var early = D.all.filter(function (x) { return (x.j.v === 'go' || x.j.v === 'watch') && (x.m.stage === 'rising' || x.m.stage === 'emerging') && x !== t1; })
    .sort(function (a, c) { return (c.d7 === null ? 999 : c.d7) - (a.d7 === null ? 999 : a.d7); })[0] || gos[1];
  var warn = D.all.filter(function (x) { return x.j.v === 'no' || x.j.v === 'late'; }).sort(function (a, c) { return c.m.w[11] - a.m.w[11]; })[0];
  var todos = [];
  if (t1) todos.push({ x: t1, kicker: '지금 올라타기', line: t1.j.plus.join(' · ') + '. 쓸 수 있는 기간 ' + t1.j.life.label + '.', meta: '어울림 ' + t1.j.score + '점 · 관심도 ' + t1.m.w[11] });
  if (early) todos.push({ x: early, kicker: '먼저 쓰면 좋은 밈', line: '지난주보다 ' + fmtPct(early.d7) + '. ' + (DIFF_HINT[early.m.diff] || ''), meta: '어울림 ' + early.j.score + '점 · ' + DIFF[early.m.diff] });
  if (warn) todos.push({ x: warn, kicker: '지금은 피하세요', line: '관심도 ' + warn.m.w[11] + '로 자주 보이지만, ' + (warn.j.why[0] || ''), meta: '다른 팀이 쓰려 하면 공유하세요', warn: true });
  var todoHtml = R.region === 'KR' ? todos.map(function (t, i) {
    var x = t.x;
    return '<article class="card todo' + (t.warn ? ' warn' : '') + (i === 0 ? ' lead' : '') + (x.m.id === D.sel.m.id ? ' sel' : '') + '">' +
      '<div class="todo-top"><span class="kicker' + (t.warn ? ' warn' : '') + '">' + t.kicker + '</span>' + badge(x.j.v) + '</div>' +
      '<button class="name" data-act="radarPick" data-arg="' + x.m.id + '"' + lang(x.m) + '>' + esc(x.m.name) + '</button>' +
      '<p class="todo-line">' + esc(t.line) + '</p>' +
      '<dl class="todo-stats">' +
        '<div><dt>' + (t.warn ? '관심도' : '어울림') + '</dt><dd class="big-num">' + (t.warn ? x.m.w[11] : x.j.score) + '</dd></div>' +
        '<div><dt>쓸 수 있는 기간</dt><dd>' + esc(t.warn ? '—' : x.j.life.label) + '</dd></div>' +
        '<div class="spark-cell" style="color:' + (t.warn ? 'var(--red)' : 'var(--blue)') + '"><dt>12주 흐름</dt><dd>' + spark(x.m.w, 96, 26) + '</dd></div>' +
      '</dl>' +
      '<div class="foot">' + (t.warn ? '<span class="note">' + esc(t.meta) + '</span><a class="btn sm" href="#meme-' + x.m.id + '">왜 안 되는지 보기</a>'
        : '<a class="btn sm ghost" href="#meme-' + x.m.id + '">근거 보기</a><button class="btn sm primary" data-act="planWith" data-arg="' + x.m.id + '">이 밈으로 기획하기 ' + icon('arrow', 12) + '</button>') + '</div></article>';
  }).join('') : '';

  // ---- filters ----
  var activeF = [];
  if (R.cat !== 'all') activeF.push('<button class="chip" aria-pressed="true" data-act="radarCat" data-arg="all">' + CAT_LABEL[R.cat] + ' ✕</button>');
  if (R.query) activeF.push('<button class="chip" aria-pressed="true" data-act="radarClearQ">"' + esc(R.query) + '" ✕</button>');
  Object.keys(R.off).forEach(function (k) { if (R.off[k]) activeF.push('<button class="chip" aria-pressed="true" data-act="radarToggle" data-arg="' + k + '">' + (VERDICT[k] ? VERDICT[k].label : GROUPS.filter(function (g) { return g.id === k; })[0].label) + ' 숨김 ✕</button>'); });

  var legendDefs = R.colorBy === 'verdict' ? V_ORDER.map(function (v) { return { id: v, label: VERDICT[v].label }; }) : GROUPS.map(function (g) { return { id: g.id, label: g.label }; });
  var legend = legendDefs.map(function (g) {
    var on = !R.off[g.id], n = D.base.filter(function (x) { return x.group === g.id; }).length;
    return '<button class="lg" aria-pressed="' + on + '" data-act="radarToggle" data-arg="' + g.id + '"><span class="sw" style="background:' + (on ? SW_COLOR[g.id] : 'transparent') + ';border:1.5px solid ' + SW_COLOR[g.id] + '"></span>' + g.label + ' <span class="mono muted" style="font-size:12px">' + n + '</span></button>';
  }).join('');

  // ---- quick verdict ----
  var s = D.sel, sj = s.j;
  var canPlan = sj.v !== 'no' && sj.v !== 'late';
  var qv = '<aside class="card qv" aria-label="고른 밈">' +
    '<div class="row" style="justify-content:space-between"><span class="note" style="font-weight:600">' + esc(b.name) + josa(b.name, '이', '가') + ' 써도 될까?</span><span class="note">' + esc(s.m.fmt || '') + ' · ' + esc(s.m.ages) + '</span></div>' +
    '<div class="stack" style="gap:6px"><span class="nm"' + lang(s.m) + '>' + esc(s.m.name) + '</span><span class="sub" style="font-size:13.5px">' + esc(s.m.gloss) + '</span></div>' +
    vboxHtml(sj) + axesHtml(sj) + '<div style="border-top:1px solid var(--line);padding-top:12px">' + lifeHtml(sj, S.lead) + '</div>' + fastLane(s.m, sj, S.lead) +
    '<div class="row" style="justify-content:space-between;align-items:flex-end"><div class="stack" style="gap:3px"><span class="note">12주 관심도</span>' + areaChart(s.m.w, 220, 44) + '</div>' +
    '<div class="stack" style="gap:2px;align-items:flex-end"><span class="disp" style="font-size:28px;line-height:1">' + s.m.w[11] + '</span><span class="mono ' + pctCls(s.p) + '" style="font-size:12px">' + arrow(s.p) + fmtPct(s.p) + ' · ' + D.per.label + '</span></div></div>' +
    '<p style="font-size:12.5px" class="sub"><b style="color:var(--ink)">' + esc(DIFF[s.m.diff] || '') + '</b> — ' + esc(DIFF_HINT[s.m.diff] || '') + '</p>' +
    '<div class="row" style="gap:8px">' + (canPlan ? '<button class="btn primary" style="flex:1" data-act="planWith" data-arg="' + s.m.id + '">이 밈으로 기획하기</button>' : '') +
    '<a class="btn" style="flex:1" href="#meme-' + s.m.id + '">자세히 보기</a>' +
    '<button class="btn" data-act="toggleWatch" data-arg="' + s.m.id + '" aria-pressed="' + !!S.watch[s.m.id] + '" aria-label="관심 밈에 넣기" style="width:42px;padding:0;color:' + (S.watch[s.m.id] ? 'var(--pink)' : 'var(--ink-2)') + ';border-color:' + (S.watch[s.m.id] ? 'var(--pink)' : 'var(--line-2)') + '">' + icon('heart', 16).replace('fill="none"', 'fill="' + (S.watch[s.m.id] ? 'currentColor' : 'none') + '"') + '</button></div></aside>';

  // ---- ranking ----
  var rankDefs = [
    { id: 'fit', label: '우리 브랜드 추천', note: b.name + '에 쓰기 좋은 순서예요 (이미 늦었거나 쓰면 안 되는 밈은 뺐어요)' },
    { id: 'hot', label: '급상승', note: D.per.label + ' 동안 관심이 가장 많이 오른 순서예요 (NEW = 새로 나온 밈)' },
    { id: 'fading', label: '곧 식을 밈', note: '최고점을 지났거나 식는 중이에요 — 지금 쓰고 있다면 바꿀 때예요' }
  ];
  var rd = rankDefs.filter(function (r) { return r.id === R.rank; })[0], rows;
  if (R.rank === 'fit') rows = D.ranked.filter(function (x) { return ['go', 'watch', 'care'].indexOf(x.j.v) >= 0; });
  else if (R.rank === 'hot') rows = D.all.filter(function (x) { return x.m.safety !== 'avoid'; }).sort(function (a, c) { return (c.p === null ? 1e9 : c.p) - (a.p === null ? 1e9 : a.p); });
  else rows = D.all.filter(function (x) { return x.m.stage === 'declining' || (x.m.stage === 'peak' && x.d7 !== null && x.d7 < 0); }).sort(function (a, c) { return c.m.w[11] - a.m.w[11]; });
  var rankHtml = '<div class="table-wrap"><table class="t"><thead><tr><th>#</th><th>밈</th><th class="hide-sm">12주</th><th>써도 될까</th><th class="num">' + D.per.label + ' 변화</th><th class="hide-sm" style="text-align:right">쓸 수 있는 기간</th></tr></thead><tbody>' +
    rows.slice(0, 10).map(function (x, i) {
      return '<tr class="click' + (x.m.id === s.m.id ? ' sel' : '') + '" data-act="radarPick" data-arg="' + x.m.id + '"><td class="mono muted">' + (i < 9 ? '0' : '') + (i + 1) + '</td><td><b' + lang(x.m) + '>' + esc(x.m.name) + '</b></td>' +
        '<td class="hide-sm" style="color:' + (x.p !== null && x.p < 0 ? 'var(--gray)' : 'var(--blue)') + '">' + spark(x.m.w, 64, 20) + '</td><td>' + badge(x.j.v) + '</td>' +
        '<td class="num ' + pctCls(x.p) + '">' + fmtPct(x.p) + '</td><td class="hide-sm sub" style="text-align:right;font-size:12.5px">' + esc(x.j.life.label) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
  if (!rows.length) rankHtml = emptyState('해당하는 밈이 없어요', '다른 순위 기준을 골라 보세요.');

  // ---- timing map (svg) ----
  var lanes = ['emerging', 'rising', 'peak', 'steady', 'declining'], W = 560, H = 330, L = 36, B = 30, laneW = (W - L) / 5, cnt = {};
  var yOf = function (v) { return (H - B) - (v / 100) * (H - B - 14) - 4; };
  var zoneY = yOf(100) - 6, zoneH = yOf(70) - zoneY;
  var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="유행 단계와 어울림으로 본 타이밍 맵">' +
    '<rect x="' + (L + laneW) + '" y="' + zoneY + '" width="' + (laneW * 2) + '" height="' + zoneH + '" fill="var(--blue-soft)" stroke="var(--blue)" stroke-dasharray="4 3" stroke-opacity=".6"></rect>' +
    lanes.map(function (l, i) { return '<line x1="' + (L + laneW * (i + 1)) + '" y1="0" x2="' + (L + laneW * (i + 1)) + '" y2="' + (H - B) + '" stroke="var(--line)" stroke-dasharray="3 3"></line><text x="' + (L + laneW * i + laneW / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="12" fill="var(--ink-2)">' + STAGE[l].label + '</text>'; }).join('') +
    '<line x1="' + L + '" y1="0" x2="' + L + '" y2="' + (H - B) + '" stroke="var(--line-2)"></line><line x1="' + L + '" y1="' + (H - B) + '" x2="' + W + '" y2="' + (H - B) + '" stroke="var(--line-2)"></line>' +
    [100, 70, 40].map(function (v) { return '<text x="' + (L - 6) + '" y="' + (yOf(v) + 4) + '" text-anchor="end" font-size="11" fill="var(--ink-3)" font-family="IBM Plex Mono, monospace">' + v + '</text>'; }).join('') +
    D.shown.slice().sort(function (a, c) { return c.m.w[11] - a.m.w[11]; }).map(function (x, i) {
      var li = lanes.indexOf(x.m.stage), k = cnt[li] = (cnt[li] || 0) + 1;
      var cx = L + laneW * li + laneW / 2 + (((k * 37) % 70) - 35) * (laneW / 110), cy = yOf(x.j.score), r = 5 + x.m.w[11] / 100 * 10, on = x.m.id === s.m.id;
      var lab = (on || i < 3) ? '<text x="' + (cx + r + 4) + '" y="' + (cy + 4) + '" font-size="12" font-weight="' + (on ? 700 : 500) + '" fill="var(--ink)" paint-order="stroke" stroke="var(--surface)" stroke-width="3">' + esc(x.m.name) + '</text>' : '';
      return '<g data-act="radarPick" data-arg="' + x.m.id + '" style="cursor:pointer"><title>' + esc(x.m.name) + ' · ' + STAGE[x.m.stage].label + ' · 어울림 ' + x.j.score + '점</title><circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' + SW_COLOR[x.j.v] + '" fill-opacity="' + (on ? 1 : .75) + '" stroke="' + (on ? 'var(--ink)' : 'var(--surface)') + '" stroke-width="' + (on ? 3 : 1.5) + '"></circle>' + lab + '</g>';
    }).join('') + '</svg>';

  // ---- alerts / risks ----
  var alerts = D.all.filter(function (x) { return S.watch[x.m.id]; }).map(function (x) {
    var a = alertFor(x.m);
    return '<div class="alert"><span class="ico ' + a.kind + '">' + icon(a.kind, 14) + '</span><span class="stack" style="gap:2px"><b' + lang(x.m) + '>' + esc(x.m.name) + '</b><span class="sub" style="font-size:13px">' + esc(a.text) + '</span></span><button class="btn sm" data-act="radarPick" data-arg="' + x.m.id + '">자세히</button></div>';
  }).join('') || '<p class="sub" style="font-size:13px;padding:8px 0">이 나라에서 지켜보는 밈이 없어요. 오른쪽 칸의 하트를 눌러 넣어 보세요.</p>';
  var risks = D.all.filter(function (x) { return x.j.v === 'no' || x.m.safety !== 'safe'; }).sort(function (a, c) { return c.m.w[11] - a.m.w[11]; }).slice(0, 5).map(function (x) {
    return '<a href="#meme-' + x.m.id + '" style="display:grid;grid-template-columns:110px 90px minmax(0,1fr);gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none;font-size:13px"><b' + lang(x.m) + '>' + esc(x.m.name) + '</b><span>' + badge(x.j.v) + '</span><span class="sub">' + esc(x.j.why[0] || x.m.note || '') + '</span></a>';
  }).join('') || '<p class="sub" style="font-size:13px;padding:8px 0">이 지역엔 따로 확인할 밈이 없어요.</p>';

  
  var ctx = '<div class="ctx" aria-label="우리 브랜드 기준">' +
    '<span class="ctx-brand">' + esc(b.name) + '</span>' +
    [esc(b.kind), esc(b.ages.join('·')), '한국', esc(b.tone)].map(function (v) { return '<span class="ctx-item">' + v + '</span>'; }).join('') +
    '<span class="ctx-sep"></span><span class="ctx-label">올리기까지</span>' + leadSeg() +
    '<a class="ctx-edit" href="#settings">브랜드 고치기</a></div>';

  var toolbar = '<div class="ex-tools">' +
    '<div class="seg" role="group" aria-label="지역">' + REGIONS.map(function (r) { return '<button aria-pressed="' + (r.id === R.region) + '" data-act="radarRegion" data-arg="' + r.id + '">' + r.label + '</button>'; }).join('') + '</div>' +
    '<div class="seg" role="group" aria-label="기간">' + PERIODS.map(function (p) { return '<button aria-pressed="' + (p.id === R.period) + '" data-act="radarPeriod" data-arg="' + p.id + '">' + p.label + '</button>'; }).join('') + '</div>' +
    '<div class="seg" role="group" aria-label="색 기준"><button aria-pressed="' + (R.colorBy === 'verdict') + '" data-act="radarColor" data-arg="verdict">써도 될까</button><button aria-pressed="' + (R.colorBy === 'stage') + '" data-act="radarColor" data-arg="stage">유행 단계</button></div>' +
    '<label class="search" style="margin-left:auto">' + icon('search', 14) + '<span class="sr">밈 이름 검색</span><input id="rq" data-in="radarQ" value="' + esc(R.query) + '" placeholder="이 목록에서 찾기"></label></div>' +
    '<div class="chips" role="group" aria-label="형식">' + CATS.map(function (c) { return '<button class="chip sm" aria-pressed="' + (c.id === R.cat) + '" data-act="radarCat" data-arg="' + c.id + '">' + c.label + '</button>'; }).join('') +
    '<span class="note" style="margin-left:auto;align-self:center" title="' + MORE_REGIONS + '">+8개 나라 준비 중</span></div>' +
    (activeF.length ? '<div class="row" style="gap:6px"><span class="note">적용한 필터</span>' + activeF.join('') + '<button class="btn sm" data-act="radarReset">모두 지우기</button></div>' : '');

  return '<header class="page-head"><div class="stack" style="gap:10px"><span class="eyebrow">이번 주 트렌드 · <span class="mono">' + AS_OF + ' 06:00</span> 갱신 <span class="tag-ex">예시 데이터</span></span>' +
    '<h1 class="h1">이번 주, ' + esc(b.name) + josa(b.name, '이', '가') + ' 쓸 수 있는 밈</h1>' + ctx + '</div>' +
    '<div class="row"><button class="btn" data-act="studioShorts">' + icon('studio', 14) + ' 쇼츠 분석하기</button><button class="btn primary" data-act="planWith" data-arg="">새 기획안</button></div></header>' +
    (todoHtml ? '<section class="stack" aria-labelledby="todo-h" style="gap:14px"><div class="sec-head"><h2 id="todo-h" class="h2">이번 주 할 일</h2><span class="note">' + esc(b.name) + ' 기준 · 근거와 판정 규칙은 각 밈의 자세히에서 볼 수 있어요</span></div><div class="grid-3 todo-row">' + todoHtml + '</div></section>' : '') +
    '<section class="stack" aria-labelledby="ex-h" style="gap:14px"><div class="sec-head"><h2 id="ex-h" class="h2">트렌드 탐색</h2><span class="note">글자 크기 = 이번 주 관심도 · 색 = ' + (R.colorBy === 'verdict' ? '써도 되는지' : '유행 단계') + ' · 누르면 오른쪽에 판정이 보여요</span></div>' +
    (R.region !== 'KR' ? '<p class="note">' + REGION_LABEL[R.region] + ' 밈을 ' + esc(b.name) + ' 기준으로 봤어요. 그 나라에서 캠페인을 한다면 현지 말로 쓸 수 있는지 먼저 확인하세요.</p>' : '') +
    '<div class="explore"><div class="card stack ex-card">' + toolbar +
    '<div class="cloud" id="cloud" aria-label="밈 워드클라우드"></div>' +
    (D.shown.length ? '' : emptyState('조건에 맞는 밈이 없어요', '필터를 줄이거나 다른 지역을 골라 보세요.', 'radarReset', '필터 초기화')) +
    '<div class="legend"><span class="note">지금 쓰이는 밈 ' + D.shown.length + '개 · 눌러서 켜고 끄기</span>' + legend + '</div></div>' + qv + '</div></section>' +
    '<div class="grid-split"><section class="card" aria-labelledby="rk-h"><div class="card-head"><h2 id="rk-h" class="h3">순위</h2><div class="seg" role="group" aria-label="순위 기준">' + rankDefs.map(function (r) { return '<button aria-pressed="' + (r.id === R.rank) + '" data-act="radarRank" data-arg="' + r.id + '">' + r.label + '</button>'; }).join('') + '</div></div><p class="note" style="margin-bottom:8px">' + esc(rd.note) + '</p>' + rankHtml +
    '<div class="row" style="justify-content:flex-end;margin-top:10px"><a href="#library" style="font-size:13px;font-weight:600">밈 사전에서 전체 보기 →</a></div></section>' +
    '<section class="card" aria-labelledby="mx-h"><div class="card-head"><h2 id="mx-h" class="h3">타이밍 맵</h2><span class="note">파란 칸 = 지금 기획하기 좋은 밈 · 원이 클수록 관심이 많아요</span></div><div class="matrix">' + svg + '</div></section></div>' +
    '<div class="grid-2"><section class="card" aria-labelledby="sf-h"><div class="card-head"><h2 id="sf-h" class="h3">많이 보이지만 쓰면 안 되는 밈</h2><span class="note">' + esc(b.name) + ' 기준</span></div>' + risks + '</section>' +
    '<section class="card" aria-labelledby="wt-h"><div class="card-head"><h2 id="wt-h" class="h3">지켜보는 밈 소식</h2><span class="note">매주 월요일 메일로도 보내요</span></div>' + alerts + '</section></div>' +
    '<footer class="method"><p><b>이렇게 골라요.</b> ' + METHOD_NOTE + '</p><p><b>데이터.</b> ' + SOURCES_NOTE + '. 모든 추천에는 출처와 날짜가 붙어요.</p></footer>';
};

// cloud layout after mount (depends on real width)
var cloudMemo = { key: '', html: '' };
AFTER.push(function () {
  var el = document.getElementById('cloud'); if (!el) return;
  var R = S.radar, D = radarData();
  var W = Math.max(280, el.clientWidth), H = el.clientHeight || 452;
  var small = W < 520;
  var key = R.region + '|' + W + '|' + D.shown.map(function (x) { return x.m.id; }).join(',');
  var layout;
  if (cloudMemo.key === key) layout = cloudMemo.layout;
  else {
    var opt = small ? { min: 13, max: 34, padX: 7, padY: 4, limit: 16 } : (R.region === 'GLOBAL' ? { min: 16, max: 54, padX: 8, padY: 4 } : { min: 18, max: 60, padX: 8, padY: 4 });
    layout = layoutCloud(D.shown.map(function (x) { return { id: x.m.id, name: x.m.name, weight: x.m.w[11] }; }), W, H, opt);
    cloudMemo = { key: key, layout: layout };
  }
  el.innerHTML = layout.map(function (c) {
    var x = D.byId[c.id], cls = WORD_CLS[x.group], on = c.id === D.sel.m.id;
    var flag = R.colorBy === 'stage' && x.m.safety !== 'safe' ? '<span class="flag" style="color:' + (x.m.safety === 'avoid' ? 'var(--red)' : 'var(--amber)') + '">' + (x.m.safety === 'avoid' ? '자제' : '주의') + '</span>' : '';
    return '<button type="button" class="w ' + cls + '" aria-pressed="' + on + '" data-act="radarPick" data-arg="' + c.id + '" aria-label="' + esc(c.name + ', ' + x.j.label + ', 관심도 ' + x.m.w[11]) + '" style="left:' + c.x + 'px;top:' + c.y + 'px;width:' + c.bw + 'px;height:' + c.bh + 'px;font-size:' + c.fs + 'px;line-height:' + c.bh + 'px"' + lang(x.m) + '>' + esc(c.name) + flag + '</button>';
  }).join('');
});

ACT.radarPick = function (id) { S.radar.sel = id; render(); };
ACT.radarRegion = function (r) { S.radar.region = r; S.radar.sel = null; S.radar.off = {}; render(); };
ACT.radarPeriod = function (p) { S.radar.period = p; render(); };
ACT.radarCat = function (c) { S.radar.cat = c; render(); };
ACT.radarColor = function (c) { S.radar.colorBy = c; S.radar.off = {}; render(); };
ACT.radarToggle = function (g) { S.radar.off[g] = !S.radar.off[g]; render(); };
ACT.radarRank = function (r) { S.radar.rank = r; render(); };
ACT.radarReset = function () { S.radar.cat = 'all'; S.radar.query = ''; S.radar.off = {}; render(); };
ACT.radarClearQ = function () { S.radar.query = ''; render(); };
ACT.studioShorts = function () { S.studio.mode = 'shorts'; S.studio.step = 1; S.studio.ran = false; S.studio.phase = 'idle'; go('studio'); };
IN.radarQ = function (v) { S.radar.query = v; render(); };
// ===== end radar =====
