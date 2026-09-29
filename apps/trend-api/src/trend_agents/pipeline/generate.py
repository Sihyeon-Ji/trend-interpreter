"""SNS 카피·숏폼 대본·썸네일 구성안 생성 (Plan 08, 사용 흐름 3단계 '만들기').

요청마다 모델을 두 번만 부른다(ADR 0002 §3): Gemini 한 번의 구조화 생성 → Gemma 한 번의 사전 대조 검사.
검사에 걸린 안이 있으면 한 번 다시 만들고(최대 4회), 두 번째도 걸린 안은 빼고 이유를 남긴다.
검사는 규칙이 먼저다 — 고른 밈이 글에 실제로 들어 있나(mentions), 욕설·선정 표현(unsafe) — 그다음 모델이 '사전 뜻대로 썼나' 만 본다.
결과는 저장하지 않는다. 모델이 아예 없는 개발 환경은 고정 예시를 돌려준다.
"""
from __future__ import annotations

from ..schemas import ContentDraft, DraftCheck, ProductBrief, ScriptScene, ShortScript, SocialCopy, ThumbnailPlan
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from .gemini import BudgetExhausted, configured, local_ok, structured
from .dashboard import term_regions
from .match import mentions, unsafe
from .views import Dropped, GenerationResult

MAX_MEMES = 3
# 목표 지역의 말. 결과물은 입력 언어가 아니라 이 말로 만든다(Plan 08). 필리핀·싱가포르는 영어가 광고 표준어다.
REGION_LANG = {"KR": "ko", "JP": "ja", "TW": "zh-Hant", "HK": "zh-Hant", "TH": "th", "VN": "vi", "ID": "id", "PH": "en", "MY": "ms", "SG": "en"}
LANG_NAME = {"ko": "한국어", "ja": "일본어", "zh-Hant": "번체 중국어(대만·홍콩식)", "th": "태국어", "vi": "베트남어", "id": "인도네시아어",
             "en": "영어", "ms": "말레이어"}
TONE_KO = {"friendly": "친근함", "witty": "재치", "premium": "고급스러움"}
IDS = ("copy0", "copy1", "copy2", "copy3", "script", "thumbnail")

GEN_PROMPT = """너는 {region} 시장의 SNS 마케터다. 아래 제품을 아래 밈으로 홍보하는 결과물을 만든다. 톤: {tone}.
제품: {product} — {scene}. 핵심 가치: {values}. 피할 것: {avoid}
밈(사전에서 확인된 뜻 — 이 뜻대로만 쓴다. 뜻을 바꾸거나 새로 지어내지 마라):
{memes}

만들 것 (글은 모두 {lang}로. 밈 이름은 사전 표기 그대로 넣는다. 설명 칸 note_ko·layout·subject 만 {explain}로 — 마케터가 읽는다):
- copies: 인스타그램 캡션 2안(platform="instagram", 해시태그 3~6개), X 게시글 2안(platform="x", 280자 이내). 네 안 모두 밈 하나 이상을 글에 넣는다.
- script: 틱톡·릴스용 15~30초 대본. 장면마다 시작·끝 초, 화면, 자막, 대사.
- thumbnail: 주요 문구, 배치, 색, 인물·제품 위치.
{feedback}"""

CHECK_PROMPT = """아래는 광고 결과물 초안이다. 각 안(id)이 밈을 **사전 뜻대로** 썼는지 검사하라.
- 뜻과 다르게 쓰였거나(예: 긍정의 말을 조롱으로), 쓸 때 조심할 점에 적힌 맥락으로 쓰였으면 ok=false, problem 에 한국어 한 문장.
- 밈 뜻대로 자연스럽게 썼으면 ok=true, problem 은 빈 문자열.
사전:
{memes}

초안:
{drafts}"""


class Unavailable(RuntimeError):
    """모델이 설정돼 있는데 지금 만들지 못했다(예산·장애)."""


