"""리스크 분류 연구용 표본 내보내기 (Plan 03). 수집 서버에서 돌려 CSV 하나를 만들고, 비공개 Kaggle Dataset 으로
올려 Kaggle 노트북(models/kaggle/gemma_risk_labeling.ipynb)에서 같은 문장을 다른 프롬프트·모델로 다시 분류해 본다.
실데이터는 수집 서버의 DB 에만 있으므로 **수집 서버에서** 실행한다(개발 PC 의 DB 는 비어 있거나 예시다). 노트북은 이 결과 없이는 합성 문장으로만 돈다.

  uv run scripts/export_risk_sample.py                    # 리스크 수준별로 고르게 40개 용어
  uv run scripts/export_risk_sample.py --terms 20 --seed 7
  uv run scripts/export_risk_sample.py --only 'pov,brah'  # 표제어를 골라서

한 행이 근거 문장 하나다. 문장은 파이프라인의 risk 단계가 분류하는 것과 같은 것만 담는다(risk._usage: 쓰임 근거이고 표제어가 든 것, 용어당
최근 PER_TERM 개). risk.classify 는 아직 분류하지 않은 문장만 묶어 보내지만 노트북은 이 PER_TERM 개를 한 번에 묶는다.
서버가 이미 붙인 분류(pipeline_polarity·pipeline_risk)와 용어의 현재 수준을 함께 넣어 비교 기준으로 쓴다.
human_* 칸은 사람이 채울 자리다(빈칸으로 내보낸다).

사용자 입력 표(explain_cache·lookups·reader_prefs)는 읽지 않는다. 문장 구성은 risk 단계와 똑같이 둔다 — risk 단계는 커뮤니티·SNS 글
문장도 로컬 Gemma 로 분류하므로 기본으로 함께 담는다. 빼면(--exclude-community) 서버와 입력이 달라져 수준 비교가 참고용이 된다.
결과는 저장소 루트의 artifacts/risk_sample/ 에 둔다(artifacts/ 는 커밋하지 않는다).
같은 이름의 .env.json 에 이 서버의 분류 환경(Ollama 버전·모델 digest·호출 옵션·프롬프트 해시·커밋)을 남긴다 — 노트북이 이것으로
같은 버전을 설치하고 모델·프롬프트가 같은지 확인한다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx
from trend_agents.collectors.community import is_community_post
from trend_agents.config import GEMMA_LOCAL_MODEL, LOCAL_LLM_BASE_URL
from trend_agents.interpreters import local_chat
from trend_agents.pipeline import risk
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

OUT = Path(__file__).resolve().parents[3] / "artifacts" / "risk_sample"
FIELDS = ["term_id", "term", "definition", "term_risk_level", "term_risk_human", "evidence_id", "i", "kind", "source_domain",
          "community", "observed_at", "sentence", "pipeline_polarity", "pipeline_risk",
          "human_on_topic", "human_polarity", "human_risk", "human_level"]


def rows_for(con, term, include_community: bool) -> list[dict]:
    m = ds.current_meaning(con, term.term_id)
    labels = ds.evidence_labels(con, term.term_id)
    usage = [e for e in risk._usage(con, term) if include_community or not is_community_post(e)]
    out = []
    for i, e in enumerate(usage):
        polarity, kind = labels.get(e.evidence_id, ("", ""))
        out.append({
            "term_id": term.term_id, "term": term.canonical, "definition": (m.definition if m else "")[:160],
            "term_risk_level": term.risk_level or "", "term_risk_human": term.risk_human or "",
            "evidence_id": e.evidence_id, "i": i, "kind": e.kind, "source_domain": e.source_domain,
            "community": int(is_community_post(e)), "observed_at": e.observed_at.isoformat(),
            "sentence": (e.excerpt or e.title)[:220], "pipeline_polarity": polarity, "pipeline_risk": kind,
            "human_on_topic": "", "human_polarity": "", "human_risk": "", "human_level": "",
        })
    return out


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def environment(include_community: bool) -> dict:
    """노트북이 같은 조건을 만들 수 있게 이 서버의 분류 환경을 적는다. 알 수 없는 값은 빈칸."""
    env = {"model": GEMMA_LOCAL_MODEL, "backend": "openai-compatible" if LOCAL_LLM_BASE_URL else "ollama",
           "ollama_version": "", "model_digest": "", "temperature": 0.1, "num_ctx": local_chat.NUM_CTX,
           "max_tokens": local_chat.MAX_TOKENS, "think": False, "per_term": risk.PER_TERM,
           "risk_prompt_sha256": sha(risk.PROMPT), "json_rule_sha256": sha(local_chat._JSON_RULE),
           "retry_rule_sha256": sha(local_chat._RETRY_RULE), "include_community": include_community, "git_commit": ""}
    if not LOCAL_LLM_BASE_URL:
        host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
        host = host if host.startswith("http") else f"http://{host}"
        try:
            env["ollama_version"] = httpx.get(f"{host}/api/version", timeout=5).json().get("version", "")
            tags = httpx.get(f"{host}/api/tags", timeout=5).json().get("models", [])
            env["model_digest"] = next((m.get("digest", "") for m in tags if m.get("model") == GEMMA_LOCAL_MODEL), "")
        except Exception:
            pass
    try:
        env["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                           cwd=Path(__file__).parent, timeout=5).stdout.strip()
    except Exception:
        pass
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--terms", type=int, default=40, help="용어 수 (리스크 수준별로 고르게)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only", default="", help="쉼표로 구분한 표제어")
    ap.add_argument("--min-sentences", type=int, default=risk.MIN_LABELED, help="문장이 이보다 적은 용어는 뺀다")
    ap.add_argument("--exclude-community", action="store_true", help="커뮤니티·SNS 글 문장을 뺀다(서버와 입력이 달라진다)")
    args = ap.parse_args()

    con = db.connect()
    terms = ds.list_terms(con, ("verified",))
    if args.only:
        wanted = {t.strip() for t in args.only.split(",") if t.strip()}
        terms = [t for t in terms if t.canonical in wanted]
    include_community = not args.exclude_community
    by_term = {t.term_id: rows_for(con, t, include_community) for t in terms}
    terms = [t for t in terms if len(by_term[t.term_id]) >= (1 if args.only else args.min_sentences)]

    if not args.only:
        # 수준별로 나눠 돌아가며 뽑는다 — 대부분이 '없음'·'판단 보류' 라 그냥 뽑으면 주의·사용 자제가 거의 안 들어온다
        groups: dict[str, list] = defaultdict(list)
        for t in terms:
            groups[t.risk_level or "undecided"].append(t)
        rng = random.Random(args.seed)
        for g in groups.values():
            rng.shuffle(g)
        picked, keys = [], sorted(groups)
        while len(picked) < args.terms and any(groups.values()):
            for k in keys:
                if groups[k] and len(picked) < args.terms:
                    picked.append(groups[k].pop())
        terms = picked

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"risk_sample_{datetime.now():%Y%m%d_%H%M}.csv"
    n = 0
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for t in terms:
            for row in by_term[t.term_id]:
                w.writerow(row)
                n += 1
    levels = defaultdict(int)
    for t in terms:
        levels[t.risk_level or "undecided"] += 1
    env = environment(include_community)
    path.with_suffix(".env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    scope = "risk 단계와 같은 문장" if include_community else "커뮤니티 글 제외"
    print(f"{path}  용어 {len(terms)}개 · 문장 {n}개 ({scope}) · 수준 {dict(levels)}")
    print(f"{path.with_suffix('.env.json')}  {env['model']} · Ollama {env['ollama_version'] or '?'} · digest {env['model_digest'][:12] or '?'}")


if __name__ == "__main__":
    main()
