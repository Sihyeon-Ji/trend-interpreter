"""5단계 추적. 뉴스 제목·쇼츠 해석·트렌드 검색어에서 용어 언급을 주 단위로 세고, 생애주기 규칙으로 단계와 재검증 주기를 정한다."""
from __future__ import annotations

import itertools
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ..lifecycle import RECENT_DAYS, diffusion, interest_stage, recency_stage, stage as life_stage
from ..schemas import Evidence, NewsItem, ShortsInterpretation, ShortsVideo
from ..storage import dictionary_store as ds
from .collect import home_edition
from ..verification import reference_doc
from .match import CUES, evidence_mentions, mentions, mostly_offtopic, numeric_like, same_term, term_pattern
from .runs import stage
from ..storage.db import Connection

WEEKS = 12


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _week(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


# 쓰임을 실제로 관측한 근거만 센다. 위키·웹은 설명 문서이고, 데이터랩은 지수라 '언급' 이 아니다.
# 네이버 검색 결과는 약관상 표시 전용이라 신호로도 쓰지 않는다.
USAGE_KINDS = ("community", "news", "short")
MIXED_ON_MIN = 3        # 딴 이야기가 더 많은 말은 그 뜻으로 쓰인 근거가 이만큼 있고
MIXED_ON_SHARE_DEN = 3  # 전체 분류의 1/3 이상일 때만 그 마지막 때로 생애주기를 정한다. 아니면 판단 보류


def _evidences(con: Connection, term_id: str) -> list[Evidence]:
    """이 표제어의 근거 가운데 표제어가 실제로 든 것만 — 검색이 끌어온 딴 글은 쓰임도 문서도 아니다(match.evidence_mentions)."""
    t = ds.get_term(con, term_id)
    if not t:
        return []
    evs = (Evidence.model_validate_json(j) for (j,) in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,)).fetchall())
    return [e for e in evs if evidence_mentions(e, t.canonical, t.aliases)]


def evidence_weeks(con: Connection, term_id: str) -> Counter:
    """조사가 모은 근거를 관측한 주에 센다. 이게 빠져서 근거 50건짜리 표제어도 언급 0 → unknown 이었다
    (2026-09-28 표본 30개 전부. Plan 02)."""
    c: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    for e in _evidences(con, term_id):
        if e.kind not in USAGE_KINDS or e.source_domain.startswith("naver"):
            continue
        w = _week(e.observed_at.date())
        if (e.url, w) in seen:
            continue
        seen.add((e.url, w))
        c[w] += 1
    return c


def usage_kinds(con: Connection, term_id: str) -> dict[str, int]:
    """쓰임 근거를 종류별로 센다(네이버 표시 전용 결과 제외). 확산 단계 판정에 쓴다.
    'documented' 는 참고 문서 근거 수 — 쓰임은 아니지만 자리 잡은 말인지 가른다. 참고 문서는 사전 등재와 같은 규칙(ADR 0003,
    verification.reference_doc: 나무위키·위키백과·Know Your Meme·pixiv 백과사전·萌娘百科의 문서 주소). 위키백과·나무위키만 보던 때는
    Know Your Meme 문서가 있는 밈도 '태동' 이 될 수 있었다. 홈페이지 주소나 나무위키 실시간 검색어(datalab)는 문서가 아니다."""
    c: Counter = Counter()
    for e in _evidences(con, term_id):
        if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver"):
            c[e.kind] += 1
        elif reference_doc(e):
            c["documented"] += 1
    return dict(c)


def newest_usage(con: Connection, term_id: str, on_topic: dict[str, tuple[str, str]] | None = None) -> datetime | None:
    """조사가 찾은 쓰임 근거 중 가장 최근 관측 시각. on_topic(근거 문장 분류)을 주면 그 뜻으로 쓰였다고 분류된 근거만 본다."""
    newest = None
    for e in _evidences(con, term_id):
        if on_topic is not None and on_topic.get(e.evidence_id, ("offtopic",))[0] == "offtopic":
            continue
        if e.kind in USAGE_KINDS and not e.source_domain.startswith("naver"):
            at = e.observed_at if e.observed_at.tzinfo else e.observed_at.replace(tzinfo=timezone.utc)
            newest = at if newest is None or at > newest else newest
    return newest


TITLE_SEP = "\x00"


