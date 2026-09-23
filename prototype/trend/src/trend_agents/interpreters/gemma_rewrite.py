"""'쉽게 풀어 쓰면' — 로컬 Gemma 가 사전의 뜻을 참고해 메시지를 자연스러운 쉬운 말로 다시 쓴다.

단어 치환이 아니라 문장 재작성이다. 단, 바꿀 수 있는 것은 사전에 있는 표현만이고 나머지(어투·ㅋㅋ·이모지)는 원문 그대로.
뜻 판단은 사전(검증된 데이터)이 하고, 모델은 문장만 다듬는다.
"""
from __future__ import annotations

from pydantic import BaseModel

from ..config import GEMMA_LOCAL_MODEL
from . import local_chat


class GlossaryItem(BaseModel):
    term: str
    meaning: str | None  # 뜻(문장). None 이면 뜻이 따로 없는 감탄사 → 빼고 문장을 다듬는다


class Rewrite(BaseModel):
    text: str


PROMPT = {
    "ko": """아래 메시지를, 유행어를 전혀 모르는 사람(예: 50대 부모)이 읽어도 바로 이해할 수 있게 다시 써라.
사전에 있는 표현의 뜻을 참고해서 그 사람이 원래 하려던 말을 평범한 말투로 다시 쓰는 것이다. 단어를 갈아 끼우는 게 아니다.

규칙:
- 사전에 있는 표현만 바꾼다. 나머지 말투(ㅋㅋ, 이모지, 반말/존댓말, 문장 순서)는 그대로 둔다.
- 사전의 문구를 그대로 끼워 넣지 마라. 문장이 사람이 실제로 말하듯 자연스러워야 한다.
  나쁜 예: "완전 오히려 좋아잖아?", "긍정적으로 생각하기 가자"
  좋은 예: "오히려 잘된 거 아냐?", "좋게 생각하자"
- **사전에 없는 말은 뜻을 짐작해서 바꾸지 마라. 글자 그대로 두어라.** 모르면 두는 게 맞다.
  (실제로 있었던 잘못: 'ㅇㅈㄹ' 을 사전에 없는데도 '인정' 으로 바꿨다. 'ㅇㅈㄹ' 은 그대로 두었어야 한다.)
- 뜻이 없는 감탄사(뜻: 없음)는 빼고, 뺀 자리의 문장이 어색하지 않게 다듬는다.
- 설명을 덧붙이지 않는다. 길이는 원문과 비슷하게. 결과 문장만 JSON 으로.

예시
사전: 킹받네 → 매우 화가 난다 / 갓생 → 부지런하고 성실하게 사는 삶
메시지: 그 영화 결말 완전 킹받네ㅋㅋ 내일부터 갓생 살아야지
결과: 그 영화 결말 진짜 화나네ㅋㅋ 내일부터 부지런하게 살아야지

사전에 없는 말은 건드리지 않는 예
사전: 늙크크 → 촌스럽거나 옛날 감성
메시지: 식스티 세븐~ ㅇㅈㄹ하는거 진짜 늙크크같고 웃김
결과: 식스티 세븐~ ㅇㅈㄹ하는거 진짜 옛날 감성 같고 웃김

사전:
{glossary}

메시지: {text}""",
    "en": """Rewrite the message below so that someone who knows no internet slang (say, a parent in their 50s) understands it immediately.
Use the glossary meanings to say what the writer meant, in ordinary words. This is a rewrite, not a word swap.

Rules:
- Only change expressions listed in the glossary. Keep everything else (tone, "ngl", emoji, sentence order) as in the original.
- Do not paste the glossary phrase verbatim if it reads awkwardly; the sentence must sound like something a person would say.
- **Never guess at words that are not in the glossary. Leave them exactly as written.** Not knowing is fine.
- Exclamations with no meaning (meaning: none) are dropped, and the sentence around them must still be complete — never leave a fragment like "bro is so".
- No explanations. Similar length. Return only the rewritten message as JSON.

Example
Glossary: rizz → charm, skill at flirting / mid → mediocre, not special
Message: his rizz is unreal but the food was mid ngl
Result: his charm is unreal but the food was nothing special ngl

Glossary:
{glossary}

Message: {text}""",
}


def rewrite_plain(text: str, glossary: list[GlossaryItem], lang: str = "ko", model: str = GEMMA_LOCAL_MODEL) -> str:
    none = "뜻 없음, 감탄사" if lang == "ko" else "meaning: none, exclamation"
    gl = "\n".join(f"- {g.term} → {g.meaning or none}" for g in glossary)
    return local_chat.structured(PROMPT[lang].format(glossary=gl, text=text), Rewrite, temperature=0.2, model=model).text.strip()
