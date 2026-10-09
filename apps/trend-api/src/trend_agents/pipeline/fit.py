"""광고 쓰임 낱말 붙이기 (Plan 07 추천의 배치 준비).

추천은 요청 때 모델을 부르지 않고 점수를 매겨야 한다(ADR 0002 §3). 그러려면 표제어와 제품을 같은 낱말로 비교할 수 있어야 해서,
확인된 표제어마다 '어떤 느낌을 전하는가·어떻게 쓰이나·어느 분야에 어울리나·말투의 결' 을 닫힌 낱말(schemas.MemeFit)로 미리 붙인다.
로컬 Gemma 가 사전 뜻만 보고 붙이고, 뜻이 바뀌면(새 meaning_id) 다시 붙인다. 로컬 모델이 없으면 건너뛰고 붙인 것은 그대로 둔다.
"""
from __future__ import annotations


from ..schemas import FitLabel, MemeFit
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from .gemini import local_ok, structured
from .runs import stage

MAX_TERMS = 40      # 한 실행에 붙일 표제어 수 (8개씩 5번 호출)
BATCH = 8

PROMPT = """아래는 우리 사전에서 확인된 인터넷 표현과 그 뜻이다. 마케터가 광고 문구에 넣는다고 생각하고, 표현마다 아래 낱말로만 붙여라.
feelings (이 표현이 전하는 느낌, 1~3개): joy 기쁨 · hype 들뜸·열광 · cute 귀여움 · funny 웃김 · relatable 공감 · comfort 위로 · pride 자부심 · surprise 놀람 ·
  sarcasm 비꼼 · frustration 답답함 · tired 지침 · romance 설렘 · nostalgia 추억 · cool 멋짐
uses (주로 쓰이는 방식, 1~2개): reaction 반응 · praise 칭찬 · self_mockery 자조 · celebration 축하 · complaint 불평 · recommendation 추천 · greeting 인사 ·
  challenge 챌린지 · catchphrase 유행 문구 · format 밈 형식·짤
fits (이 표현을 넣은 광고 문구가 자연스러운 제품 분야, 0~3개): food_drink 음식·음료 · fashion_beauty 패션·뷰티 · tech 전자기기·앱 · game 게임 ·
  entertainment 공연·영상·음악 · travel 여행 · finance 금융 · health_fitness 건강·운동 · education 교육 · lifestyle 생활용품
  뜻·유래·쓰임에서 근거를 찾아 고른다. 예: 먹방·메뉴에서 나온 말 → food_drink, 운동 챌린지 → health_fitness, 게임 대사 → game, 아이돌 팬덤 말 → entertainment,
  외모·옷차림 말 → fashion_beauty, 직장·돈 이야기 → finance·lifestyle, 공부·시험 → education.
any_category: 특정 분야와 이어지지 않고 어떤 제품에나 붙는 반응·감탄 표현이면 true (그때는 fits 를 비워도 된다)
voice (말투의 결): wholesome 누구에게나 무난 · playful 장난스러움 · edgy 비꼬거나 아슬아슬함 · crude 저속·선정
audience (누가 알아듣나): general 인터넷을 잘 안 하는 사람도 아는 말 · online 인터넷 문화(짤·커뮤니티)를 아는 사람이면 아는 말 ·
  niche 특정 작품·캐릭터·게임·팬덤·서브컬처를 아는 사람끼리만 통하는 말
  캐릭터·작품·게임에서 나온 밈은 그 작품의 분야(entertainment·game)다 — 캐릭터의 생김새·옷차림만으로 fashion_beauty 를 붙이지 마라.
kind (표제어가 무엇인가 — 표제어 그대로, 뜻풀이가 아니라 말 자체를 본다): expr 문장 속에서 그 뜻으로 가져다 쓰는 표현·유행어 ·
  meme_name 그 이름만으로 대화에서 밈으로 부르는 것(짤·영상·형식의 이름) · topic 밈의 소재가 된 인물·캐릭터·작품·노래·사건·브랜드(대사·장면을
  인용해야 밈이 된다) · word 밈으로서의 쓰임이 따로 없는 일반 낱말·약어
뜻에 없는 것을 지어내지 마라. 분야와 이어지는 근거가 뜻에 없으면 fits 를 비운다. 입력 번호를 i 로 그대로 돌려줘라.

표현:
{items}"""


def todo(con: Connection) -> list[tuple]:
    """(표제어, 현재 뜻) — 아직 안 붙였거나 뜻이 바뀌었거나 audience·kind 칸이 생기기 전에 붙인 것만. 최근 언급이 많은 것부터(대시보드 윗줄이 먼저 준비되게)."""
    fits = ds.all_fits(con)
    out = []
    for t in ds.list_terms(con, ("verified",)):
        m = ds.current_meaning(con, t.term_id)
        if m and (t.term_id not in fits or fits[t.term_id][0] != m.meaning_id or fits[t.term_id][1].audience is None
                  or fits[t.term_id][1].kind is None):
            out.append((t, m, sum(c for _, c in ds.get_weekly(con, t.term_id, 4))))
    out.sort(key=lambda x: -x[2])
    return [(t, m) for t, m, _ in out]


def label(con: Connection, batch: list[tuple], *, gemini: str | None = None) -> int:
    """gemini 는 Gemini 모델 이름 — 밀린 것을 몰아 붙일 때만(fit_backfill --gemini). 로컬 e4b 가 audience·kind 를 거의 가르지 못했다(10-09, 210개 중 niche 1개)."""
    lines = []
    for i, (t, m) in enumerate(batch):
        ko = ds.get_translation(con, t.term_id, "ko")
        text = (ko.definition if ko else m.definition)[:160]
        nuance = (ko.nuance if ko else m.nuance)[:100]
        origin = (ko.origin if ko else m.origin)[:100]                  # 분야의 근거는 유래에 많다(먹방·게임 대사·팬덤)
        lines.append(f"{i}. {t.canonical} — {text} (유래: {origin} / 뉘앙스: {nuance})")
    prompt = PROMPT.format(items="\n".join(lines))
    parsed, model = (structured(con, prompt, list[FitLabel], model=gemini, prefer_gemini=True) if gemini
                     else structured(con, prompt, list[FitLabel]))
    n = 0
    for p in parsed or []:
        if 0 <= p.i < len(batch):
            t, m = batch[p.i]
            ds.set_fit(con, t.term_id, m.meaning_id, MemeFit.model_validate(p.model_dump(exclude={"i"})), model)
            n += 1
    return n


def run(con: Connection) -> dict:
    with stage(con, "fit") as r:
        if not local_ok():
            r.status, r.note = "skipped", "로컬 모델 없음 — 붙인 것은 그대로 둔다"
        else:
            pending = todo(con)[:MAX_TERMS]
            for k in range(0, len(pending), BATCH):
                try:
                    r.count += label(con, pending[k:k + BATCH])
                except Exception as e:           # 한 묶음의 형식 실패가 나머지를 막지 않는다
                    r.note += f"batch{k // BATCH}:{type(e).__name__} "
            r.detail = {"남은 표제어": max(0, len(todo(con)))}
    return {"fit": r}
