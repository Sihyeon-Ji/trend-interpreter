"""콘텐츠 조사 에이전트를 돌린다. uv run scripts/content_agent.py squid-game "Squid Game" --steps 30"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import content_agent  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

key, name = sys.argv[1], sys.argv[2]
steps = int(sys.argv[sys.argv.index("--steps") + 1]) if "--steps" in sys.argv else 30
LANGS = ("ko", "en", "ja", "zh", "th", "id", "vi")


def wikidata_labels(qid: str) -> dict:
    """같은 QID 의 언어별 이름 — 나라마다 작품을 부르는 이름(시작점 문서 제목)."""
    import httpx

    from trend_agents.config import BOT_UA

    r = httpx.get("https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": qid, "props": "labels", "format": "json"},
                  headers={"User-Agent": BOT_UA}, timeout=30)
    return {k: v["value"] for k, v in r.json()["entities"][qid]["labels"].items() if k in LANGS}


path = Path(f"data/work/graph/{name}.json")
if "--qid" in sys.argv:
    labels = wikidata_labels(sys.argv[sys.argv.index("--qid") + 1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "labels": labels}, ensure_ascii=False, indent=1), encoding="utf-8")
else:
    labels = {k: v for k, v in json.loads(path.read_text(encoding="utf-8"))["labels"].items() if k in LANGS}
print("labels", labels)
seeds = [f"https://namu.wiki/w/{labels.get('ko', name)}", f"kym_children slug={key}", f"https://namu.wiki/w/{labels.get('ko', name)}/등장인물", f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}"]
seeds += [f"https://{lg}.wikipedia.org/wiki/{labels[lg].replace(' ', '_')}" for lg in ("ja", "zh", "th", "id", "vi") if labels.get(lg)]
con = db.connect()
rid = content_agent.run(con, key, name, labels, seeds, steps)
print("run", rid)
for s, tool, args, res in con.execute("SELECT step, tool, args_json, result FROM agent_trace WHERE run_id=? ORDER BY step", (rid,)):
    print(f"{s:>2} {tool:<12} {args[:90]} → {res[:80]!r}")
for r in con.execute("SELECT name, region, verified, reason, sentence, description FROM content_findings WHERE run_id=?", (rid,)):
    print(("O" if r[2] else "X"), r[1], r[0], "| 근거:", r[4], "|", r[3], "|", (r[5] or "")[:60])
for r in con.execute("SELECT a, a_region, b, b_region, verified, reason FROM content_pairs WHERE run_id=?", (rid,)):
    print("짝", ("확인" if r[4] else "제안"), f"{r[0]}({r[1]}) ↔ {r[2]}({r[3]})", "|", r[5])
