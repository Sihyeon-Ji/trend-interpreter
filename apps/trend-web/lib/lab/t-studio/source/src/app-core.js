// ===== app core: state, router, helpers, shell =====
var LS_KEY = 'trend-tongyeok-web-v3';
var ALL = [];
(function () { ['KR', 'JP', 'GLOBAL'].forEach(function (r) { MEMES[r].forEach(function (m) { m.region = r; ALL.push(m); }); }); })();
var BY_ID = {}; ALL.forEach(function (m) { BY_ID[m.id] = m; });
var REGION_LABEL = { KR: '한국', JP: '일본', GLOBAL: '글로벌' };
var CAT_LABEL = {}; CATS.forEach(function (c) { CAT_LABEL[c.id] = c.label; });
var V_ORDER = ['go', 'watch', 'care', 'late', 'no'];

function clone(o) { return JSON.parse(JSON.stringify(o)); }
var DEFAULT_BRANDS = clone(BRANDS);

var S = {
  brands: clone(BRANDS), brandId: 'latte', lead: 14, watch: { yar: true, pierrot: true, typo: true, nanri: true },
  plans: clone(PLAN_SEED), theme: null,
  radar: { region: 'KR', period: '30d', cat: 'all', query: '', colorBy: 'verdict', off: {}, sel: null, rank: 'fit' },
  studio: { step: 1, mode: 'product', product: '', oneLiner: '', goal: '참여 (댓글·공유)', channels: { '릴스·쇼츠·틱톡': true }, shortsUrl: SHORTS.url, shortsKind: 'ref', photo: '', sel: null, pinned: null, phase: 'idle', loadStep: 0, ran: false, copied: null, prep: {}, approved: false, showExample: false, saved: false },
  lib: { region: 'all', verdict: 'all', stage: 'all', cat: 'all', sort: 'hot', query: '', page: 1 },
  meme: { hover: null, report: {} },
  check: { query: '삐에로 밈', sel: 'pierrot' },
  decoder: { text: DECODER_SAMPLE },
  report: { mail: false },
  settings: { edit: null, draft: null, confirmReset: false },
  plansUi: { confirm: null },
  sheet: false, search: false, searchQ: '', onboarded: true
};
(function load() {
  try {
    var raw = localStorage.getItem(LS_KEY); if (!raw) return;
    var p = JSON.parse(raw) || {};
    ['brands', 'brandId', 'lead', 'watch', 'plans', 'theme', 'onboarded'].forEach(function (k) { if (p[k] !== undefined && p[k] !== null) S[k] = p[k]; });
    if (!S.brands.length) S.brands = clone(BRANDS);
  } catch (e) {}
})();
function persist() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({ brands: S.brands, brandId: S.brandId, lead: S.lead, watch: S.watch, plans: S.plans, theme: S.theme, onboarded: S.onboarded })); } catch (e) {}
}
function brand() { return S.brands.filter(function (b) { return b.id === S.brandId; })[0] || S.brands[0]; }

