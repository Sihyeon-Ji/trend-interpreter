"""화면 언어(ko·en·ja) — 이용자가 읽는 설명(제품 요약·문구 설명·AI 의견·브리핑 요약·쉽게 풀어 쓰기)을 어느 말로 쓰나.
결과물 본문(시장의 말)과는 다르다. 일본어 화면도 이 설명을 영어로 받던 것을 일본어로(10-13, 계획 ktwoo-copy-flow-and-japanese-ui B)."""
UI_LANGS = ("ko", "en", "ja")
NAME_KO = {"ko": "한국어", "en": "영어", "ja": "일본어"}          # 한국어로 쓴 프롬프트 안에서 부르는 이름
NAME_EN = {"ko": "Korean", "en": "English", "ja": "Japanese"}    # 영어로 쓴 프롬프트 안에서


def ui_lang(lang: str | None) -> str:
    """모르는 값은 한국어 — 예전 화면은 ko·en 만 보냈다."""
    return lang if lang in UI_LANGS else "ko"


# 설명 칸을 그 말로 쓰라는 지시를 그 말로 — 한국어 프롬프트 안의 '일본어로' 만으로는 약한 모델(Flash Lite)이 영어·한국어로 썼다(10-13 시험)
RULE = {
    "ko": "",
    "en": "Write {fields} in English.\n",
    "ja": "{fields} は日本語で書く（英語・韓国語は使わない）。\n",
}


def rule(lang: str, fields: str) -> str:
    return RULE.get(lang, "").format(fields=fields)
