"""Wiktionary 뜻풀이 조회. 영어 Wiktionary 는 한국어·일본어·인도네시아어 인터넷 속어도 꽤 갖고 있다 (밤티, aura farming …).
발굴이 아니라 '검증 앵커' 용도: 사전이 이미 아는 표현이면 뜻풀이가 근거가 되고, 없으면 빈 목록."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ..schemas import Evidence
from ..storage import dictionary_store as ds

from ..config import BOT_UA as UA  # noqa: E402
TAG = re.compile(r"<[^>]+>")


def lookup(term: str, lang: str = "en", timeout: float = 8.0) -> list[Evidence]:
    """en.wiktionary 의 언어별 정의. 결과 발췌는 '용어 — 품사: 정의' 꼴이라 용어 앵커가 항상 성립한다."""
    key = term.strip().replace(" ", "_")
    if not key:
        return []
    try:
        r = httpx.get(f"https://en.wiktionary.org/api/rest_v1/page/definition/{quote(key)}", headers={"User-Agent": UA}, timeout=timeout)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    sections = data.get(lang) or data.get("en") or next(iter(data.values()), [])
    lines = []
    for sec in sections[:3]:
        for d in sec.get("definitions", [])[:2]:
            text = TAG.sub("", d.get("definition", "")).strip()
            if text:
                lines.append(f"{sec.get('partOfSpeech', '')}: {text}")
    if not lines:
        return []
    url = f"https://en.wiktionary.org/wiki/{quote(key)}"
    return [Evidence(evidence_id=ds.new_id("e", url), kind="web", url=url, title=f"Wiktionary: {term}", source_domain="en.wiktionary.org",
                     observed_at=datetime.now(timezone.utc), excerpt=f"{term} — " + " / ".join(lines)[:300])]