class TitleIndex:
    """뉴스 제목을 한 덩어리로 이어 표기 패턴을 표기마다 한 번만 돌린다. 제목마다 mentions() 를 부르면 1만여 개 표제어 × 6만여 제목이라
    재계산이 40분 걸렸다(10-05). 구분자 \\x00 은 공백도 영문·숫자도 아니어서 표기 패턴이 제목 경계를 넘어 맞지 않으므로 답은 mentions() 와 같다."""

    def __init__(self, titles: list[str]):
        self.titles = titles
        self.joined = not any(TITLE_SEP in t for t in titles)
        self.text = TITLE_SEP.join(titles)
        self.starts = list(itertools.accumulate((len(t) + 1 for t in titles[:-1]), initial=0))

    def matching(self, term: str, aliases: list[str] | tuple[str, ...]) -> list[int]:
        """mentions(title, term, aliases) 가 참인 제목의 번호들, 오름차순."""
        if not self.joined:
            return [i for i, title in enumerate(self.titles) if mentions(title, term, aliases)]
        hits: dict[int, list[str]] = {}
        for c in (term, *aliases):
            if not c or not c.strip():
                continue
            for m in term_pattern(c).finditer(self.text):
                hits.setdefault(bisect_right(self.starts, m.start()) - 1, []).append(c)
        return sorted(i for i, hit in hits.items() if not all(numeric_like(c) for c in hit) or CUES.search(self.titles[i]))


class Sources:
    """주간 언급을 셀 원본을 한 번만 읽어 둔다 – 표제어마다 뉴스 전체를 다시 읽고 JSON 을 풀었다."""

    def __init__(self, con: Connection):
        self.news = [NewsItem.model_validate_json(j) for (j,) in con.execute("SELECT json FROM news").fetchall()]
        self.titles = TitleIndex([n.title for n in self.news])
        self.shorts = [(ShortsInterpretation.model_validate_json(j), vj, created) for j, vj, created in con.execute(
            "SELECT i.json, v.json, i.created_at FROM interpretations i LEFT JOIN videos v ON v.video_id=i.video_id").fetchall()]
        self.queries: dict[str, list[tuple[str, str]]] = {}
        for t, d, region in con.execute("SELECT term, date, region FROM trend_queries").fetchall():
            self.queries.setdefault(_norm(t), []).append((d, region))


def weekly_counts(con: Connection, term: str, aliases: list[str], term_id: str | None = None,
                  by_region: dict[str, Counter] | None = None, queried: Counter | None = None, home: str | None = None,
                  sources: Sources | None = None) -> Counter:
    """원본(뉴스 제목·쇼츠 해석·검색어)에서 주별 언급 수. by_region 을 주면 같은 한 번의 훑기로 나라별로도 센다(Plan 04).
    queried 를 주면 용어별 뉴스 검색(query 가 있는 뉴스)에서 온 것을 따로 센다 — 잰 주에만 몰리는 몫이다.
    home(표제어의 나라 판)을 주면 이 말을 다른 판에서 키워드로 잰 기사(영어의 SG·MY·PH, 중국어의 홍콩판)는 나라별 수에만 센다 — 전체 수와
    생애주기의 틀은 표제어의 나라 판이다. 돌아가며 재는 판을 전체에 넣으면 그 판을 잰 주에 '꾸준함' 이 '오르는 중' 으로 튀었다(검토 09-30)."""
    keys = {_norm(term), *(_norm(a) for a in aliases)}
    c: Counter = Counter()

    def add(week: str, region: str | None, total: bool = True) -> None:
        if total:
            c[week] += 1
        if by_region is not None and region:
            by_region.setdefault(region, Counter())[week] += 1

    src = sources or Sources(con)
    for i in src.titles.matching(term, aliases):
        n = src.news[i]
        d = (n.published_at or datetime.now(timezone.utc)).date()
        other = bool(home and n.query and n.region != home and _norm(n.query) in keys)
        add(_week(d), n.region, total=not other)
        if queried is not None and n.query and not other:
            queried[_week(d)] += 1
    for it, vj, created in src.shorts:
        if any(same_term(m.name, term, aliases) for m in it.memes):
            v = ShortsVideo.model_validate_json(vj) if vj else None
            # 영상 행은 30일 보존 뒤 지워진다 — 그때는 해석한 날로 둔다(오늘로 두면 옛 쇼츠가 매번 '이번 주' 언급이 됐다, 검토 2차). 나라는 모른다
            when = v.published_at.date() if v else (datetime.fromisoformat(created).date() if created else None)
            if when:
                add(_week(when), v.region if v else None)
    for key in keys:
        for d, region in src.queries.get(key, ()):
            add(_week(date.fromisoformat(d)), region)
    if term_id:
        c.update(evidence_weeks(con, term_id))
    return c


def interest_lifecycle(con: Connection, term_id: str, today: date) -> str:
    """검색 관심도(네이버 데이터랩 주별)가 있으면 그것으로, 없으면 위키 문서 월별 조회수(언어판을 합침)로. 덜 찬 이번 주·이번 달은 뺀다."""
    weekly = [(p, v) for p, v in ds.get_interest(con, term_id, "naver") if p < _week(today)]
    if weekly:
        st = interest_stage([v for _, v in weekly], "week")
        if st != "unknown":
            return st
    by_month: Counter = Counter()
    for m, v in ds.get_pageviews(con, term_id):
        if m < today.strftime("%Y%m"):
            by_month[m] += v
    return interest_stage([by_month[m] for m in sorted(by_month)][-24:], "month") if by_month else "unknown"