// ---------- helpers ----------
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
function josa(word, a, b) { var ch = String(word).charCodeAt(String(word).length - 1); if (ch < 0xAC00 || ch > 0xD7A3) return b; return (ch - 0xAC00) % 28 ? a : b; }
function lang(m) { return m.lang ? ' lang="' + m.lang + '"' : ''; }
function badge(v) { return '<span class="badge v-' + v + '">' + VERDICT[v].short + '</span>'; }
function stageChip(stage) { return '<span class="stage">' + STAGE[stage].label + '</span>'; }
function pctCls(p) { return p === null || p > 0 ? 'up' : p < 0 ? 'down' : 'flat'; }
function arrow(p) { return p === null ? '' : p > 5 ? '▲ ' : p < -5 ? '▼ ' : ''; }
function periodObj() { return PERIODS.filter(function (p) { return p.id === S.radar.period; })[0]; }
function J(m, b, lead) { return judge(m, b || brand(), lead || S.lead); }
function spark(w, W, H, cls) {
  return '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" aria-hidden="true"><polyline points="' + sparkPoints(w, W, H, 2) + '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" class="' + (cls || '') + '"></polyline></svg>';
}
function areaChart(w, W, H) {
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" aria-hidden="true" style="color:var(--blue)"><polygon points="' + sparkArea(w, W, H, 3, 100) + '" fill="var(--blue-soft)"></polygon><polyline points="' + sparkPoints(w, W, H, 3, 100) + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></polyline></svg>';
}
function icon(name, size) {
  var s = size || 16;
  var P = {
    radar: '<circle cx="8" cy="8" r="6"/><path d="M8 8l4-3"/>', studio: '<rect x="2" y="3" width="12" height="10" rx="2"/><path d="M6.5 6v4l3.5-2z" fill="currentColor"/>',
    plans: '<path d="M4 2h6l3 3v9H4z"/><path d="M6.5 8.5h4M6.5 11h4"/>', report: '<path d="M3 13V8M8 13V3M13 13V6"/>',
    lib: '<path d="M3 3h3v10H3zM7 3h3v10H7zM11 4l2.5-.5 1.5 9.5-2.5.5z"/>', check: '<path d="M3 8.5l3 3L13 4"/>',
    decoder: '<path d="M2 4h12v7H6l-3 3v-3H2z"/>', regions: '<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12"/>',
    settings: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4"/>',
    search: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>', more: '<circle cx="3.5" cy="8" r="1"/><circle cx="8" cy="8" r="1"/><circle cx="12.5" cy="8" r="1"/>',
    heart: '<path d="M8 13.5s-5-3-5-7a2.8 2.8 0 015-1.7A2.8 2.8 0 0113 6.5c0 4-5 7-5 7z"/>', arrow: '<path d="M3 8h10M9 4l4 4-4 4"/>',
    back: '<path d="M13 8H3M7 4L3 8l4 4"/>', copy: '<rect x="5" y="5" width="8" height="9" rx="1.5"/><path d="M3 11V3.5C3 2.7 3.7 2 4.5 2H10"/>',
    moon: '<path d="M12.5 10A5.5 5.5 0 016 3.5a5.5 5.5 0 106.5 6.5z"/>', close: '<path d="M4 4l8 8M12 4l-8 8"/>',
    up: '<path d="M2 11l4-4 2 2 5-5"/>', down: '<path d="M2 5l4 4 2-2 5 5"/>', turn: '<path d="M2 10l4-5 4 3 3-4"/>', peak: '<path d="M2 12L8 3l6 9"/>', flat: '<path d="M2 8h12"/>',
    ok: '<path d="M3 7.5l2.5 2.5L11 4"/>', warn: '<path d="M7 3v5M7 10.5v.5"/>', photo: '<rect x="2" y="3" width="12" height="10" rx="2"/><circle cx="6" cy="7" r="1.4"/><path d="M3 12l3.5-3 2.5 2 2.5-2.5L14 11"/>'
  };
  return '<svg width="' + s + '" height="' + s + '" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (P[name] || '') + '</svg>';
}
function axesHtml(j) {
  return '<div class="axes">' + [['지금 뜨는 정도', j.timing], ['우리 타깃이 쓰나', j.target], ['분야·말투와 맞나', j.fit]].map(function (a) {
    return '<div class="axis"><span class="sub">' + a[0] + '</span><span class="bar"><i class="' + (a[1] >= 70 ? '' : a[1] >= 50 ? 'mid' : 'low') + '" style="width:' + a[1] + '%"></i></span><span class="mono" style="text-align:right">' + a[1] + '</span></div>';
  }).join('') + '</div>';
}
function lifeHtml(j, lead) {
  var life = j.life, scale = 42;
  var d = life.days === null ? 14 : Math.min(life.days, scale);
  var over = life.days !== null && life.days < lead;
  var lp = Math.min(100, lead / scale * 100);
  return '<div class="life"><div class="row" style="justify-content:space-between;font-size:12.5px"><span class="sub">쓸 수 있는 기간</span><b>' + esc(life.label) + '</b></div>' +
    '<div class="life-track"><div class="t"></div><div class="f ' + (life.days === null ? 'unknown' : over ? 'over' : '') + '" style="width:' + (life.days === 0 ? 0 : d / scale * 100) + '%"></div>' +
    '<div class="m ' + (over || life.days === 0 ? 'over' : '') + '" style="left:calc(' + lp + '% - 1px)"></div><span class="mt ' + (over || life.days === 0 ? 'over' : '') + '" style="left:' + lp + '%">게시 ' + leadLabel(lead) + ' 뒤</span></div>' +
    '<div class="life-scale"><span>오늘</span><span>2주</span><span>4주</span><span>6주+</span></div></div>';
}
function reasonsOf(j) {
  var out = [];
  if (j.v === 'go' && j.plus.length) out.push(j.plus.join(' · '));
  j.why.forEach(function (w) { out.push(w); });
  if (j.v !== 'go' && j.plus.length) out.push('좋은 점 · ' + j.plus.join(' · '));
  return out;
}
function vboxHtml(j, big) {
  return '<div class="vbox ' + j.v + '"><div class="vl"><b style="' + (big ? 'font-size:26px' : '') + '">' + VERDICT[j.v].label + '</b><span class="mono" style="font-size:13px">어울림 ' + j.score + '점' + '</span></div>' +
    reasonsOf(j).map(function (t) { return '<span style="font-size:13px;line-height:1.5">' + esc(t) + '</span>'; }).join('') + '</div>';
}
function fastLane(m, j, lead) {
  if (!(j.life.days !== null && j.life.days < lead && j.v === 'care')) return '';
  return '<div class="vbox care" style="background:var(--surface-2)"><b style="font-size:13px">빨리 가는 안</b><span style="font-size:13px;line-height:1.5;color:var(--ink-2)">쓸 수 있는 기간이 ' + esc(j.life.label) + '예요. 제작 ' + leadLabel(lead) + '짜리 영상은 늦어요. 기존 영상에 자막만 얹는 3일짜리 안으로 가세요.</span>' +
    '<button class="btn sm" style="align-self:flex-start" data-act="setLead" data-arg="3">3일 안에 올린다면?</button></div>';
}
function brandSeg(act) {
  return '<div class="seg" role="group" aria-label="우리 브랜드">' + S.brands.map(function (b) {
    return '<button type="button" aria-pressed="' + (b.id === S.brandId) + '" data-act="' + (act || 'setBrand') + '" data-arg="' + esc(b.id) + '">' + esc(b.name) + '</button>';
  }).join('') + '</div>';
}
function brandSelect(id, compact) {
  return '<label class="ws' + (compact ? ' compact' : '') + '" for="' + id + '"><span class="note">우리 브랜드</span><select class="select" id="' + id + '" data-ch="wsBrand">' +
    S.brands.map(function (b) { return '<option value="' + esc(b.id) + '"' + (b.id === S.brandId ? ' selected' : '') + '>' + esc(b.name) + '</option>'; }).join('') +
    '<option value="__new">+ 새 브랜드 추가</option></select></label>';
}
function brandLine() {
  var b = brand();
  return '<span class="note"><b style="color:var(--ink)">' + esc(b.name) + '</b> 기준 · ' + esc(b.kind) + ' · ' + esc(b.ages.join('·')) + ' · ' + esc(b.tone) + '</span>';
}
function leadSeg() {
  return '<div class="seg" role="group" aria-label="올리기까지 걸리는 시간">' + LEADS.map(function (l) {
    return '<button type="button" aria-pressed="' + (l.days === S.lead) + '" data-act="setLead" data-arg="' + l.days + '">' + l.label + '</button>';
  }).join('') + '</div>';
}
function facts(pairs, style) { return '<dl class="facts"' + (style ? ' style="' + style + '"' : '') + '>' + pairs.map(function (p) { return '<div class="fact"><dt>' + p[0] + '</dt><dd>' + p[1] + '</dd></div>'; }).join('') + '</dl>'; }
function memeLink(m, cls) { return '<a href="#meme-' + m.id + '" class="' + (cls || '') + '"' + lang(m) + '>' + esc(m.name) + '</a>'; }
function emptyState(title, body, btnAct, btnLabel) {
  return '<div class="stack" style="align-items:center;text-align:center;padding:36px 16px;gap:8px"><b style="font-size:15px">' + esc(title) + '</b><span class="sub" style="font-size:13px">' + esc(body) + '</span>' +
    (btnAct ? '<button class="btn sm" data-act="' + btnAct + '">' + esc(btnLabel) + '</button>' : '') + '</div>';
}
var toastT = null;
function toast(msg) {
  var el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(function () { el.hidden = true; }, 2200);
}
function copyText(text, okMsg) {
  var done = function () { toast(okMsg || '복사했어요'); };
  var fallback = function () {
    try { var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); done(); }
    catch (e) { toast('복사가 막혀 있어요. 글을 직접 선택해 주세요'); }
  };
  try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback); else fallback(); } catch (e) { fallback(); }
}

