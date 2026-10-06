"""파이프라인 전 단계가 공유하는 데이터 모델.

Gemini 구조화 출력(response_schema), Ollama format, SQLite 저장에 그대로 쓴다.
이 파일이 곧 '트렌드 DB 스키마'라서, 제품 방향이 바뀌면 여기부터 바뀐다.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, get_args

import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["slang", "meme", "song", "drama", "dance", "news", "geopolitics", "product", "other"]
Generation = Literal["10s", "20s", "30s", "40s", "50s+", "all"]


class ShortsVideo(BaseModel):
    video_id: str
    url: str
    title: str
    channel: str
    published_at: datetime
    duration_sec: int
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    region: str
    category_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str  # "most_popular" | "search:<query>"


class MemeRef(BaseModel):
    name: str = Field(description="유행어/밈/노래/드라마 이름. 원어 그대로")
    kind: Category
    origin_hypothesis: str = Field(description="유래 가설. 어디서 언제 시작됐는지. 모르면 'unknown'")
    confidence: float = Field(ge=0, le=1)
    quote: str = Field(default="", description="영상 속에서 이 표현이 실제로 나온 대사·자막 한 줄, 원어 그대로 120자 안. 말하거나 보이지 않았으면 빈 문자열")


class ShortsInterpretation(BaseModel):
    """Gemini 가 쇼츠 하나를 직접 보고 내놓는 해석."""

    url: str
    language: str
    summary: str = Field(description="영상에서 실제로 일어나는 일, 2문장")
    memes: list[MemeRef]
    target_generation: list[Generation]
    why_viral: str
    explain_for_outsider: str = Field(description="이 문화권/세대 밖의 사람에게 맥락 설명 (한국어)")
    risk_flags: list[str] = Field(
        default_factory=list, description="브랜드/기관이 쓰면 위험한 이유 (조롱, 정치, 비하 유래, 유행 소멸 등)"
    )


class GenerationRead(BaseModel):
    """로컬 Gemma 가 텍스트 한 조각을 읽고 내놓는 세대 판정."""

    detected_generation: Generation
    slang_terms: list[str]
    plain_explanation: str
    confidence: float = Field(ge=0, le=1)


class NewsItem(BaseModel):
    title: str
    link: str
    published_at: datetime | None
    source: str
    region: str
    query: str | None = None


# ---------- 사전(지식 그래프) 계층 ----------
# 저장소(Spanner Graph / 로컬 SQLite)와 무관한 논리 모델. 저장 어댑터가 이걸 테이블/노드로 옮긴다.

class TrendQuery(BaseModel):
    """Google Trends 나라별 검색어 한 줄 (BigQuery 공개 데이터셋 또는 'Trending now' RSS).
    원천에 카테고리·연령이 없다 → 분류는 뒤에서 로컬 모델이 붙인다."""

    term: str
    region: str  # ISO 3166-1 alpha-2
    rank: int
    source: Literal["bq_top", "bq_rising", "rss_now", "namu_rank"]
    date: date
    score: int | None = None  # bq_top: 0~100 (해당 용어의 5년 시계열 안에서 상대값)
    percent_gain: int | None = None  # bq_rising 만
    approx_traffic: str | None = None  # rss_now 만 ("500+")
    news_title: str | None = None
    news_url: str | None = None


TermStatus = Literal["candidate", "researching", "needs_review", "verified", "retired"]
Verification = Literal["unverified", "verified_auto", "verified_human", "rejected"]
Lifecycle = Literal["emerging", "rising", "peak", "steady", "declining", "dormant", "unknown"]
EvidenceKind = Literal["short", "news", "datalab", "web", "community", "human", "wiki"]


# 확산 단계(Plan 02). 주간 언급 모양과 별개로 '어디까지 퍼졌나' 를 출처 종류로 본다. 규칙은 lifecycle.diffusion.
Diffusion = Literal["underground", "spreading", "mainstream", "fading"]


# 리스크(Plan 03). 수준은 규칙 코드가 정한다(pipeline/risk.py). None 은 '근거가 모자라 판단 보류'.
RiskLevel = Literal["none", "caution", "avoid"]
RiskType = Literal["hate", "mockery", "gender", "politics", "sexual", "none"]


class EvidenceLabel(BaseModel):
    """근거 문장 하나의 뉘앙스와 위험 유형. 로컬 Gemma 가 붙이고, 수준 판정은 코드가 한다."""

    i: int
    polarity: Literal["positive", "neutral", "negative"] = "neutral"
    risk: RiskType = "none"
    # 그 유행어의 뜻으로 쓰인 문장인가. 글자만 같은 딴 이야기(2026-09-28: 'La Peace' 근거 다섯 건이 콜롬비아
    # '토털 피스' 정책 기사)는 수준 판정에서 뺀다.
    on_topic: bool = True

    @field_validator("polarity", "risk", mode="before")
    @classmethod
    def _blank(cls, v, info):
        if isinstance(v, str) and not v.strip():
            return "neutral" if info.field_name == "polarity" else "none"
        return v


# 밈 추천(Plan 07)의 닫힌 낱말. 용어 쪽은 배치(fit 단계)가, 제품 쪽은 요청 때 붙이고, 겹침 점수는 규칙(pipeline/recommend.py)이 매긴다.
# 자유 낱말끼리 겹침을 세면 '여름' 이 'Brat Summer' 에 걸리는 우연만 남았다(2026-09-29 실측: 라떼 설명에 사전 135개 중 3개, 전부 우연).
Feeling = Literal["joy", "hype", "cute", "funny", "relatable", "comfort", "pride", "surprise", "sarcasm", "frustration", "tired", "romance",
                  "nostalgia", "cool"]
MemeUse = Literal["reaction", "praise", "self_mockery", "celebration", "complaint", "recommendation", "greeting", "challenge", "catchphrase", "format"]
FitCategory = Literal["food_drink", "fashion_beauty", "tech", "game", "entertainment", "travel", "finance", "health_fitness", "education", "lifestyle"]
Voice = Literal["wholesome", "playful", "edgy", "crude"]
CampaignTone = Literal["friendly", "witty", "premium"]   # 홍보 톤: 친근함·재치·고급스러움


def _known(values, allowed: tuple, limit: int):
    """모델이 목록 밖 낱말을 섞어도 그 값만 버린다(형식 실패로 전체를 잃지 않게)."""
    if not isinstance(values, list):
        return values
    return list(dict.fromkeys(v for v in (str(x).strip().lower() for x in values) if v in allowed))[:limit]


class MemeFit(BaseModel):
    """표제어 하나가 광고 문구에서 어떤 느낌·쓰임으로 들어가나. 로컬 Gemma 가 사전 뜻을 보고 닫힌 낱말로만 붙인다."""

    feelings: list[Feeling] = Field(description="이 표현이 전하는 느낌 1~3개")
    uses: list[MemeUse] = Field(description="주로 쓰이는 방식 1~2개")
    fits: list[FitCategory] = Field(default_factory=list, description="자연스럽게 어울리는 제품 분야 0~3개")
    any_category: bool = Field(default=False, description="분야를 가리지 않고 쓰는 반응·감탄 표현이면 true")
    voice: Voice = Field(description="말투의 결")

    @field_validator("feelings", "uses", "fits", mode="before")
    @classmethod
    def _closed(cls, v, info):
        allowed = {"feelings": Feeling, "uses": MemeUse, "fits": FitCategory}[info.field_name]
        return _known(v, get_args(allowed), 3)

    @field_validator("voice", mode="before")
    @classmethod
    def _voice(cls, v):
        # 모르는 값·빈 값은 'edgy' — 친근함·고급스러움 톤에서 빠진다. 'playful' 로 두면 저속한 말이 형식 실수 하나로 문을 통과했다(검토 2차)
        v = str(v or "").strip().lower()
        return v if v in get_args(Voice) else "edgy"


class FitLabel(MemeFit):
    """배치로 여러 표제어를 한 번에 붙일 때의 한 줄 — i 는 입력 번호."""

    i: int


# ---------- 콘텐츠 생성 (Plan 08) — Gemini 한 번의 구조화 출력과 Gemma 의 사전 대조 검사 ----------

def _clip(n: int):
    def f(v):
        return str(v).strip()[:n] if v is not None else ""
    return f


def _hashtag(x) -> str:
    """해시태그 한 칸 — 글자·숫자·결합 부호·밑줄만. 태그는 공백·기호에서 끊겨 '#aura farming' 은 #aura 만 걸렸다(검토 3차).
    \\W 로 지우면 태국어 모음 부호(결합 부호)까지 지워지므로 유니코드 분류로 가른다."""
    return "".join(ch for ch in str(x) if ch == "_" or unicodedata.category(ch)[0] in "LMN")[:40]


class SocialCopy(BaseModel):
    """SNS 카피 한 안. 글은 목표 지역의 언어, note_ko 는 마케터가 읽는 설명(화면 언어 — 이름은 예전 그대로)."""

    platform: Literal["instagram", "x"]
    text: str = Field(description="게시글 본문 (목표 지역 언어). 고른 밈을 그대로 넣는다")
    hashtags: list[str] = Field(default_factory=list, description="해시태그 3~6개, # 없이, 띄어쓰기 없이")
    note_ko: str = Field(default="", description="이 안이 밈을 어떻게 썼는지 한 문장 (마케터가 읽는 설명, 화면 언어)")

    @field_validator("text", "note_ko", mode="before")
    @classmethod
    def _short(cls, v, info):
        return _clip(600 if info.field_name == "text" else 200)(v)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _tags(cls, v):
        if not isinstance(v, list):
            return v
        out: list[str] = []
        for x in v:
            if (t := _hashtag(x)) and t not in out:
                out.append(t)
        return out[:8]


class ScriptScene(BaseModel):
    start_s: int = Field(ge=0)
    end_s: int = Field(ge=0)
    visual: str = Field(description="화면에 보이는 것 (목표 지역 언어)")
    caption: str = Field(default="", description="자막 (목표 지역 언어)")
    line: str = Field(default="", description="대사·내레이션 (목표 지역 언어)")


class ShortScript(BaseModel):
    """틱톡·릴스용 15~30초 대본."""

    title: str
    duration_s: int = Field(ge=5, le=60)
    scenes: list[ScriptScene]
    note_ko: str = Field(default="", description="대본 설명 (마케터가 읽는 설명, 화면 언어)")


class ThumbnailPlan(BaseModel):
    headline: str = Field(description="썸네일 주요 문구 (목표 지역 언어)")
    layout: str = Field(description="배치 (마케터가 읽는 설명, 화면 언어)")
    colors: list[str] = Field(default_factory=list, description="색 (화면 언어)")
    subject: str = Field(default="", description="인물·제품 위치 (마케터가 읽는 설명, 화면 언어)")
    note_ko: str = Field(default="", description="썸네일 설명 (화면 언어)")


class ContentDraft(BaseModel):
    """생성 한 번의 결과: 인스타그램 2안·X 2안, 숏폼 대본 하나, 썸네일 구성안 하나."""

    copies: list[SocialCopy]
    script: ShortScript
    thumbnail: ThumbnailPlan

    @model_validator(mode="before")
    @classmethod
    def _hoist(cls, v):
        """모양만 바로잡는다(내용은 그대로): 작은 모델이 thumbnail 을 script 안에 넣고 script 의 note_ko 를 장면 목록 끝에 넣는 일이 잦았다
        (2026-09-29 로컬 Gemma 실측, 생성 18번 중 7번이 이 모양으로 실패). Gemini 는 응답 스키마를 지켜 이 모양이 오지 않는다."""
        if not (isinstance(v, dict) and isinstance(v.get("script"), dict)):
            return v
        s = dict(v["script"])
        if "thumbnail" not in v and isinstance(s.get("thumbnail"), dict):
            v = {**v, "thumbnail": s.pop("thumbnail")}
        if isinstance(s.get("scenes"), list):
            scenes = []
            for x in s["scenes"]:
                if isinstance(x, dict) and set(x) == {"note_ko"}:
                    s.setdefault("note_ko", x["note_ko"])
                else:
                    scenes.append(x)
            s["scenes"] = scenes
        return {**v, "script": s}


class ProductBrief(BaseModel):
    """사진이나 홍보 문구를 읽은 제품 설명. 요청 때 한 번 만든다(Gemini, 개발 환경은 로컬 Gemma 또는 고정 예시).
    추천 점수에는 category·feelings 만 쓰고(닫힌 낱말), 나머지는 이유 서술과 화면 표시에 쓴다."""

    product: str = Field(description="제품이 무엇인지 한 줄 (120자 안)")
    category: FitCategory = Field(description="제품 분야")
    feelings: list[Feeling] = Field(description="이 제품 홍보가 전하고 싶은 느낌 1~3개")
    values: list[str] = Field(default_factory=list, description="핵심 가치 1~3개 (예: 시원함, 한정판)")
    scene: str = Field(default="", description="어떤 장면·상황에서 쓰이나")
    colors: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list, description="이 홍보에서 피해야 할 표현·주제")

    @field_validator("feelings", mode="before")
    @classmethod
    def _closed(cls, v):
        return _known(v, get_args(Feeling), 3)

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, v):
        v = str(v or "").strip().lower()
        return v if v in get_args(FitCategory) else "lifestyle"

    @field_validator("product", "scene", mode="before")
    @classmethod
    def _short_text(cls, v, info):
        # 만들기(/generate)는 추천 결과의 설명을 브라우저에서 다시 받는다 — 길이를 여기서 막는다(검토 3차: 수백 KB 가 생성 프롬프트로 갔다)
        return _clip(120 if info.field_name == "product" else 200)(v)

    @field_validator("values", "colors", "avoid", mode="before")
    @classmethod
    def _short_list(cls, v):
        return [str(x).strip()[:40] for x in v if str(x).strip()][:5] if isinstance(v, list) else v


class Term(BaseModel):
    term_id: str
    canonical: str
    lang: str = "ko"
    aliases: list[str] = Field(default_factory=list)
    category: Category = "slang"
    status: TermStatus = "candidate"
    lifecycle: Lifecycle = "unknown"
    diffusion: Diffusion | None = None  # 태동·확산·주류·식상. 근거가 모자라면 None
    # 검색 관심도(네이버 데이터랩·위키 조회수)의 최고점 대비 최근. 생애주기가 unknown 일 때만 채운다. 쓰임 단계가 아니다 –
    # 원본 언급·최근 쓰임과 우연 수준으로 맞고 오래된 밈일수록 '유지' 로 기울어(10-06 검증, Plan 02) 생애주기에 넣지 않는다
    interest: Literal["steady", "declining", "dormant"] | None = None
    risk_level: RiskLevel | None = None  # 없음·주의·사용 자제. None 은 판단 보류
    risk_reasons: list[str] = Field(default_factory=list)
    risk_checked_at: datetime | None = None
    risk_human: RiskLevel | None = None  # 검수자가 정한 수준. 있으면 규칙보다 우선한다
    risk_rule_level: RiskLevel | None = None  # 규칙이 본 수준 — 검수자가 덮어도 따로 남겨 관리 화면이 둘을 나란히 보인다
    risk_decided_by: str | None = None   # 검수자 계정 (사람의 결정만 기록한다)
    risk_decided_at: datetime | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class Evidence(BaseModel):
    evidence_id: str
    kind: EvidenceKind
    url: str
    title: str = ""
    source_domain: str
    observed_at: datetime
    excerpt: str = Field(default="", description="근거가 되는 원문 문장")
    derived: bool = Field(default=False, description="발췌가 우리 모델이 쓴 문장인가 (쇼츠 해석 등). 화면에는 보이되 검증 앵커로는 제목만 본다")


class MeaningDraft(BaseModel):
    """리서치 에이전트 출력. 검증 게이트를 통과하기 전까지는 Meaning 이 아니다."""

    definition: str = Field(description="뜻, 1~2문장")
    expansion: str | None = Field(default=None, description="줄임말 풀이. 예: 자만추 → 자연스러운 만남 추구. 아니면 null")
    origin: str = Field(description="유래. 어디서 언제. 모르면 'unknown'")
    nuance: str = Field(description="뉘앙스·사용 맥락·주의점")
    generations: list[Generation]
    regions: list[str] = Field(description="ISO 국가코드")
    self_confidence: float = Field(ge=0, le=1)
    is_expression: bool = Field(default=True, description="유행어·밈·줄임말·챌린지·노래 후렴 같은 '표현'인가. 상품·기관·인물·정책·일반 단어면 false")

    @field_validator("generations", mode="before")
    @classmethod
    def _known_generations(cls, v):
        # 모델이 연령대 자리에 연대('90s'·'2000s')를 넣으면 형식 실패로 조사 전체가 죽었다(2026-09-28, 같은 세 용어가 이틀 내내).
        # 세대는 부가 정보라 모르는 값만 버린다.
        return [g for g in v if g in get_args(Generation)] if isinstance(v, list) else v

    @field_validator("regions", mode="before")
    @classmethod
    def _country_codes(cls, v):
        # 빈 문자열('')이 나라로 저장돼 36개 용어가 어느 나라에도 속하지 않았다(2026-09-28). 두 글자 코드와 GLOBAL 만 받는다.
        if not isinstance(v, list):
            return v
        codes = [str(r).strip().upper() for r in v]
        return list(dict.fromkeys(r for r in codes if re.fullmatch(r"[A-Z]{2}", r) or r == "GLOBAL"))



class Meaning(MeaningDraft):
    """검증 게이트를 거쳐 저장된 버전. 뜻이 바뀌면 새 version 을 만들고 이전 것은 valid_to 를 닫는다(위키식 이력)."""

    meaning_id: str
    term_id: str
    version: int
    confidence: float = Field(ge=0, le=1)
    verification: Verification = "unverified"
    valid_from: datetime
    valid_to: datetime | None = None
    created_by: str = "research_agent"
    citations: list[str] = Field(default_factory=list, description="grounding 이 돌려준 출처 URL")


class Segment(BaseModel):
    """세대 × 국가. 확산 경로의 노드."""

    segment_id: str  # 예: KR-20s
    generation: Generation
    region: str


class MeaningText(BaseModel):
    """한 언어로 된 뜻 묶음. 로컬 Gemma 가 언어별로 만들어 저장한다. 용어 원문(canonical)은 번역 대상이 아니다."""

    definition: str
    expansion: str | None = Field(default=None, description="줄임말 풀이. 원문 표기를 남기고 뜻만 옮긴다")
    origin: str
    nuance: str
    plain: str | None = Field(default=None, description="쉽게 풀어 쓴 표현. 뜻이 따로 없는 감탄사면 null")


class WikiTop(BaseModel):
    """위키백과 언어판별 일간 조회 상위 문서. 키 없음. 인물·작품·사건 관심 신호."""

    lang: str
    date: date
    rank: int
    article: str
    views: int


CandidateSource = Literal["trend", "shorts", "news", "manual", "spot", "wiki", "hunt", "namu"]


class Candidate(BaseModel):
    """사전 후보. 여러 소스에서 같은 표현이 나오면 count 가 오른다. 리서치는 count·신뢰도 순."""

    candidate_id: str
    text: str
    lang: str = "ko"
    regions: list[str] = Field(default_factory=list)
    sources: list[CandidateSource] = Field(default_factory=list)
    count: int = 1
    first_seen: datetime
    last_seen: datetime
    status: Literal["new", "researching", "promoted", "rejected", "expired"] = "new"  # expired: 한 번만 보고 묵은 후보(재등장하면 new 로)
    note: str = ""


# ---------- '지금 뜨는 것' 보드 (프론트 lib/trends/types.ts 와 1:1) ----------

TrendCategory = Literal["slang_meme", "song_challenge", "fashion_beauty", "food", "product", "people_content", "sports_event"]
Change = Literal["new", "up", "flat", "down"]


class Text2(BaseModel):
    ko: str
    en: str


class TrendItem(BaseModel):
    id: str
    region: str
    category: TrendCategory
    term: str
    rank: int
    change: Change
    gain_pct: int | None = None
    weekly: list[int]
    term_id: str | None = None
    topic_id: str | None = None
    note: Text2


class TopicVariantLink(BaseModel):
    label: str
    note: Text2
    term_id: str | None = None


class TopicVariant(BaseModel):
    region: str
    local_name: str
    since: str
    # since 에 날짜를 대는 출처가 있나. 있어야 이동 경로의 한 점이 된다 — 없으면 지도는 이 나라를 '쓰는 곳'으로만 보이고 선을 긋지 않는다.
    dated: bool = False
    since_source: Text2 | None = None
    heat: int
    what_changed: Text2
    local_memes: list[TopicVariantLink] = Field(default_factory=list)
    linked: list[TopicVariantLink] = Field(default_factory=list)
    term_id: str | None = None


class Topic(BaseModel):
    id: str
    category: TrendCategory
    name: Text2
    summary: Text2
    variants: list[TopicVariant]


class TrendBoard(BaseModel):
    generated_at: datetime
    items: list[TrendItem]
    topics: list[Topic]
    why: list["TrendWhy"] = Field(default_factory=list)


class TrendClassification(BaseModel):
    """검색어 한 건의 분류 결과. 인덱스 매핑 배치 JSON 으로 받는다 (순서 어긋남 방지)."""

    i: int
    term: str = Field(default="", description="그 줄의 표현을 그대로 옮겨 적는다 (줄이 어긋났는지 확인용)")
    category: TrendCategory
    kind: Literal["slang_meme", "song", "challenge", "person", "event", "sports", "product", "food", "fashion", "place", "other"]
    is_term_candidate: bool = Field(description="유행어·밈·줄임말처럼 '뜻을 설명할 가치'가 있는가")
    lang: str = Field(description="ISO 639-1")


class DemandedTerm(BaseModel):
    """수요 기반 조사(hunt) 출력: 사전이 못 답한 질문 한 줄에서 뽑은 '이용자가 물어본 표현'.
    original 은 한글로 적은 외래어의 원어 표기 — 인터넷 자료는 원어로 적혀 있어서 그걸로 찾아야 한다."""

    # i·term 만 필수다. 작은 모델이 lang·kind 를 빼먹어도 그 줄을 버리지 않도록 기본값을 둔다
    # (2026-09-16 실측: 전부 기본값 없이 두었더니 11줄이 한꺼번에 검증에 걸려 단계가 죽었다).
    i: int
    term: str
    original: str | None = Field(default=None, description="원어 표기. 한국어 고유 표현이면 null")
    lang: str = Field(default="en", description="ISO 639-1")
    kind: Literal["slang", "meme", "song", "challenge", "none"] = "slang"

    @field_validator("kind", "lang", mode="before")
    @classmethod
    def _blank_to_default(cls, v, info):
        """작은 모델은 모르는 칸을 비워서 보낸다(kind=""). 기본값은 키가 아예 없을 때만 쓰이므로
        빈 값은 여기서 기본값으로 바꿔 준다 — 안 그러면 줄 전체가 버려진다(2026-09-16 실측)."""
        if isinstance(v, str) and not v.strip():
            return "slang" if info.field_name == "kind" else "en"
        return v


class SpottedTerm(BaseModel):
    """발굴(spot) 단계 출력: 짧은 글 한 줄에서 뽑은 '뜻을 찾아볼 표현'. 후보가 될지는 규칙(원문에 실재·두 번 이상 목격)이 정한다."""

    i: int
    term: str
    lang: str = Field(description="ISO 639-1")
    kind: Literal["slang", "meme", "song", "challenge", "none"]
    confidence: float = Field(ge=0, le=1)


# ---------- 문서 대조 (Plan 12) — 로컬 Gemma 는 제안만 한다. 상태·뜻은 사람이 검수 큐에서 바꾼다 ----------

class MeaningFix(BaseModel):
    """참고 문서와 맞춰 본 고칠 안 — 뜻·유래·뉘앙스만. 빈 칸은 지금 실린 뜻을 그대로 둔다(풀이·세대·나라도 그대로)."""

    definition: str = Field(default="", description="고친 뜻 (한국어). 바꿀 필요가 없으면 빈 문자열")
    origin: str = Field(default="", description="고친 유래 (한국어). 바꿀 필요가 없으면 빈 문자열")
    nuance: str = Field(default="", description="고친 뉘앙스·주의점 (한국어). 바꿀 필요가 없으면 빈 문자열")

    @field_validator("definition", "origin", "nuance", mode="before")
    @classmethod
    def _text(cls, v):
        return str(v or "").strip()


class DocReading(BaseModel):
    """위키끼리 다를 때 참고 문서 하나가 적은 것."""

    i: int = Field(description="참고 문서 번호")
    summary: str = Field(description="그 문서가 적은 뜻·유래 한 문장 (한국어)")
    proposal: MeaningFix | None = Field(default=None, description="그 문서대로 고친 안. 없으면 null")


class CrosscheckJudgement(BaseModel):
    """사전 뜻과 참고 문서 발췌를 나란히 본 로컬 Gemma 의 제안(Plan 12 §2). '문서 없음' 은 규칙(verification.reference_doc)이 정하므로 여기 없다."""

    verdict: Literal["keep", "fix", "conflict", "not_a_meme"]
    reason: str = Field(default="", description="한국어 한두 문장. 무엇이 맞거나 다른지 문서 번호를 들어 쓴다")
    proposal: MeaningFix | None = Field(default=None, description="fix 일 때 고칠 안")
    readings: list[DocReading] = Field(default_factory=list, description="conflict 일 때 문서마다 그 문서가 적은 것")


# ---------- 급증 원인 조사 ----------

Trigger = Literal["influencer", "release", "event", "controversy", "meme", "promotion", "holiday", "sports", "unknown"]


class Actor(BaseModel):
    name: str = Field(description="근거 원문에 그대로 나오는 이름")
    role: str = Field(description="인플루언서·유튜버·연예인·브랜드·정치인·방송 등")


class ExplanationDraft(BaseModel):
    """'왜 지금 뜨는가'. 근거에 없는 사실은 쓰지 않는다. 판정(저장·갱신)은 규칙이 한다."""

    why_now: str = Field(description="한국어 1~2문장. 누가 무엇을 해서 지금 뜨는지")
    why_now_en: str
    trigger: Trigger
    actors: list[Actor] = Field(default_factory=list)
    first_signal: str | None = Field(default=None, description="근거에서 확인되는 가장 이른 날짜 YYYY-MM-DD, 없으면 null")
    self_confidence: float = Field(ge=0, le=1)


class TrendExplanation(ExplanationDraft):
    term: str
    region: str
    date: date
    evidence_ids: list[str] = Field(default_factory=list)
    model: str = ""


# ---------- 화면용: 왜 지금 뜨나 · 최근 변화 · 세대 곡선 ----------

class EvidenceBrief(BaseModel):
    kind: EvidenceKind
    source_domain: str
    title: str
    url: str
    observed_at: datetime


class TrendWhy(BaseModel):
    """급증 원인 설명 + 근거 요약 (이용자 화면용)."""

    term: str
    region: str
    date: date
    why_now: Text2
    trigger: Trigger
    actors: list[Actor] = Field(default_factory=list)
    first_signal: str | None = None
    confidence: float
    evidence_counts: dict[str, int] = Field(default_factory=dict)  # kind → n
    evidence: list[EvidenceBrief] = Field(default_factory=list)
    updated_at: datetime


class UpdateItem(BaseModel):
    """'오늘의 변화' 한 줄. kind: new_term | verified | meaning_changed | spike | recheck | reviewed"""

    kind: str
    at: datetime
    label: str
    region: str | None = None
    term_id: str | None = None
    detail: Text2 | None = None


class GenerationCurve(BaseModel):
    generation: Generation
    points: list[tuple[str, float]]  # (date, ratio 0~100 요청 내 상대값)
    peak_date: str | None = None