def measured_series(series: list[int], weeks: list[str], last_sampled: datetime) -> list[int]:
    """용어별 뉴스 검색으로 잰 주까지만 — 그 뒤의 0 은 '안 쓰임' 이 아니라 '안 봤음' 이다. 잰 주는 잰 날까지만 셌으므로 한 주로 늘려
    앞 주들과 견준다. 9일 전에 잰 推し活 [..,9,96,0,0] 이 '지는 중' 이 됐고(검토 3차), 매일 고르게 쓰이는 말도 이번 주 화요일에는
    이번 주 이틀 치가 지난주 이레 치보다 적어 '지는 중' 으로 읽혔다."""
    w = _week(last_sampled.date())
    if w not in weeks:
        return []
    cut = weeks.index(w)
    out = series[:cut + 1]
    days = min(7, (last_sampled.date() - date.fromisoformat(w)).days + 1)
    out[-1] = round(out[-1] * 7 / days)
    return out


def as_of_last_look(last_look: datetime | None, now: datetime) -> datetime:
    """'마지막으로 쓰인 때' 를 셀 기준 시각 — 조사가 마지막으로 근거를 찾아본 때(오래지 않았으면). 그 뒤로 찾아보지 않은 날을 '안 쓰임' 으로
    세면 다시 조사하기 전에 '꾸준함' 이 '지는 중' 으로 저절로 바뀌었다(검토 3차: 일본 '지금 쓰이는 밈' 12개 중 9개가 사흘 안에).
    마지막 조사가 RECENT_DAYS 의 두 배보다 오래됐으면 지금을 기준으로 — 그만큼 안 봤으면 식은 것으로 본다."""
    if last_look is None:
        return now
    last_look = last_look if last_look.tzinfo else last_look.replace(tzinfo=timezone.utc)
    return last_look if (now - last_look).days <= 2 * RECENT_DAYS else now