// ---------- routes ----------
var NAV = [
  { id: 'radar', label: '이번 주 트렌드', icon: 'radar', group: 'work' },
  { id: 'studio', label: '콘텐츠 스튜디오', icon: 'studio', group: 'work' },
  { id: 'library', label: '밈 사전', icon: 'lib', group: 'find' },
  { id: 'regions', label: '나라별 비교', icon: 'regions', group: 'find' },
  { id: 'decoder', label: '무슨 뜻이야?', icon: 'decoder', group: 'find' },
  { id: 'check', label: '써도 될까?', icon: 'check', group: 'find' },
  { id: 'plans', label: '내 기획안', icon: 'plans', group: 'keep', count: function () { return S.plans.length; } },
  { id: 'report', label: '주간 리포트', icon: 'report', group: 'keep' },
  { id: 'settings', label: '우리 브랜드 설정', icon: 'settings', group: 'foot' }
];
var TITLES = { radar: '이번 주 트렌드', studio: '콘텐츠 스튜디오', plans: '내 기획안', report: '주간 리포트', library: '밈 사전', check: '써도 될까?', decoder: '무슨 뜻이야?', regions: '나라별 비교', settings: '우리 브랜드 설정', meme: '밈 자세히' };
function route() {
  var h = (location.hash || '').replace(/^#/, '');
  if (h.indexOf('meme-') === 0 && BY_ID[h.slice(5)]) return { name: 'meme', arg: h.slice(5) };
  if (TITLES[h] && h !== 'meme') return { name: h };
  return { name: 'radar' };
}
function go(hash) { if (location.hash === '#' + hash) render(true); else location.hash = hash; }

function shell() {
  var r = route(), cur = r.name === 'meme' ? 'library' : r.name;
  var navItem = function (n) {
    var c = n.count ? '<span class="count">' + n.count() + '</span>' : '';
    return '<a class="nav" href="#' + n.id + '"' + (n.id === cur ? ' aria-current="page"' : '') + '>' + icon(n.icon) + '<span>' + n.label + '</span>' + c + '</a>';
  };
  var rail = '<nav class="rail" aria-label="주요 메뉴">' +
    '<a class="brand" href="#radar"><span class="logo"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true"><circle cx="9" cy="9" r="6.5" stroke="#E3FF3B" stroke-width="1.6"></circle><circle cx="9" cy="9" r="2.5" fill="#E3FF3B"></circle></svg></span><span><b>트렌드 통역</b><small>마케터용 밈 트렌드 도구</small></span></a>' +
    brandSelect('ws-rail') + '<button class="btn" style="justify-content:flex-start;gap:8px;margin:0 2px 10px;color:var(--ink-3);font-weight:500" data-act="openSearch">' + icon('search', 14) + '<span>밈 찾기</span><span class="mono" style="margin-left:auto;font-size:11px">/</span></button>' +
    NAV.filter(function (n) { return n.group === 'work'; }).map(navItem).join('') +
    '<div class="nav-group">찾아보기</div>' + NAV.filter(function (n) { return n.group === 'find'; }).map(navItem).join('') +
    '<div class="nav-group">기록</div>' + NAV.filter(function (n) { return n.group === 'keep'; }).map(navItem).join('') +
    '<div class="rail-foot">' + NAV.filter(function (n) { return n.group === 'foot'; }).map(navItem).join('') +
    '<button class="theme-btn" data-act="toggleTheme"><span>화면 테마</span><span class="muted" style="font-size:12px">' + themeLabel() + '</span></button></div></nav>';
  var tabs = ['radar', 'studio', 'check', 'library'].map(function (id) { return NAV.filter(function (n) { return n.id === id; })[0]; });
  var tabbar = '<nav class="tabbar" aria-label="하단 메뉴">' + tabs.map(function (n) {
    return '<a href="#' + n.id + '"' + (n.id === cur ? ' aria-current="page"' : '') + '>' + icon(n.icon, 20) + '<span>' + ({radar:'트렌드',studio:'스튜디오',check:'써도 될까',library:'밈 사전'})[n.id] + '</span></a>';
  }).join('') + '<button type="button" data-act="openSheet" aria-label="더보기">' + icon('more', 20) + '<span>더보기</span></button></nav>';
  var top = '<header class="topbar"><a class="brand" href="#radar" style="padding:0"><span class="logo"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true"><circle cx="9" cy="9" r="6.5" stroke="#E3FF3B" stroke-width="1.6"></circle><circle cx="9" cy="9" r="2.5" fill="#E3FF3B"></circle></svg></span><span><b>트렌드 통역</b></span></a>' +
    brandSelect('ws-top', true) + '<div class="row" style="gap:4px"><button class="btn sm" data-act="openSearch" aria-label="밈 찾기">' + icon('search', 16) + '</button><button class="btn sm" data-act="toggleTheme" aria-label="화면 테마 바꾸기">' + icon('moon', 16) + '</button></div></header>';
  return '<div class="shell">' + rail + '<div style="flex:1;min-width:0;display:flex;flex-direction:column">' + top + '<main class="main" id="view"></main></div></div>' + tabbar + '<div id="overlay"></div>';
}
function themeLabel() { return S.theme === 'dark' ? '어둡게' : S.theme === 'light' ? '밝게' : '시스템'; }
function applyTheme() { var r = document.documentElement; if (S.theme) r.setAttribute('data-theme', S.theme); else r.removeAttribute('data-theme'); }

function overlayHtml() {
  var h = '';
  if (S.sheet) {
    h += '<div class="sheet-bg" data-act="closeSheet"></div><div class="sheet" role="dialog" aria-label="메뉴"><div class="row" style="justify-content:space-between;padding:0 4px 8px"><b>메뉴</b><button class="btn sm" data-act="closeSheet" aria-label="닫기">' + icon('close', 14) + '</button></div>' +
      NAV.filter(function (n) { return ['radar', 'studio', 'check', 'library'].indexOf(n.id) < 0; }).map(function (n) { return '<a class="nav" href="#' + n.id + '" data-act="closeSheet">' + icon(n.icon) + '<span>' + n.label + '</span></a>'; }).join('') +
      '<button class="theme-btn" data-act="toggleTheme"><span>화면 테마</span><span class="muted">' + themeLabel() + '</span></button></div>';
  }
  if (S.search) {
    var q = S.searchQ.trim();
    var hits = q ? ALL.filter(function (m) { return m.name.toLowerCase().indexOf(q.toLowerCase()) >= 0 || (ALIASES[m.id] || []).some(function (a) { return a.indexOf(q) >= 0; }) || m.gloss.indexOf(q) >= 0; }).slice(0, 8)
      : ALL.slice().sort(function (a, b) { return b.w[11] - a.w[11]; }).slice(0, 6);
    h += '<div class="sheet-bg" data-act="closeSearch"></div><div role="dialog" aria-label="밈 찾기" style="position:fixed;left:50%;top:calc(env(safe-area-inset-top,0px) + 10vh);transform:translateX(-50%);width:min(560px,calc(100% - 32px));z-index:52;background:var(--surface);border-radius:14px;box-shadow:var(--shadow);border:1px solid var(--line);overflow:hidden">' +
      '<label class="search" style="border:none;border-bottom:1px solid var(--line);border-radius:0;height:52px;padding:0 16px">' + icon('search', 16) + '<span class="sr">밈 이름이나 뜻으로 찾기</span><input id="gsearch" data-in="searchQ" value="' + esc(S.searchQ) + '" placeholder="밈 이름이나 뜻으로 찾기 · 예: 야르, 삐" autocomplete="off"></label>' +
      '<div style="max-height:60vh;overflow:auto;padding:6px">' + (q ? '' : '<div class="note" style="padding:6px 10px">지금 관심도가 높은 밈</div>') +
      (hits.length ? hits.map(function (m) { var j = J(m); return '<a href="#meme-' + m.id + '" data-act="closeSearch" style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px;border-radius:9px;color:var(--ink);text-decoration:none" class="hov-row"><span style="min-width:0"><b class="disp" style="font-size:16px"' + lang(m) + '>' + esc(m.name) + '</b> <span class="muted" style="font-size:12px">' + REGION_LABEL[m.region] + '</span><br><span class="sub" style="font-size:12.5px">' + esc(m.gloss) + '</span></span>' + badge(j.v) + '</a>'; }).join('')
        : '<div class="note" style="padding:16px 10px">"' + esc(q) + '"에 맞는 밈이 없어요. "무슨 뜻이야?"에 문장째 넣어 보세요.</div>') + '</div></div>';
  }
  return h;
}

// ---------- render ----------
var PAGES = {};
var SUPPRESS_RENDER = false;
function onboardBanner() {
  if (S.onboarded) return '';
  return '<div class="card row" role="note" style="justify-content:space-between;background:var(--hl-soft);border-color:var(--ink)"><span style="font-size:13.5px"><b>지금은 예시 브랜드 \'' + esc(brand().name) + '\'로 보고 있어요.</b> 우리 브랜드를 알려 주면 모든 추천이 우리에게 맞게 바뀌어요.</span>' +
    '<span class="row"><button class="btn sm primary" data-act="onboardGo">우리 브랜드 넣기</button><button class="btn sm" data-act="onboardSkip">예시로 계속 보기</button></span></div>';
}
var lastRoute = null;
function render(isNav) {
  if (SUPPRESS_RENDER) return;
  var r = route();
  var focusId = document.activeElement && document.activeElement.id, selS = null, selE = null;
  try { if (focusId) { selS = document.activeElement.selectionStart; selE = document.activeElement.selectionEnd; } } catch (e) {}
  var key = r.name + ':' + (r.arg || '');
  var navigated = isNav || key !== lastRoute;
  var y = window.scrollY;
  document.getElementById('app').innerHTML = shell();
  lastRoute = key;
  var view = document.getElementById('view');
  view.innerHTML = (r.name === 'settings' ? '' : onboardBanner()) + PAGES[r.name](r.arg);
  document.getElementById('overlay').innerHTML = overlayHtml();
  document.title = (r.name === 'meme' ? BY_ID[r.arg].name + ' · 밈 자세히' : TITLES[r.name]) + ' · 트렌드 통역';
  afterRender();
  window.scrollTo(0, navigated ? 0 : y);
  if (focusId) { var el = document.getElementById(focusId); if (el) { el.focus({ preventScroll: true }); try { if (selS !== null) el.setSelectionRange(selS, selE); } catch (e) {} } }
}
var AFTER = [];
function afterRender() {
  AFTER.forEach(function (f) { try { f(); } catch (e) { console.error(e); } });
  var els = document.querySelectorAll('[data-act]:not(button):not(a):not(input):not(select):not(label)');
  for (var i = 0; i < els.length; i++) { if (!els[i].hasAttribute('tabindex')) els[i].setAttribute('tabindex', '0'); if (!els[i].hasAttribute('role')) els[i].setAttribute('role', 'button'); }
}
function set(patch) { for (var k in patch) S[k] = patch[k]; persist(); render(); }
function setIn(obj, patch) { for (var k in patch) S[obj][k] = patch[k]; render(); }

// ---------- events ----------
var ACT = {
  setBrand: function (id) { S.brandId = id; S.radar.sel = null; persist(); render(); },
  setLead: function (d) { S.lead = +d; persist(); render(); },
  toggleWatch: function (id) { S.watch[id] = !S.watch[id]; persist(); toast(S.watch[id] ? '관심 밈에 넣었어요' : '관심 밈에서 뺐어요'); render(); },
  toggleTheme: function () { S.theme = S.theme === null ? 'dark' : S.theme === 'dark' ? 'light' : null; applyTheme(); persist(); render(); },
  openSheet: function () { S.sheet = true; render(); },
  closeSheet: function () { S.sheet = false; render(); },
  openSearch: function () { S.search = true; S.searchQ = ''; render(); var el = document.getElementById('gsearch'); if (el) el.focus(); },
  closeSearch: function () { S.search = false; render(); },
  planWith: function (id) { S.studio.pinned = id || null; S.studio.step = 1; S.studio.ran = false; S.studio.sel = null; S.studio.phase = 'idle'; go('studio'); },
  copy: function (arg, el) { copyText(el.getAttribute('data-text') || arg, el.getAttribute('data-ok') || '복사했어요'); }
};
var IN = { searchQ: function (v) { S.searchQ = v; render(); },
  wsBrand: function (v) { if (v === '__new') { go('settings'); setTimeout(function () { ACT.addBrand(); }, 0); return; } S.brandId = v; S.radar.sel = null; S.onboarded = true; persist(); toast(brand().name + ' 기준으로 바꿨어요'); render(); } };
ACT.onboardGo = function () { S.onboarded = true; persist(); go('settings'); };
ACT.onboardSkip = function () { S.onboarded = true; persist(); render(); };
document.addEventListener('click', function (e) {
  var t = e.target.closest('[data-act]');
  if (!t) return;
  var fn = ACT[t.getAttribute('data-act')];
  if (!fn) return;
  if (t.tagName === 'A' && t.getAttribute('href')) { fn(t.getAttribute('data-arg'), t, e); return; }
  e.preventDefault();
  fn(t.getAttribute('data-arg'), t, e);
});
document.addEventListener('input', function (e) {
  var t = e.target.closest('[data-in]'); if (!t) return;
  var fn = IN[t.getAttribute('data-in')]; if (!fn) return;
  SUPPRESS_RENDER = !!e.isComposing;          // 한글 조합 중에는 다시 그리지 않는다 (조합이 끊겨 자모가 흩어짐)
  try { fn(t.type === 'checkbox' ? t.checked : t.value, t, e); } finally { SUPPRESS_RENDER = false; }
});
document.addEventListener('compositionend', function (e) {
  var t = e.target.closest && e.target.closest('[data-in]'); if (!t) return;
  var fn = IN[t.getAttribute('data-in')]; if (fn) fn(t.value, t, e);
});
document.addEventListener('change', function (e) {
  var t = e.target.closest('[data-ch]'); if (!t) return;
  var fn = IN[t.getAttribute('data-ch')]; if (fn) fn(t.type === 'checkbox' ? t.checked : t.value, t, e);
});
document.addEventListener('keydown', function (e) {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.getAttribute && e.target.getAttribute('role') === 'button' && e.target.hasAttribute('data-act')) { e.preventDefault(); e.target.dispatchEvent(new MouseEvent('click', { bubbles: true })); return; }
  if (e.key === 'Escape' && (S.search || S.sheet)) { S.search = false; S.sheet = false; render(); }
  var tag = (e.target.tagName || '').toLowerCase();
  if (e.key === '/' && tag !== 'input' && tag !== 'textarea' && tag !== 'select' && !S.search) { e.preventDefault(); ACT.openSearch(); }
  // 데모 녹화용: Alt+1~5 로 장면 순서대로 화면을 연다 (DEMO.md 의 장면 번호와 같다)
  if (e.altKey && DEMO_SCENES[e.key]) { e.preventDefault(); go(DEMO_SCENES[e.key]); }
});
var DEMO_SCENES = { '1': 'radar', '2': 'meme-yar', '3': 'studio', '4': 'regions', '5': 'decoder' };
window.addEventListener('hashchange', function () { S.search = false; S.sheet = false; render(true); });
var resizeT = null;
window.addEventListener('resize', function () { clearTimeout(resizeT); resizeT = setTimeout(afterRender, 150); });
// ===== end core =====