def _meme_lines(con: Connection, terms) -> str:
    out = []
    for t in terms:
        m = ds.current_meaning(con, t.term_id)
        ko = ds.get_translation(con, t.term_id, "ko")
        text = ko or m
        caution = " / 쓸 때 조심: " + "; ".join(r for r in t.risk_reasons if r != "검수자가 정한 수준")[:160] if t.risk_level == "caution" else ""
        alias = f" (다른 표기: {', '.join(t.aliases[:3])})" if t.aliases else ""
        out.append(f"- {t.canonical}{alias}: {(text.definition if text else '')[:160]} (뉘앙스: {(text.nuance if text else '')[:120]}){caution}")
    return "\n".join(out)


def _items(d: ContentDraft) -> dict[str, object]:
    got: dict[str, object] = {f"copy{i}": c for i, c in enumerate(d.copies[:4])}
    got["script"], got["thumbnail"] = d.script, d.thumbnail
    return got


def _text(item) -> str:
    if isinstance(item, SocialCopy):
        return f"{item.text} {' '.join(item.hashtags)}"
    if isinstance(item, ShortScript):
        return " ".join([item.title, *(f"{s.visual} {s.caption} {s.line}" for s in item.scenes)])
    if isinstance(item, ThumbnailPlan):
        return f"{item.headline} {item.layout} {item.subject}"
    return str(item)


def rule_problems(items: dict[str, object], terms) -> dict[str, str]:
    """규칙 검사 — {id: 문제}. 카피는 고른 밈이 글에 실제로 있어야 하고(mentions), 어떤 안도 욕설·선정 표현이 없어야 한다."""
    out = {}
    for k, item in items.items():
        text = _text(item)
        if unsafe(text):
            out[k] = "욕설·선정 표현이 들어 있음"
        elif k.startswith("copy") and not any(mentions(text, t.canonical, t.aliases) for t in terms):
            out[k] = "고른 밈이 글에 없음"
    return out


def check(con: Connection, draft: ContentDraft, terms) -> tuple[dict[str, str], int]:
    """({id: 문제}, 부른 모델 수). 규칙에 걸린 것은 모델에 묻지 않는다. 모델이 없으면 규칙만."""
    items = _items(draft)
    problems = rule_problems(items, terms)
    rest = {k: v for k, v in items.items() if k not in problems}
    if not rest or not (local_ok() or configured()):
        return problems, 0
    drafts = "\n".join(f"[{k}] {_text(v)[:500]}" for k, v in rest.items())
    try:
        parsed, _ = structured(con, CHECK_PROMPT.format(memes=_meme_lines(con, terms), drafts=drafts), list[DraftCheck])
    except Exception:
        return problems, 1           # 검사를 못 하면 규칙 검사만으로 둔다 — 모델 판단 없이 막지는 않는다
    for c in (parsed or []):
        if c.id in rest and not c.ok:
            problems[c.id] = c.problem.strip()[:160] or "사전 뜻과 다르게 쓰였음"
    return problems, 1


def _generate(con: Connection, terms, brief: ProductBrief, region: str, tone: str, feedback: str, ui: str) -> tuple[ContentDraft, str]:
    lang = REGION_LANG.get(region, "en")
    prompt = GEN_PROMPT.format(region=region, tone=TONE_KO.get(tone, tone), product=brief.product, scene=brief.scene or "-",
                               values=", ".join(brief.values) or "-", avoid=", ".join(brief.avoid) or "-", memes=_meme_lines(con, terms),
                               lang=LANG_NAME.get(lang, lang), explain="한국어" if ui == "ko" else "영어", feedback=feedback)
    try:
        parsed, model = structured(con, prompt, ContentDraft, temperature=0.7, prefer_gemini=True)
    except BudgetExhausted as e:
        raise Unavailable("오늘 만들기 한도를 다 썼습니다") from e
    except Exception as e:
        raise Unavailable("지금은 결과물을 만들지 못했습니다") from e
    return (parsed if isinstance(parsed, ContentDraft) else ContentDraft.model_validate(parsed)), ("local" if model.startswith("local:") else "gemini")