def run(con: Connection) -> dict:
    with stage(con, "track") as r:
        today = date.today()
        weeks = [_week(today - timedelta(weeks=i)) for i in range(WEEKS - 1, -1, -1)]
        n = 0
        # 뉴스 검색으로 언급을 마지막으로 잰 때. 재지 않은 주의 0 은 '안 쓰임' 이 아니라 '안 봤음' 이다 — 최근 두 주를 재지 않았으면
        # 모양(life_stage) 대신 마지막으로 쓰인 때(recency_stage)로 본다(검토 2차: 推し活 [...,9,96,0,0] 이 '지는 중' 이 됐다)
        sampled = {k: datetime.fromisoformat(v) for k, v in ds.mention_sampled(con).items() if v}
        queried = {q: datetime.fromisoformat(at) for q, at in con.execute(
            "SELECT query, MAX(first_seen) FROM news WHERE query IS NOT NULL GROUP BY query").fetchall() if q and at}
        sources = Sources(con)
        for t in ds.list_terms(con, ("verified", "needs_review", "researching")):
            by_region: dict[str, Counter] = {}
            query_hits: Counter = Counter()
            raw = weekly_counts(con, t.canonical, t.aliases, by_region=by_region, queried=query_hits, home=home_edition(t),
                                sources=sources)
            for region, at in ds.indicator_mentions(con, t.term_id):   # 근거로 넣지 않은 다른 판의 기사 — 나라별 수에만(Plan 04)
                by_region.setdefault(region, Counter())[_week(datetime.fromisoformat(at).date())] += 1
            # 주간 언급·마지막 본 때는 원본만. 조사 근거는 조사한 주에 몰려 '최근 조사한 것' 이 '요즘 뜨는 것' 으로
            # 보였다(2026-09-29 검토: 2017년 가즈아·날아다니는 스파게티 괴물이 '10대 유행어' 윗줄). 근거는 처음 본 때와
            # '마지막으로 쓰인 때'(recency_stage) 에만 쓴다.
            ds.set_weekly(con, t.term_id, {w: raw.get(w, 0) for w in weeks})
            ds.set_weekly_region(con, t.term_id, {r: {w: cnt.get(w, 0) for w in weeks} for r, cnt in by_region.items()})
            observed_raw = [datetime.fromisoformat(w) for w, v in raw.items() if v]
            observed = observed_raw + [datetime.fromisoformat(w) for w, v in evidence_weeks(con, t.term_id).items() if v]
            first = min([t.first_seen.replace(tzinfo=None) if t.first_seen else datetime.now()] + observed)
            weeks_since = max(0, (datetime.now() - first).days // 7)
            # 모양(오르는 중·정점)은 꾸준히 모으는 원본(뉴스·쇼츠·검색어)으로만 판정한다. 조사 근거는 조사한 주에만
            # 몰려서, 그대로 넣으면 '우리가 언제 조사했나' 를 잰다(2026-09-28: 2017년 유행어 가즈아가 '오르는 중').
            # 원본에 언급이 없으면 조사 근거로는 '마지막으로 쓰인 때' 만 본다.
            raw_series = [raw.get(w, 0) for w in weeks]
            last_sampled = sampled.get(t.term_id) or queried.get(t.canonical)
            if last_sampled and last_sampled.tzinfo is None:
                last_sampled = last_sampled.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            fresh_sample = bool(last_sampled) and (now - last_sampled).days <= 14
            newest = newest_usage(con, t.term_id)
            # 늘 모으는 원본(나라별 뉴스판·쇼츠·검색어)은 매 실행 모든 말을 같이 보므로 0 도 뜻이 있다. 용어별 뉴스 검색은 잰 주에만 몰린다
            steady_series = [raw.get(w, 0) - query_hits.get(w, 0) for w in weeks]
            measured = measured_series(raw_series, weeks, last_sampled) if fresh_sample else []
            if sum(measured):
                t.lifecycle = life_stage(measured, weeks_since)
            elif sum(steady_series):
                t.lifecycle = life_stage(steady_series, weeks_since)
            else:
                last_raw = max((datetime.fromisoformat(w).replace(tzinfo=timezone.utc) for w, v in raw.items() if v), default=None)
                last_look = ds.last_researched(con, t.term_id, ok_only=True)
                t.lifecycle = recency_stage(max((d for d in (newest, last_raw) if d), default=None), now=as_of_last_look(last_look, now))
            # 근거 문장 분류에서 딴 이야기가 더 많으면 원본 언급(뉴스 제목 등)은 같은 글자의 일반어로 부푼 것이다 – 모양을 믿지 않고
            # 그 뜻으로 쓰였다고 분류된 근거의 마지막 때로만 본다. 'Robert'·'Again' 이 '오르는 중', '궁예'·'조지' 가 '꾸준함' 이었다(10-06, Plan 02)
            labels = ds.evidence_labels(con, t.term_id)
            offtopic = mostly_offtopic(labels)
            if offtopic and t.lifecycle != "unknown":
                # 그 뜻으로 쓰인 근거가 적으면 판단을 보류한다 – 스물넷 중 하나만 그 뜻이어도 그 하나가 최근이면 '꾸준함' 이 됐다('lean' 1/24, 'son' 4/20)
                on = sum(1 for p, _ in labels.values() if p != "offtopic")
                newest = newest_usage(con, t.term_id, on_topic=labels) if on >= MIXED_ON_MIN and on * MIXED_ON_SHARE_DEN >= len(labels) else None
                t.lifecycle = recency_stage(newest, now=as_of_last_look(ds.last_researched(con, t.term_id, ok_only=True), now))
            # 원본도 조사 근거도 없으면(위키 밈 분류로 들어온 말 대부분) 검색 관심도·위키 조회수를 따로 적는다. 생애주기로 쓰지 않는다 –
            # 원본 언급과 κ −0.04, 최근 쓰임과 κ 0.13 이고 2015년 이전 밈의 71% 가 '꾸준함' 이 됐다(10-06 검증, Plan 02)
            interest = interest_lifecycle(con, t.term_id, today) if t.lifecycle == "unknown" else "unknown"
            lifecycle, dif = t.lifecycle, diffusion(usage_kinds(con, t.term_id), t.lifecycle)
            # 다른 필드는 저장된 쪽에서 — 훑는 몇 분 사이 검수자가 승인·제외한 것을 시작 때 읽은 사본이 덮지 않게
            fresh = ds.get_term(con, t.term_id) or t
            fresh.lifecycle, fresh.diffusion = lifecycle, dif
            fresh.interest = None if interest == "unknown" else interest
            fresh.first_seen = first.replace(tzinfo=timezone.utc)
            # 마지막 본 때 = 원본의 마지막 주와 가장 최근 쓰임 근거 가운데 늦은 것 — 생애주기(recency_stage)와 같은 재료.
            # 둘 다 없으면 비운다(예전 규칙으로 남은 날짜가 그대로 남아 있던 것, 검토 2차)
            seen = ([] if offtopic else [d.replace(tzinfo=timezone.utc) for d in observed_raw]) + ([newest if newest.tzinfo else newest.replace(tzinfo=timezone.utc)] if newest else [])
            fresh.last_seen = max(seen) if seen else None
            ds.upsert_term(con, fresh)
            n += 1
        r.count = n
    return {"track": r}
