// ===== pages: 라이브러리 · 밈 브리프 · 리포트 · 퀵 체크 · 기획안 · 설정 · 해석기 · 지역 비교 =====
var PAGE_SIZE = 10;

// ---------- 밈 라이브러리 (filter · sort · pagination) ----------
function libRows() {
  var L = S.lib, b = brand(), q = L.query.trim().toLowerCase();
  var rows = ALL.map(function (m) { return { m: m, j: J(m, b), p4: pct(m.w, 4) }; }).filter(function (x) {
    return (L.region === 'all' || x.m.region === L.region) && (L.verdict === 'all' || x.j.v === L.verdict) && (L.stage === 'all' || STAGE[x.m.stage].group === L.stage) &&
      (L.cat === 'all' || x.m.cat === L.cat) && (!q || x.m.name.toLowerCase().indexOf(q) >= 0 || x.m.gloss.indexOf(L.query.trim()) >= 0 || (ALIASES[x.m.id] || []).some(function (a) { return a.indexOf(L.query.trim()) >= 0; }));
  });
  var sorters = {
    hot: function (a, c) { return (c.p4 === null ? 1e9 : c.p4) - (a.p4 === null ? 1e9 : a.p4); },
    idx: function (a, c) { return c.m.w[11] - a.m.w[11]; },
    fit: function (a, c) { return V_ORDER.indexOf(a.j.v) - V_ORDER.indexOf(c.j.v) || c.j.score - a.j.score; },
    name: function (a, c) { return a.m.name.localeCompare(c.m.name, 'ko'); }
  };
  return rows.sort(sorters[L.sort]);
}
PAGES.library = function () {
  var L = S.lib, rows = libRows(), total = rows.length, pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (L.page > pages) L.page = pages;
  var from = (L.page - 1) * PAGE_SIZE, slice = rows.slice(from, from + PAGE_SIZE);
  var sel = function (id, label, value, opts) {
    return '<label class="field" for="' + id + '" style="min-width:130px">' + label + '<select class="select" id="' + id + '" data-ch="' + id + '">' + opts.map(function (o) { return '<option value="' + o[0] + '"' + (o[0] === value ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select></label>';
  };
  var active = [];
  if (L.region !== 'all') active.push(['region', REGION_LABEL[L.region]]);
  if (L.verdict !== 'all') active.push(['verdict', VERDICT[L.verdict].label]);
  if (L.stage !== 'all') active.push(['stage', GROUPS.filter(function (g) { return g.id === L.stage; })[0].label]);
  if (L.cat !== 'all') active.push(['cat', CAT_LABEL[L.cat]]);
  if (L.query) active.push(['query', '"' + L.query + '"']);
  var table = '<div class="table-wrap hide-sm"><table class="t"><thead><tr><th>밈</th><th>뜻</th><th>지역</th><th>단계</th><th>' + esc(brand().name) + '에 써도 될까</th><th class="num">관심도</th><th class="num">4주 변화</th><th>12주</th></tr></thead><tbody>' +
    slice.map(function (x) {
      return '<tr class="click" data-act="goMeme" data-arg="' + x.m.id + '"><td><a class="lib-name" href="#meme-' + x.m.id + '"' + lang(x.m) + ' style="color:var(--ink)">' + esc(x.m.name) + '</a><br><span class="note">' + esc(x.m.fmt || CAT_LABEL[x.m.cat]) + ' · ' + esc(x.m.ages) + '</span></td>' +
        '<td class="sub" style="font-size:13px;max-width:320px">' + esc(x.m.gloss) + '</td><td class="sub" style="white-space:nowrap">' + REGION_LABEL[x.m.region] + '</td><td>' + stageChip(x.m.stage) + '</td><td>' + badge(x.j.v) + '</td>' +
        '<td class="num">' + x.m.w[11] + '</td><td class="num ' + pctCls(x.p4) + '">' + fmtPct(x.p4) + '</td><td style="color:' + (x.p4 !== null && x.p4 < 0 ? 'var(--gray)' : 'var(--blue)') + '">' + spark(x.m.w, 72, 22) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
  var list = '<div class="show-sm stack" style="gap:0">' + slice.map(function (x) {
    return '<a href="#meme-' + x.m.id + '" style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 10px;padding:12px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none"><span class="lib-name"' + lang(x.m) + '>' + esc(x.m.name) + '</span>' + badge(x.j.v) + '<span class="sub" style="font-size:13px">' + esc(x.m.gloss) + '</span><span class="mono ' + pctCls(x.p4) + '" style="font-size:12px;text-align:right">' + fmtPct(x.p4) + '</span></a>';
  }).join('') + '</div>';
  var pageBtns = [];
  for (var i = 1; i <= pages; i++) pageBtns.push('<button data-act="libPage" data-arg="' + i + '"' + (i === L.page ? ' aria-current="page"' : '') + ' aria-label="' + i + '쪽">' + i + '</button>');
  var pager = '<nav class="pager" aria-label="쪽 이동"><span class="note">총 ' + total + '개 중 ' + (total ? from + 1 : 0) + '–' + Math.min(total, from + PAGE_SIZE) + '</span><div class="pages"><button data-act="libPage" data-arg="' + (L.page - 1) + '"' + (L.page === 1 ? ' disabled' : '') + ' aria-label="이전 쪽">‹</button>' + pageBtns.join('') + '<button data-act="libPage" data-arg="' + (L.page + 1) + '"' + (L.page === pages ? ' disabled' : '') + ' aria-label="다음 쪽">›</button></div></nav>';
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">밈 사전</span><h1 class="h1">모아 둔 밈 ' + ALL.length + '개</h1><p class="sub">뜻, 유행 단계, ' + esc(brand().name) + '에 써도 되는지를 한 표에서 봐요. 누르면 자세히 볼 수 있어요.</p></div>' + brandLine() + '</header>' +
    '<section class="card stack"><div class="row" style="align-items:flex-end;gap:12px">' +
    '<label class="field" for="lib-q" style="flex:1;min-width:220px">검색<span class="search">' + icon('search', 14) + '<input id="lib-q" data-in="libQ" value="' + esc(L.query) + '" placeholder="이름·뜻·변형으로 찾기 · 예: 삐, 감탄사"></span></label>' +
    sel('libRegion', '지역', L.region, [['all', '전체']].concat(REGIONS.map(function (r) { return [r.id, r.label]; }))) +
    sel('libVerdict', '써도 될까', L.verdict, [['all', '전체']].concat(V_ORDER.map(function (v) { return [v, VERDICT[v].label]; }))) +
    sel('libStage', '단계', L.stage, [['all', '전체']].concat(GROUPS.map(function (g) { return [g.id, g.label]; }))) +
    sel('libCat', '형식', L.cat, CATS.map(function (c) { return [c.id, c.label]; })) +
    sel('libSort', '정렬', L.sort, [['hot', '4주 급상승'], ['idx', '관심도 높은 순'], ['fit', '우리 브랜드에 맞는 순'], ['name', '이름순']]) + '</div>' +
    (active.length ? '<div class="row" style="gap:6px"><span class="note">적용한 필터</span>' + active.map(function (a) { return '<button class="chip" aria-pressed="true" data-act="libClear" data-arg="' + a[0] + '">' + esc(a[1]) + ' ✕</button>'; }).join('') + '<button class="btn sm" data-act="libReset">모두 지우기</button></div>' : '') +
    (total ? table + list + pager : emptyState('조건에 맞는 밈이 없어요', '필터를 하나씩 지워 보세요.', 'libReset', '필터 모두 지우기')) + '</section>';
};
ACT.goMeme = function (id, el, e) { if (e && e.target.closest('a')) return; go('meme-' + id); };
ACT.libPage = function (p) { S.lib.page = Math.max(1, +p); render(); var t = document.querySelector('.pager'); if (t) t.scrollIntoView({ block: 'end' }); };
ACT.libClear = function (k) { S.lib[k] = k === 'query' ? '' : 'all'; S.lib.page = 1; render(); };
ACT.libReset = function () { Object.assign(S.lib, { region: 'all', verdict: 'all', stage: 'all', cat: 'all', query: '', page: 1 }); render(); };
IN.libQ = function (v) { S.lib.query = v; S.lib.page = 1; render(); };
['Region', 'Verdict', 'Stage', 'Cat', 'Sort'].forEach(function (k) { IN['lib' + k] = function (v) { S.lib[k.toLowerCase()] = v; S.lib.page = 1; render(); }; });

// ---------- 밈 브리프 ----------
function dayOf(md) { var p = md.split('/'); var m = +p[0], d = +p[1]; return { 6: 0, 7: 30, 8: 61, 9: 92 }[m] + d - 22; }
PAGES.meme = function (id) {
  var m = BY_ID[id], b = brand(), j = J(m, b), rich = id === 'pierrot' ? DOSSIER : id === 'yar' ? DETAIL_YAR : null;
  var d7 = pct(m.w, 1), aliases = (rich && rich.aliases) || ALIASES[id] || [];
  var reviewed = id === 'pierrot' || id === 'yar' ? '사람이 확인함' : '자동 분석 · 사람 확인 전';
  // chart
  var W = 720, H = 240, pad = 8, top = 30;
  var pts = m.w.map(function (v, i) { return { x: 40 + pad + i * (W - 40 - 2 * pad) / 11, y: top + (H - top - 26) - (v / 100) * (H - top - 26 - pad), v: v, i: i }; });
  var line = pts.map(function (p) { return p.x.toFixed(1) + ',' + p.y.toFixed(1); }).join(' ');
  var base = top + (H - top - 26);
  var ev = id === 'pierrot' ? DOSSIER.path.map(function (p, i) { return { n: i + 1, x: 40 + pad + dayOf(p.date) / 77 * (W - 40 - 2 * pad), off: { 0: -11, 1: 11, 3: -11, 4: 11 }[i] || 0 }; }) : [];
  var hi = S.meme.hover;
  var chart = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="12주 관심도 그래프">' +
    [100, 50, 0].map(function (v) { var y = base - (v / 100) * (H - top - 26 - pad); return '<line x1="40" x2="' + W + '" y1="' + y + '" y2="' + y + '" stroke="var(--line)"></line><text x="32" y="' + (y + 4) + '" text-anchor="end" font-size="11" fill="var(--ink-3)" font-family="IBM Plex Mono, monospace">' + v + '</text>'; }).join('') +
    '<polygon points="' + pts[0].x + ',' + base + ' ' + line + ' ' + pts[11].x + ',' + base + '" fill="var(--blue-soft)"></polygon><polyline points="' + line + '" fill="none" stroke="var(--blue)" stroke-width="2.5" stroke-linejoin="round"></polyline>' +
    ev.map(function (e) { return '<line x1="' + e.x + '" x2="' + e.x + '" y1="24" y2="' + base + '" stroke="var(--ink)" stroke-dasharray="3 3" stroke-opacity=".45"></line><circle cx="' + (e.x + e.off) + '" cy="12" r="10" fill="#141412"></circle><text x="' + (e.x + e.off) + '" y="16" text-anchor="middle" font-size="11" fill="#E3FF3B" font-family="IBM Plex Mono, monospace">' + e.n + '</text>'; }).join('') +
    pts.map(function (p) { return '<g data-act="memeHover" data-arg="' + p.i + '" style="cursor:pointer"><circle cx="' + p.x + '" cy="' + p.y + '" r="14" fill="transparent"></circle><circle cx="' + p.x + '" cy="' + p.y + '" r="' + (hi === p.i ? 7 : 5) + '" fill="' + (hi === p.i ? 'var(--hl)' : 'var(--surface)') + '" stroke="var(--blue)" stroke-width="2"></circle><title>' + WEEKS[p.i] + ' 주 · 관심도 ' + p.v + '</title></g>'; }).join('') +
    pts.map(function (p) { return '<text x="' + p.x + '" y="' + (H - 6) + '" text-anchor="middle" font-size="11" fill="var(--ink-3)" font-family="IBM Plex Mono, monospace">' + WEEKS[p.i] + '</text>'; }).join('') +
    (hi !== null && pts[hi] ? '<g><rect x="' + (pts[hi].x - 62) + '" y="' + (pts[hi].y - 40) + '" width="124" height="26" rx="6" fill="var(--inverse)"></rect><text x="' + pts[hi].x + '" y="' + (pts[hi].y - 23) + '" text-anchor="middle" font-size="12" font-weight="600" fill="var(--on-inverse)">' + WEEKS[hi] + ' 주 · 관심도 ' + pts[hi].v + '</text></g>' : '') + '</svg>';
  var pathList = id === 'pierrot' ? '<ol class="path" style="list-style:none;margin:0;padding:0">' + DOSSIER.path.map(function (p, i) { return '<li><span class="pin">' + (i + 1) + '</span><span class="mono sub">' + p.date + '</span><span class="stack" style="gap:2px"><span><b>' + esc(p.kind) + '</b><span class="muted"> · ' + esc(p.domain || '이름 비공개') + '</span></span><span>' + esc(p.title) + '</span><span class="muted">' + esc(p.note || '') + '</span></span></li>'; }).join('') + '</ol>' : '';
  var usage = rich && rich.usage ? rich.usage.map(function (u) { var mine = b.ages.indexOf(u.age) >= 0; return '<div class="axis" style="grid-template-columns:40px minmax(0,1fr) 40px"><b>' + u.age + '</b><span class="bar" style="height:16px;border-radius:4px"><i style="width:' + u.share + '%;border-radius:4px;background:' + (mine ? 'var(--blue)' : 'var(--line-2)') + '"></i></span><span class="mono" style="text-align:right">' + u.share + '%</span></div>'; }).join('') + '<p class="note">처음 쓰인 연령대별 비율이에요. ' + esc(b.name) + ' 타깃(' + esc(b.ages.join('·')) + ')과 겹치는 연령은 파랑이에요.</p>'
    : '<p class="sub" style="font-size:13.5px">주로 <b style="color:var(--ink)">' + esc(m.ages) + '</b>가 써요. 나이대별 비율은 사람이 확인한 뒤 채워져요.</p>';
  var safety = id === 'pierrot' ? DOSSIER.safety : [
    { k: '비하·혐오', state: m.safety === 'safe' ? 'ok' : 'care', t: m.safety === 'safe' ? '걸리는 점이 없어요' : (m.note || '문맥 확인 필요') },
    { k: '실존 인물·저작권', state: m.tip ? 'care' : 'ok', t: m.tip || '해당 신호 없음' },
    { k: '광고 규제 표현', state: m.id === 'wegovy' ? 'care' : 'ok', t: m.id === 'wegovy' ? '의약품 이름 — 광고 문구엔 부적합' : '해당 없음' }
  ];
  var safetyHtml = safety.map(function (s) { return '<div class="safe-row"><span class="safe-ic ' + (s.state === 'ok' ? 'ok' : 'care') + '">' + icon(s.state === 'ok' ? 'ok' : 'warn', 12) + '</span><span class="stack" style="gap:1px"><b>' + esc(s.k) + '</b><span class="sub">' + esc(s.t) + '</span></span></div>'; }).join('');
  var ex = rich && rich.goodEx ? '<div class="grid-2"><div class="ex good"><b style="font-size:12px">이렇게 쓰면 통해요</b><q>' + esc(rich.goodEx.text) + '</q><span style="font-size:12.5px">' + esc(rich.goodEx.why) + '</span></div><div class="ex bad"><b style="font-size:12px">이렇게 쓰면 어색해요</b><q>' + esc(rich.badEx.text) + '</q><span style="font-size:12.5px">' + esc(rich.badEx.why) + '</span></div></div>'
    : (m.note || m.tip ? '<div class="vbox care"><b style="font-size:12.5px">쓰기 전에</b><span style="font-size:13px">' + esc(m.note || m.tip) + '</span></div>' : '');
  var srcs = id === 'pierrot' ? DOSSIER.path.map(function (p) { return { kind: p.kind, domain: p.domain || '커뮤니티 · 이름 비공개', title: p.title, date: '2026-0' + p.date.split('/')[0] + '-' + ('0' + p.date.split('/')[1]).slice(-2) }; }) : rich ? rich.sources : [];
  var similar = MEMES[m.region].filter(function (x) { return x.id !== id && x.cat === m.cat; }).sort(function (a, c) { return c.w[11] - a.w[11]; }).slice(0, 4);
  var canPlan = j.v !== 'no' && j.v !== 'late';
  return '<nav aria-label="위치" class="row" style="gap:8px;font-size:13px"><a href="#library">밈 사전</a><span class="muted">›</span><b' + lang(m) + '>' + esc(m.name) + '</b>' +
    '<span style="margin-left:auto" class="row"><span class="badge" style="background:var(--blue-soft);color:var(--blue-ink)">' + icon('ok', 12) + reviewed + '</span><span class="note">' + AS_OF + ' · 7일마다 다시 확인 · 예시 데이터</span>' +
    '<button class="btn sm" data-act="toggleWatch" data-arg="' + id + '" style="' + (S.watch[id] ? 'color:var(--pink);border-color:var(--pink)' : '') + '">' + (S.watch[id] ? '관심 밈에 있음' : '관심 밈에 넣기') + '</button>' +
    '<button class="btn sm" data-act="memeReport" data-arg="' + id + '">' + (S.meme.report[id] ? '리포트에 담음' : '주간 리포트에 담기') + '</button></span></nav>' +
    '<div class="meme-hero"><section class="card stack" style="gap:14px;padding:26px 28px"><span class="eyebrow">밈 자세히 · ' + REGION_LABEL[m.region] + '</span><h1 class="big disp"' + lang(m) + '>' + esc(m.name) + '</h1>' +
    '<p style="font-size:19px;font-weight:600;line-height:1.5">' + esc(id === 'pierrot' ? DOSSIER.rule : m.gloss) + '</p>' +
    (aliases.length ? '<div class="chips">' + aliases.map(function (a) { return '<span class="alias">' + esc(a) + '</span>'; }).join('') + '</div>' : '') +
    facts([['형식', esc(m.fmt || CAT_LABEL[m.cat])], ['쓰는 사람', esc(m.ages)], ['단계', STAGE[m.stage].label + ' · ' + esc(DIFF[m.diff] || '')], ['첫 등장', esc(m.since)], ['이번 주 관심도', '<span class="mono">' + m.w[11] + '</span> <span class="mono ' + pctCls(d7) + '" style="font-size:12px">지난주 ' + fmtPct(d7) + '</span>']], 'border-top:1px solid var(--line);padding-top:14px') + ex + '</section>' +
    '<aside class="card stack" aria-label="우리 브랜드가 써도 될까"><span class="note" style="font-weight:600">우리 브랜드가 써도 될까요?</span>' + brandLine() + '<div class="row"><span class="sub" style="font-size:12.5px">올리기까지 걸리는 시간</span>' + leadSeg() + '</div>' +
    vboxHtml(j, true) + axesHtml(j) + '<div style="border-top:1px solid var(--line);padding-top:12px">' + lifeHtml(j, S.lead) + '</div>' + fastLane(m, j, S.lead) +
    (canPlan ? '<button class="btn lg primary" data-act="planWith" data-arg="' + id + '">이 밈으로 기획하기</button>' : '<a class="btn lg" href="#radar">레이더에서 대신 쓸 밈 찾기</a>') + '</aside></div>' +
    '<section class="card stack chart"><div class="card-head" style="margin:0"><h2 class="h3">' + (id === 'pierrot' ? '어떻게 퍼졌나 — 커뮤니티에서 뉴스까지 16일' : '12주 관심도') + '</h2><span class="note">관심도 0–100 · 점을 누르면 값이 보여요 · 지금 <b style="color:var(--ink)">' + esc(DIFF[m.diff] || '') + '</b></span></div>' +
    (pathList ? '<div class="grid-2" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)"><div>' + chart + '</div>' + pathList + '</div>' : chart) + '<p class="note">' + esc(DIFF_HINT[m.diff] || '') + '</p></section>' +
    '<div class="grid-3"><section class="card stack"><h2 class="h3">뜻 · 유래 · 뉘앙스</h2><p style="font-size:13.5px">' + esc(rich ? rich.definition : m.gloss) + '</p>' +
    (rich ? '<p class="sub" style="font-size:13px"><b style="color:var(--ink)">유래 </b>' + esc(rich.origin) + '</p><p class="sub" style="font-size:13px"><b style="color:var(--ink)">뉘앙스 </b>' + esc(rich.nuance) + '</p>' : '<p class="note">자세한 유래와 뉘앙스는 사람이 확인한 뒤 채워져요.</p>') +
    (PLAIN[id] ? '<p class="sub" style="font-size:13px"><b style="color:var(--ink)">쉽게 말해 </b>' + esc(PLAIN[id]) + '</p>' : '') + '</section>' +
    '<section class="card stack"><h2 class="h3">누가 쓰나</h2>' + usage + '</section><section class="card stack" style="gap:6px"><h2 class="h3">브랜드 안전 체크</h2>' + safetyHtml + '</section></div>' +
    '<div class="grid-2">' + (rich ? '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">이렇게 써 보세요</h2><span class="note">AI 제안 · 예시</span></div><div class="grid-3">' + rich.angles.map(function (a) { return '<div class="stack" style="gap:8px;padding:14px;border-radius:12px;background:var(--surface-2)"><b>' + esc(a.title) + '</b><span class="sub" style="font-size:12.5px;flex:1">' + esc(a.t) + '</span><button class="btn sm" data-act="planWith" data-arg="' + id + '">이 방향으로 기획</button></div>'; }).join('') + '</div>' +
      '<div class="grid-2" style="border-top:1px solid var(--line);padding-top:12px"><div class="stack" style="gap:6px"><b style="font-size:12.5px;color:var(--blue-ink)">쓰기 좋은 상황</b>' + rich.goodFor.map(function (t) { return '<span style="font-size:13px">· ' + esc(t) + '</span>'; }).join('') + '</div><div class="stack" style="gap:6px"><b style="font-size:12.5px;color:var(--red-ink)">피할 상황</b>' + rich.avoidFor.map(function (t) { return '<span style="font-size:13px">· ' + esc(t) + '</span>'; }).join('') + '</div></div></section>'
      : '<section class="card stack"><h2 class="h3">비슷한 밈</h2>' + (similar.length ? similar.map(function (x) { var jj = J(x, b); return '<div class="row" style="justify-content:space-between;border-top:1px solid var(--line);padding-top:10px;flex-wrap:nowrap"><span>' + memeLink(x, 'lib-name') + ' <span class="note">' + esc(x.gloss) + '</span></span>' + badge(jj.v) + '</div>'; }).join('') : '<p class="note">같은 형식의 밈이 아직 없어요.</p>') + '</section>') +
    '<section class="card stack" style="gap:4px"><div class="card-head" style="margin:0 0 6px"><h2 class="h3">출처 ' + srcs.length + '건</h2><span class="note">커뮤니티 글은 이름과 링크를 보여 주지 않아요</span></div>' +
    (srcs.length ? srcs.map(function (s) { return '<div style="display:grid;grid-template-columns:90px minmax(0,1fr);gap:10px;padding:8px 0;border-top:1px solid var(--line);font-size:12.5px"><span class="stack" style="gap:1px"><b>' + esc(s.kind) + '</b><span class="mono muted">' + esc(s.date) + '</span></span><span class="stack" style="gap:1px"><span style="color:var(--blue-ink)">' + esc(s.title) + '</span><span class="muted">' + esc(s.domain) + '</span></span></div>'; }).join('')
      : '<p class="note">이 밈의 출처 목록은 예시 데이터에 없어요. 실제 서비스에서는 쇼츠·뉴스·위키 출처와 관측 날짜가 붙어요.</p>') + '</section></div>';
};
ACT.memeHover = function (i) { S.meme.hover = +i; render(); };
ACT.memeReport = function (id) { S.meme.report[id] = !S.meme.report[id]; toast(S.meme.report[id] ? '이번 주 리포트에 담았어요' : '리포트에서 뺐어요'); render(); };

// ---------- 주간 리포트 ----------
PAGES.report = function () {
  var b = brand(), all = MEMES.KR.map(function (m) { return { m: m, j: J(m, b), d7: pct(m.w, 1) }; });
  var gos = all.filter(function (x) { return x.j.v === 'go'; }).sort(function (a, c) { return c.j.score - a.j.score; });
  var early = all.filter(function (x) { return (x.j.v === 'go' || x.j.v === 'watch') && (x.m.stage === 'rising' || x.m.stage === 'emerging'); }).sort(function (a, c) { return (c.d7 || 0) - (a.d7 || 0); })[0];
  var bad = all.filter(function (x) { return x.j.v === 'no' || x.j.v === 'late'; }).sort(function (a, c) { return c.m.w[11] - a.m.w[11]; });
  var fading = all.filter(function (x) { return x.m.stage === 'declining' || (x.m.stage === 'peak' && x.d7 !== null && x.d7 < 0); }).sort(function (a, c) { return c.m.w[11] - a.m.w[11]; }).slice(0, 4);
  var picked = Object.keys(S.meme.report).filter(function (k) { return S.meme.report[k]; }).map(function (k) { return BY_ID[k]; });
  var counts = V_ORDER.map(function (v) { return { v: v, n: all.filter(function (x) { return x.j.v === v; }).length }; });
  var sum = [];
  if (gos[0]) sum.push(['이번 주 쓸 밈', 'go', '<b class="hl">' + esc(gos[0].m.name) + '</b>' + josa(gos[0].m.name, '을', '를') + ' 1순위로 추천해요 — 어울림 ' + gos[0].j.score + '점, ' + esc(gos[0].j.life.label) + ' 쓸 수 있어요.', gos[0].j.plus.join(' · ')]);
  if (early) sum.push(['먼저 쓰면 좋은 밈', 'watch', '<b>' + esc(early.m.name) + '</b>' + josa(early.m.name, '은', '는') + ' 지난주보다 ' + fmtPct(early.d7) + ' 올랐어요.', DIFF_HINT[early.m.diff] || '']);
  if (bad[0]) sum.push(['지금은 피할 밈', 'no', '<b>' + esc(bad[0].m.name) + '</b>' + josa(bad[0].m.name, '은', '는') + ' 자주 보이지만(관심도 ' + bad[0].m.w[11] + ') ' + esc(VERDICT[bad[0].j.v].label) + '.', bad[0].j.why[0] || '']);
  var plans = S.plans.filter(function (p) { return p.brandId === S.brandId; });
  var statusStyle = function (s) { return s === '초안' ? 'v-late' : s === '승인' || s === '게시 완료' ? 'v-go' : 'v-care'; };
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">주간 리포트</span><h1 class="h1">팀장님께 보내는 한 장</h1><p class="sub">매주 월요일, 브랜드 기준으로 자동으로 써져요.</p></div>' +
    '<div class="row"><button class="btn" data-act="copy" data-text="' + esc(sum.map(function (s) { return s[0] + ': ' + s[2].replace(/<[^>]+>/g, ''); }).join('\n') + '\n— 트렌드 통역 · ' + AS_OF) + '" data-ok="3줄 요약을 복사했어요">' + icon('copy', 14) + ' 3줄 요약 복사</button>' +
    '<button class="btn" data-act="toast" data-arg="PDF·슬라이드 내보내기는 실제 서비스에서 제공돼요">PDF·슬라이드</button>' +
    '<button class="btn ' + (S.report.mail ? 'on' : '') + '" data-act="reportMail" aria-pressed="' + S.report.mail + '">' + (S.report.mail ? '매주 월요일 메일 받는 중' : '매주 월요일 메일로 받기') + '</button></div></header>' +
    '<div class="row">' + brandLine() + '<span class="note">· 왼쪽 위에서 브랜드를 바꾸면 리포트도 바뀌어요</span></div>' +
    '<article class="doc"><div class="row" style="justify-content:space-between"><span class="row" style="gap:8px;font-size:12.5px;font-weight:600"><span class="logo" style="width:22px;height:22px;border-radius:6px"><svg width="12" height="12" viewBox="0 0 18 18" fill="none" aria-hidden="true"><circle cx="9" cy="9" r="6.5" stroke="#E3FF3B" stroke-width="2"></circle></svg></span>트렌드 통역 · 주간 리포트</span><span class="note">한국 · 제작 기간 ' + leadLabel(S.lead) + ' 기준</span></div>' +
    '<div class="stack" style="gap:6px"><h2 class="disp" style="font-size:clamp(30px,5vw,44px);display:block">이번 주 밈 리포트</h2><b style="font-size:17px">' + REPORT.week + '</b><span class="note">' + esc(b.name) + ' 팀 · ' + AS_OF + ' · <span class="tag-ex">예시 데이터</span></span></div>' +
    '<div class="stack" style="gap:6px"><div class="stackbar">' + counts.filter(function (c) { return c.n; }).map(function (c) { return '<span style="flex:' + c.n + ';background:' + SW_COLOR[c.v] + '"></span>'; }).join('') + '</div><div class="row" style="gap:12px;font-size:12px">' + counts.map(function (c) { return '<span class="row" style="gap:5px"><span style="width:9px;height:9px;border-radius:2px;background:' + SW_COLOR[c.v] + '"></span>' + VERDICT[c.v].label + ' <b class="mono">' + c.n + '</b></span>'; }).join('') + '</div></div>' +
    '<section class="stack"><h2><span class="mono">01</span>3줄 요약</h2><div style="border:1px solid var(--line);border-radius:10px">' + sum.map(function (s, i) { return '<div class="sumline"><span class="pin" style="background:var(--sunk);color:var(--ink)">' + (i + 1) + '</span><span class="stack" style="gap:3px"><b style="font-size:12px;color:' + SW_COLOR[s[1]] + '">' + s[0] + '</b><span style="font-size:14.5px">' + s[2] + '</span><span class="note">' + esc(s[3]) + '</span></span></div>'; }).join('') + '</div></section>' +
    '<section class="stack"><h2><span class="mono">02</span>이번 주 쓸 밈 TOP 5</h2><div class="table-wrap"><table class="t"><thead><tr><th>#</th><th>밈</th><th>한 줄 뜻</th><th>써도 될까</th><th>쓸 수 있는 기간</th><th class="num">어울림</th></tr></thead><tbody>' +
    gos.slice(0, 5).map(function (x, i) { return '<tr class="click" data-act="goMeme" data-arg="' + x.m.id + '"><td class="mono muted">0' + (i + 1) + '</td><td class="lib-name">' + esc(x.m.name) + '</td><td class="sub" style="font-size:13px">' + esc(x.m.gloss) + '</td><td>' + badge(x.j.v) + '</td><td class="sub">' + esc(x.j.life.label) + '</td><td class="num">' + x.j.score + '</td></tr>'; }).join('') + '</tbody></table></div></section>' +
    '<div class="grid-2"><section class="stack"><h2><span class="mono">03</span>쓰지 말아야 할 밈</h2>' + bad.slice(0, 4).map(function (x) { return '<div style="border-top:1px solid var(--line);padding-top:8px"><div class="row" style="justify-content:space-between"><b>' + esc(x.m.name) + ' ' + badge(x.j.v) + '</b><span class="mono note">관심도 ' + x.m.w[11] + '</span></div><span class="sub" style="font-size:13px">' + esc(x.j.why[0] || '') + '</span></div>'; }).join('') + '</section>' +
    '<section class="stack"><h2><span class="mono">04</span>곧 식을 밈 — 쓰고 있다면 바꿀 때예요</h2>' + fading.map(function (x) { return '<div style="border-top:1px solid var(--line);padding-top:8px"><b>' + esc(x.m.name) + '</b> ' + stageChip(x.m.stage) + '<br><span class="sub" style="font-size:13px">' + esc(alertFor(x.m).text) + '</span></div>'; }).join('') + '</section></div>' +
    (picked.length ? '<section class="stack"><h2><span class="mono">+</span>팀이 담은 밈</h2><div class="chips">' + picked.map(function (m) { return '<a class="alias" href="#meme-' + m.id + '">' + esc(m.name) + '</a>'; }).join('') + '</div></section>' : '') +
    '<section class="stack"><h2><span class="mono">05</span>우리 팀 계획</h2>' + (plans.length ? plans.map(function (p) { var m = BY_ID[p.memeId]; return '<div class="row" style="justify-content:space-between;border-top:1px solid var(--line);padding-top:10px"><span class="stack" style="gap:2px"><b>' + esc(p.title) + '</b><span class="note">밈 ' + esc(m ? m.name : '') + (m ? ' · ' + J(m, b).label : '') + '</span></span><span class="row"><span class="badge ' + statusStyle(p.status) + '">' + esc(p.status) + '</span><b class="mono" style="font-size:13px">' + esc(p.due) + '</b></span></div>'; }).join('') : '<p class="note">이 브랜드로 저장한 기획안이 없어요. <a href="#studio">스튜디오에서 만들기</a></p>') + '</section>' +
    '<footer class="method" style="border-top:1px solid var(--line)"><p><b>이렇게 골라요.</b> ' + METHOD_NOTE + '</p><p><b>데이터.</b> ' + SOURCES_NOTE + '.</p></footer></article>';
};
ACT.reportMail = function () { S.report.mail = !S.report.mail; toast(S.report.mail ? '다음 메일은 9/21 (월)에 가요 (예시)' : '메일 받기를 껐어요'); render(); };
ACT.toast = function (msg) { toast(msg); };

// ---------- 퀵 체크 ----------
PAGES.check = function () {
  var C = S.check, b = brand(), q = C.query.trim();
  var m = BY_ID[C.sel] || BY_ID.pierrot, j = J(m, b);
  var sugg = q ? ALL.filter(function (x) { return x.name.indexOf(q) >= 0 || (ALIASES[x.id] || []).some(function (a) { return a.indexOf(q) >= 0; }); }).slice(0, 6) : [];
  var quick = ['pierrot', 'yar', 'typo', 'bamti', 'luckyvicky', 'wegovy'].map(function (id) { return BY_ID[id]; });
  var summary = m.name + ' — ' + b.name + '에 → ' + j.label + ' (어울림 ' + j.score + '점)\n' + reasonsOf(j).join('\n') + '\n쓸 수 있는 기간 ' + j.life.label + ' · 제작 ' + leadLabel(S.lead) + '\n— 트렌드 통역 · 예시 데이터';
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">써도 될까?</span><h1 class="h1">이 밈, 우리가 써도 돼요?</h1><p class="sub">회의 중에 누가 "이거 쓰자"고 할 때 바로 확인하세요.</p></div></header>' +
    '<div class="grid-2" style="align-items:start"><section class="card stack"><label class="field" for="ck-q">밈 이름<span class="search" style="height:48px">' + icon('search', 16) + '<input id="ck-q" data-in="checkQ" value="' + esc(C.query) + '" placeholder="예: 삐에로 밈, 야르, 밤티" style="font-size:16px"></span></label>' +
    (sugg.length && !(sugg.length === 1 && sugg[0].id === m.id && sugg[0].name === q) ? '<div class="stack" style="gap:0">' + sugg.map(function (x) { return '<button class="btn" style="justify-content:space-between;border:none;border-top:1px solid var(--line);border-radius:0;height:44px" data-act="checkPick" data-arg="' + x.id + '"><span' + lang(x) + '>' + esc(x.name) + ' <span class="note">' + REGION_LABEL[x.region] + '</span></span>' + badge(J(x, b).v) + '</button>'; }).join('') + '</div>' : '') +
    (q && !sugg.length ? '<p class="note">"' + esc(q) + '"는 아직 모아 둔 밈에 없어요. <a href="#decoder">무슨 뜻이야?</a>에 문장째 넣어 보세요.</p>' : '') +
    '<div class="chips">' + quick.map(function (x) { return '<button class="chip" aria-pressed="' + (x.id === m.id) + '" data-act="checkPick" data-arg="' + x.id + '">' + esc(x.name) + '</button>'; }).join('') + '</div>' +
    '<div class="stack" style="gap:8px;border-top:1px solid var(--line);padding-top:12px"><span class="note" style="font-weight:600">우리 브랜드</span>' + brandLine() + '<div class="row"><span class="sub" style="font-size:12.5px">올리기까지 걸리는 시간</span>' + leadSeg() + '</div></div></section>' +
    '<section class="card stack" aria-live="polite"><span class="note" style="font-weight:600">' + esc(b.name) + ' 기준 · 제작 ' + leadLabel(S.lead) + '</span>' +
    '<div class="vbox ' + j.v + '" style="padding:18px"><b style="font-size:clamp(32px,6vw,48px);line-height:1.05">' + VERDICT[j.v].label + '</b><span style="font-size:13px">쓸 수 있는 기간 ' + esc(j.life.label) + ' · 게시 ' + leadLabel(S.lead) + ' 뒤 · 어울림 ' + j.score + '점</span></div>' +
    '<div class="stack" style="gap:4px"><span class="disp" style="font-size:34px"' + lang(m) + '>' + esc(m.name) + '</span><span class="sub">' + esc(m.gloss) + '</span><span class="note">' + esc(m.fmt || '') + ' · ' + esc(m.ages) + ' · ' + STAGE[m.stage].label + ' · 관심도 ' + m.w[11] + '</span></div>' +
    '<div class="stack" style="gap:6px"><b style="font-size:12.5px">왜 그런가요</b>' + reasonsOf(j).map(function (t, i) { var ok = j.v === 'go' && i === 0 || t.indexOf('좋은 점') === 0; return '<div class="row" style="flex-wrap:nowrap;align-items:flex-start;gap:8px;font-size:13.5px"><span class="safe-ic ' + (ok ? 'ok' : 'care') + '">' + icon(ok ? 'ok' : 'warn', 12) + '</span><span>' + esc(t) + '</span></div>'; }).join('') + '</div>' +
    axesHtml(j) + lifeHtml(j, S.lead) + fastLane(m, j, S.lead) +
    '<p class="sub" style="font-size:12.5px"><b style="color:var(--ink)">' + esc(DIFF[m.diff] || '') + '</b> — ' + esc(DIFF_HINT[m.diff] || '') + '</p>' +
    '<div class="row">' + (j.v !== 'no' && j.v !== 'late' ? '<button class="btn primary" style="flex:1" data-act="planWith" data-arg="' + m.id + '">이 밈으로 기획하기</button>' : '<a class="btn" style="flex:1" href="#radar">대신 쓸 밈 찾기</a>') +
    '<button class="btn" data-act="copy" data-text="' + esc(summary) + '" data-ok="결과를 복사했어요">' + icon('copy', 14) + ' 팀에 공유</button><a class="btn" href="#meme-' + m.id + '">자세히</a></div></section></div>';
};
ACT.checkPick = function (id) { S.check.sel = id; S.check.query = BY_ID[id].name; render(); };
IN.checkQ = function (v) { S.check.query = v; var exact = ALL.filter(function (x) { return x.name === v.trim(); })[0]; if (exact) S.check.sel = exact.id; render(); };

// ---------- 내 기획안 ----------
PAGES.plans = function () {
  var rows = S.plans;
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">내 기획안</span><h1 class="h1">저장한 기획안 ' + rows.length + '개</h1><p class="sub">스튜디오에서 저장한 기획안의 상태를 바꾸고, 밈이 아직 살아 있는지 다시 확인하세요.</p></div><button class="btn primary" data-act="planWith" data-arg="">새 기획안</button></header>' +
    '<section class="card">' + (rows.length ? '<div class="table-wrap"><table class="t"><thead><tr><th>기획안</th><th>밈 · 지금도 써도 될까</th><th>브랜드</th><th>상태</th><th>게시</th><th></th></tr></thead><tbody>' + rows.map(function (p) {
      var m = BY_ID[p.memeId], b = S.brands.filter(function (x) { return x.id === p.brandId; })[0] || brand(), j = m ? J(m, b) : null;
      var confirm = S.plansUi.confirm === p.id;
      return '<tr><td><b>' + esc(p.title) + '</b>' + (p.sample ? ' <span class="tag-ex">예시</span>' : '') + '</td><td>' + (m ? memeLink(m) + ' ' + badge(j.v) + (j.v === 'late' || j.v === 'no' ? '<br><span class="note" style="color:var(--red-ink)">지금은 쓰지 않는 게 좋아요</span>' : '') : '') + '</td><td class="sub">' + esc(b.name) + '</td>' +
        '<td><label class="sr" for="st-' + p.id + '">상태</label><select class="select" id="st-' + p.id + '" data-ch="planStatus" data-arg="' + p.id + '" style="height:34px;width:auto">' + PLAN_STATUS.map(function (s) { return '<option' + (s === p.status ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select></td>' +
        '<td class="mono">' + esc(p.due) + '</td><td style="text-align:right;white-space:nowrap">' + (confirm ? '<span class="note">정말 지울까요?</span> <button class="btn sm" data-act="planDel" data-arg="' + p.id + '" style="color:var(--red)">지우기</button> <button class="btn sm" data-act="planCancel">취소</button>' : '<button class="btn sm" data-act="planWith" data-arg="' + esc(p.memeId) + '">다시 열기</button> <button class="btn sm" data-act="planAsk" data-arg="' + p.id + '">삭제</button>') + '</td></tr>';
    }).join('') + '</tbody></table></div>' : emptyState('저장한 기획안이 없어요', '스튜디오에서 밈을 골라 첫 기획안을 만들어 보세요.', 'goStudio', '스튜디오로 가기')) + '</section>';
};
IN.planStatus = function (v, el) { var p = S.plans.filter(function (x) { return x.id === el.getAttribute('data-arg'); })[0]; if (p) { p.status = v; persist(); toast('상태를 "' + v + '"로 바꿨어요'); render(); } };
ACT.planAsk = function (id) { S.plansUi.confirm = id; render(); };
ACT.planCancel = function () { S.plansUi.confirm = null; render(); };
ACT.planDel = function (id) { S.plans = S.plans.filter(function (p) { return p.id !== id; }); S.plansUi.confirm = null; persist(); toast('기획안을 지웠어요'); render(); };
ACT.goStudio = function () { go('studio'); };

// ---------- 브랜드 설정 ----------
PAGES.settings = function () {
  var ST = S.settings, editId = ST.edit || S.brandId, d = ST.draft && ST.draft.id === editId ? ST.draft : clone(S.brands.filter(function (b) { return b.id === editId; })[0] || S.brands[0]);
  ST.draft = d;
  var list = S.brands.map(function (b) {
    return '<button class="btn" style="justify-content:space-between;height:auto;padding:12px 14px;text-align:left;' + (b.id === editId ? 'border-color:var(--ink);background:var(--hl-soft)' : '') + '" data-act="setEdit" data-arg="' + b.id + '"><span class="stack" style="gap:2px"><b>' + esc(b.name) + '</b><span class="note">' + esc(b.kind) + ' · ' + esc(b.ages.join('·')) + ' · ' + esc(b.tone) + '</span></span>' + (b.id === S.brandId ? '<span class="badge v-go">지금 쓰는 중</span>' : '') + '</button>';
  }).join('');
  var preview = MEMES.KR.map(function (m) { return { m: m, j: judge(m, d, S.lead) }; }).filter(function (x) { return x.j.v === 'go'; }).sort(function (a, c) { return c.j.score - a.j.score; }).slice(0, 5);
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">우리 브랜드 설정</span><h1 class="h1">우리 브랜드를 알려 주세요</h1><p class="sub">분야, 타깃 나이대, 말투를 알려 주면 어떤 밈을 써도 되는지 그에 맞춰 골라 드려요.</p></div></header>' +
    '<div class="grid-3" style="grid-template-columns:280px minmax(0,1fr) minmax(0,.8fr);align-items:start"><section class="stack">' + list + '<button class="btn" data-act="addBrand">+ 브랜드 추가</button>' +
    (ST.confirmReset ? '<div class="vbox care"><span style="font-size:13px">예시 브랜드 3개로 되돌릴까요? 추가한 브랜드는 사라져요.</span><div class="row"><button class="btn sm" data-act="resetBrands">되돌리기</button><button class="btn sm" data-act="cancelReset">취소</button></div></div>' : '<button class="btn sm" style="align-self:flex-start;border:none;color:var(--ink-3)" data-act="askReset">예시 브랜드로 되돌리기</button>') + '</section>' +
    '<section class="card stack" style="gap:16px"><h2 class="h3">' + esc(d.name || '새 브랜드') + ' 편집</h2>' +
    '<label class="field" for="b-name">브랜드·상품 이름<input class="input" id="b-name" data-in="bName" value="' + esc(d.name) + '"></label>' +
    '<label class="field" for="b-cat">분야<select class="select" id="b-cat" data-ch="bCat">' + CAT_OPTIONS.map(function (c) { return '<option value="' + c.id + '"' + (c.id === d.cat ? ' selected' : '') + '>' + c.label + '</option>'; }).join('') + '</select></label>' +
    '<fieldset class="field" style="border:none;padding:0;margin:0"><legend style="margin-bottom:6px">타깃 나이대</legend><div class="chips">' + AGE_OPTIONS.map(function (a) { return '<button class="chip" aria-pressed="' + (d.ages.indexOf(a) >= 0) + '" data-act="bAge" data-arg="' + a + '">' + a + '</button>'; }).join('') + '</div></fieldset>' +
    '<label class="field" for="b-tone">말투<select class="select" id="b-tone" data-ch="bTone">' + Object.keys(TONE_VOICES).map(function (t) { return '<option' + (t === d.tone ? ' selected' : '') + '>' + t + '</option>'; }).join('') + '</select><span class="hint">말투에 따라 쓸 수 있는 밈이 달라져요 (' + TONE_VOICES[d.tone].map(function (v) { return { wholesome: '순함', playful: '장난', edgy: '날 섬' }[v]; }).join(' · ') + ')</span></label>' +
    '<div class="row"><button class="btn primary" data-act="saveBrand">저장</button><button class="btn" data-act="useBrand">저장하고 이 브랜드로 보기</button>' + (S.brands.length > 1 ? '<button class="btn" style="margin-left:auto;color:var(--red)" data-act="delBrand">삭제</button>' : '') + '</div></section>' +
    '<section class="card stack"><h2 class="h3">이 설정이면 지금 쓰기 좋은 밈</h2><p class="note">저장 전 미리보기 · 제작 ' + leadLabel(S.lead) + ' 기준</p>' + (preview.length ? preview.map(function (x) { return '<div class="row" style="justify-content:space-between;border-top:1px solid var(--line);padding-top:10px;flex-wrap:nowrap">' + memeLink(x.m, 'lib-name') + '<span class="mono note">' + x.j.score + '</span></div>'; }).join('') : '<p class="sub" style="font-size:13px">지금 쓰기 좋은 밈이 없어요. 타깃 나이대를 넓히거나 말투를 바꿔 보세요.</p>') + '</section></div>' +
    '<section class="card row" style="justify-content:space-between"><span class="stack" style="gap:2px"><b>화면 테마</b><span class="note">시스템 설정을 따르거나 직접 고를 수 있어요</span></span><div class="seg">' + [[null, '시스템'], ['light', '밝게'], ['dark', '어둡게']].map(function (t) { return '<button aria-pressed="' + (S.theme === t[0]) + '" data-act="setTheme" data-arg="' + (t[0] || '') + '">' + t[1] + '</button>'; }).join('') + '</div></section>';
};
function draft() { return S.settings.draft; }
IN.bName = function (v) { draft().name = v; };
IN.bCat = function (v) { var d = draft(); d.cat = v; d.kind = CAT_OPTIONS.filter(function (c) { return c.id === v; })[0].label; render(); };
IN.bTone = function (v) { var d = draft(); d.tone = v; d.voices = TONE_VOICES[v]; render(); };
ACT.bAge = function (a) { var d = draft(), i = d.ages.indexOf(a); if (i >= 0) { if (d.ages.length > 1) d.ages.splice(i, 1); else toast('타깃 나이대는 하나 이상 골라야 해요'); } else { d.ages.push(a); d.ages.sort(); } render(); };
ACT.setEdit = function (id) { S.settings.edit = id; S.settings.draft = null; render(); };
ACT.saveBrand = function (arg, el, e, use) {
  var d = draft(); if (!d.name.trim()) { toast('이름을 입력해 주세요'); return; }
  var i = S.brands.map(function (b) { return b.id; }).indexOf(d.id);
  if (i >= 0) S.brands[i] = clone(d); else S.brands.push(clone(d));
  if (use) S.brandId = d.id;
  persist(); toast(use ? '저장했어요. 이제 ' + d.name + ' 기준으로 추천해요' : '저장했어요'); render();
};
ACT.useBrand = function () { ACT.saveBrand(null, null, null, true); };
ACT.addBrand = function () { var id = 'b' + Date.now(); S.settings.edit = id; S.settings.draft = { id: id, name: '새 브랜드', kind: '음식·음료', cat: 'food', ages: ['20대'], region: 'KR', tone: '친근하게', voices: TONE_VOICES['친근하게'] }; render(); var el = document.getElementById('b-name'); if (el) { el.focus(); el.select(); } };
ACT.delBrand = function () { var id = draft().id; S.brands = S.brands.filter(function (b) { return b.id !== id; }); if (S.brandId === id) S.brandId = S.brands[0].id; S.settings.edit = null; S.settings.draft = null; persist(); toast('브랜드를 지웠어요'); render(); };
ACT.askReset = function () { S.settings.confirmReset = true; render(); };
ACT.cancelReset = function () { S.settings.confirmReset = false; render(); };
ACT.resetBrands = function () { S.brands = clone(DEFAULT_BRANDS); S.brandId = 'latte'; S.settings = { edit: null, draft: null, confirmReset: false }; persist(); toast('예시 브랜드로 되돌렸어요'); render(); };
ACT.setTheme = function (t) { S.theme = t || null; applyTheme(); persist(); render(); };

// ---------- 밈 해석기 ----------
function decode(text) {
  var found = [];
  ALL.forEach(function (m) {
    var forms = [m.name].concat(ALIASES[m.id] || []);
    forms.forEach(function (f) { var i = text.indexOf(f); if (i >= 0) found.push({ m: m, form: f, i: i }); });
  });
  var re = /([가-힣]{1,4})삐(?![가-힣]*에로)/g, mm;
  while ((mm = re.exec(text))) { if (!found.some(function (f) { return f.i === mm.index; })) found.push({ m: BY_ID.pierrot, form: mm[0], i: mm.index }); }
  found.sort(function (a, c) { return a.i - c.i || c.form.length - a.form.length; });
  var out = [], end = -1;
  found.forEach(function (f) { if (f.i >= end) { out.push(f); end = f.i + f.form.length; } });
  return out;
}
PAGES.decoder = function () {
  var t = S.decoder.text, hits = decode(t), b = brand();
  var marked = '', last = 0;
  hits.forEach(function (h) { marked += esc(t.slice(last, h.i)) + '<mark style="background:var(--hl);color:var(--on-hl);padding:0 2px;border-radius:3px">' + esc(h.form) + '</mark>'; last = h.i + h.form.length; });
  marked += esc(t.slice(last));
  var plain = '', l2 = 0;
  hits.forEach(function (h) { plain += esc(t.slice(l2, h.i)) + '<b style="border-bottom:2px solid var(--blue)">' + esc(PLAIN[h.m.id] || (h.m.id === 'pierrot' ? h.form.replace('삐', ' 삐에로') : h.m.name)) + '</b>'; l2 = h.i + h.form.length; });
  plain += esc(t.slice(l2));
  var uniq = []; hits.forEach(function (h) { if (!uniq.some(function (u) { return u.m.id === h.m.id; })) uniq.push(h); });
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">무슨 뜻이야?</span><h1 class="h1">댓글·문장 속 밈을 찾아 풀어 드려요</h1><p class="sub">고객 댓글이나 받은 메시지를 붙여 넣으면 사전과 대조해 밈을 찾아요.</p></div></header>' +
    '<div class="grid-2" style="align-items:start"><section class="card stack"><label class="field" for="dc">문장<textarea class="textarea" id="dc" rows="5" data-in="decText">' + esc(t) + '</textarea></label><div class="row"><button class="btn sm" data-act="decSample">예시 문장</button><button class="btn sm" data-act="decClear">지우기</button><span class="note" style="margin-left:auto">' + t.length + '자</span></div>' +
    (hits.length ? '<div class="stack" style="gap:6px;border-top:1px solid var(--line);padding-top:12px"><span class="note" style="font-weight:600">찾은 곳</span><p style="font-size:15px;line-height:1.8">' + marked + '</p></div><div class="stack" style="gap:6px"><span class="note" style="font-weight:600">쉬운 말로 바꾸면 (사전 치환)</span><p style="font-size:15px;line-height:1.8">' + plain + '</p></div>' : '') + '</section>' +
    '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">찾은 밈 ' + uniq.length + '개</h2><span class="note">' + esc(b.name) + '에 써도 되는지 함께 봐요</span></div>' +
    (uniq.length ? uniq.map(function (h) { var j = J(h.m, b); return '<div class="stack" style="gap:6px;border-top:1px solid var(--line);padding-top:12px"><div class="row" style="justify-content:space-between">' + memeLink(h.m, 'lib-name') + badge(j.v) + '</div><span class="sub" style="font-size:13px">' + esc(h.m.gloss) + '</span><span class="note">문장 속 형태 "' + esc(h.form) + '" · ' + STAGE[h.m.stage].label + ' · ' + esc(h.m.ages) + '</span></div>'; }).join('')
      : emptyState('사전에서 찾은 밈이 없어요', '처음 보는 말이면 AI가 뜻을 조사하고 사람이 확인해 추가해요.')) + '</section></div>';
};
IN.decText = function (v) { S.decoder.text = v; render(); };
ACT.decSample = function () { S.decoder.text = DECODER_SAMPLE; render(); };
ACT.decClear = function () { S.decoder.text = ''; render(); var el = document.getElementById('dc'); if (el) el.focus(); };

// ---------- 지역 비교 ----------
PAGES.regions = function () {
  var b = brand();
  var col = function (r) {
    var list = MEMES[r].slice().sort(function (a, c) { return c.w[11] - a.w[11]; }).slice(0, 6);
    return '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">' + REGION_LABEL[r] + '</h2><span class="note">관심도 상위</span></div>' + list.map(function (m, i) {
      var p = pct(m.w, 4);
      return '<a href="#meme-' + m.id + '" style="display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none"><span class="mono muted">' + (i + 1) + '</span><span class="stack" style="gap:1px;min-width:0"><b' + lang(m) + ' style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(m.name) + '</b><span class="note">' + STAGE[m.stage].label + ' · ' + esc(m.fmt || '') + '</span></span><span class="mono ' + pctCls(p) + '" style="font-size:12.5px">' + fmtPct(p) + '</span></a>';
    }).join('') + '</section>';
  };
  return '<header class="page-head"><div class="stack" style="gap:6px"><span class="eyebrow">나라별 비교</span><h1 class="h1">나라마다 지금 뜨는 밈</h1><p class="sub">수집은 전 세계, 화면은 목표 지역 기준이에요. 지금은 한국·일본·글로벌을 보여 줘요.</p></div><span class="note" title="' + MORE_REGIONS + '">+8개 나라 준비 중</span></header>' +
    '<div class="grid-3">' + col('KR') + col('JP') + col('GLOBAL') + '</div>' +
    '<section class="card stack"><div class="card-head" style="margin:0"><h2 class="h3">나라를 건너는 밈</h2><span class="note">같은 주제가 다른 이름으로 퍼지는 경우</span></div><div class="grid-3">' + CROSS.map(function (c) {
      var a = BY_ID[c.from.id], z = BY_ID[c.to.id];
      return '<div class="stack" style="gap:8px;padding:14px;border-radius:12px;background:var(--surface-2)"><div class="row" style="gap:8px;flex-wrap:nowrap"><span class="stack" style="gap:1px;min-width:0"><span class="note">' + REGION_LABEL[c.from.region] + '</span>' + memeLink(a, 'lib-name') + '</span>' + icon('arrow', 16) + '<span class="stack" style="gap:1px;min-width:0"><span class="note">' + REGION_LABEL[c.to.region] + '</span>' + memeLink(z, 'lib-name') + '</span></div><span class="sub" style="font-size:13px">' + esc(c.note) + '</span>' +
        '<div class="row" style="gap:16px;color:var(--blue)"><span class="stack" style="gap:2px"><span class="note">' + esc(a.name) + '</span>' + spark(a.w, 90, 24) + '</span><span class="stack" style="gap:2px"><span class="note">' + esc(z.name) + '</span>' + spark(z.w, 90, 24) + '</span></div></div>';
    }).join('') + '</div></section>';
};
// ===== end pages =====
