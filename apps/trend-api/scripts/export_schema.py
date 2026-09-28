"""schemas.py → apps/trend-web/lib/contract/schema.json (JSON Schema).

프론트 TS 타입은 이 파일에서 생성한다 (apps/trend-web: `pnpm contract`). 손으로 타입을 옮기지 않는다.
"""
import json

from pydantic import BaseModel

from trend_agents.config import ROOT
from trend_agents.schemas import (
    Evidence,
    GenerationRead,
    Meaning,
    MeaningDraft,
    MeaningText,
    NewsItem,
    Segment,
    ShortsInterpretation,
    ShortsVideo,
    Term,
)


class Contract(BaseModel):
    """프론트가 소비하는 모델 묶음. $defs 에 전부 나온다."""

    term: Term
    meaning: Meaning
    meaning_draft: MeaningDraft
    meaning_text: MeaningText
    evidence: Evidence
    segment: Segment
    shorts_video: ShortsVideo
    shorts_interpretation: ShortsInterpretation
    generation_read: GenerationRead
    news_item: NewsItem


out = ROOT.parent / "trend-web" / "lib" / "contract" / "schema.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(Contract.model_json_schema(), ensure_ascii=False, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT.parent)}  ($defs: {len(Contract.model_json_schema()['$defs'])})")