def run(con: Connection, term_ids: list[str], brief: ProductBrief, region: str, tone: str, ui: str = "ko") -> GenerationResult:
    """고른 밈(확인된 것, 사용 자제 제외)으로 결과물을 만든다. 모델 호출은 생성·검사 한 번씩, 다시 만들어도 네 번까지.
    ui 는 화면 언어 — 설명 칸(note_ko·배치·위치)을 그 말로 쓴다. 결과물 자체는 목표 지역의 말이다."""
    terms = [t for tid in dict.fromkeys(term_ids) if (t := ds.get_term(con, tid)) and t.status == "verified" and t.risk_level != "avoid"][:MAX_MEMES]
    if not terms:
        raise ValueError("쓸 수 있는 밈이 없습니다")
    # 그 지역에서 쓰이는 밈만 — 한국 밈을 일본 카피에 넣으면 가타카나로 옮겨 적어(オサルヒム) 읽히지도, 검사를 통과하지도 않았다(2026-09-29 실측)
    terms = [t for t in terms if region in term_regions(t, {u["region"] for u in ds.get_usage(con, t.term_id)})]
    if not terms:
        raise ValueError("고른 밈 가운데 이 지역에서 쓰이는 것이 없습니다")
    lang = REGION_LANG.get(region, "en")
    if not (local_ok() or configured()):
        return sample(terms, region, tone)
    first, source = _generate(con, terms, brief, region, tone, "", ui)
    problems, n = check(con, first, terms)
    calls = 1 + n
    kept = {k: v for k, v in _items(first).items() if k not in problems}
    dropped: list[Dropped] = []
    if problems:
        feedback = "지난 초안의 문제(이번에는 고쳐라):\n" + "\n".join(f"- {k}: {p}" for k, p in problems.items())
        second, _ = _generate(con, terms, brief, region, tone, feedback, ui)
        again, n2 = check(con, second, terms)
        calls += 1 + n2
        redo = _items(second)
        for k in problems:
            if k in redo and k not in again:
                kept[k] = redo[k]
            else:
                dropped.append(Dropped(id=k, reason=again.get(k) or problems[k]))
    copies = [kept[k] for k in IDS[:4] if k in kept]
    return GenerationResult(region=region, language=lang, tone=tone, memes=[t.canonical for t in terms], copies=copies,  # type: ignore[arg-type]
                            script=kept.get("script"), thumbnail=kept.get("thumbnail"), dropped=dropped, model_calls=calls, source=source)


def sample(terms, region: str, tone: str) -> GenerationResult:
    """모델 없는 개발 환경의 고정 예시 — 화면과 e2e 가 끝까지 돌게. 화면이 '예시' 라고 알린다."""
    name = terms[0].canonical
    copies = [SocialCopy(platform="instagram", text=f"더운 오후엔 {name}! 여름 한정 아이스 흑당 라떼로 기분 전환해요 ☕", hashtags=["여름한정", "흑당라떼", name.replace(" ", "")],
                         note_ko=f"'{name}' 을 제품의 기분 전환 순간에 붙였다"),
              SocialCopy(platform="instagram", text=f"오늘의 {name}은 시원한 한 잔. 여름에만 만나요", hashtags=["아이스라떼", "여름메뉴"], note_ko="한정판을 강조"),
              SocialCopy(platform="x", text=f"{name} 필요한 오후, 흑당 라떼 한 잔이면 충분", note_ko="짧은 공감형"),
              SocialCopy(platform="x", text=f"여름 한정이라 더 {name}. 이번 주까지!", note_ko="마감 강조")]
    script = ShortScript(title=f"{name} 한 잔", duration_s=15, note_ko="지친 오후 → 한 모금 → 밈 자막으로 반전",
                         scenes=[ScriptScene(start_s=0, end_s=4, visual="더위에 지친 얼굴", caption="오후 3시…", line=""),
                                 ScriptScene(start_s=4, end_s=10, visual="라떼를 한 모금", caption=f"{name}!", line="이거면 돼"),
                                 ScriptScene(start_s=10, end_s=15, visual="제품 클로즈업", caption="여름 한정", line="")])
    thumb = ThumbnailPlan(headline=f"{name} 한 잔", layout="왼쪽 제품, 오른쪽 큰 문구", colors=["갈색", "흰색"], subject="제품을 화면 왼쪽 3분의 1", note_ko="문구는 두 줄 이내")
    return GenerationResult(region=region, language=REGION_LANG.get(region, "en"), tone=tone, memes=[t.canonical for t in terms],  # type: ignore[arg-type]
                            copies=copies, script=script, thumbnail=thumb, model_calls=0, source="sample")
