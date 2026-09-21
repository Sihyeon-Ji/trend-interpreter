"""An existing report → the template it was written to.

Every company already has a weekly report format, and it is never the one a tool ships
with. Somebody decided years ago that section 3 is "이슈 및 대응" and that the progress
table has four columns, and a report that arrives in a different shape gets reformatted by
hand before it goes anywhere — which is the tedium this was supposed to remove.

So: hand it last week's report and it works out the shape. Headings, their order, the
tables and their column headers.

Two paths, and the difference matters:

  **.docx** is read directly. A Word file already *knows* which paragraphs are headings
  and where its tables are, so the structure is extracted exactly, with no model involved
  and nothing to be wrong about.

  **PDF, a photo, a scan** has no structure to read, only marks on a page. That needs a
  model (or Document AI), and what comes back is an inference like any other here — so it
  carries a confidence and the low ones become questions.

Then each heading is matched to something this agent can actually fill. **A heading it
cannot fill is kept, not dropped.** A real template always has sections nobody here has
data for — budget, hiring, headcount — and there are three things to do with those:

  · drop them, and the reader believes their template was applied when it was not
  · fill them with something plausible, which is the worst thing a report can do
  · **keep them, empty, and say the agent cannot fill them**

Only the third is honest, so it is the only one implemented.
"""

from __future__ import annotations

import os

from pmo_agent import llm, render

MATCH_SYSTEM = """You match the headings of an existing report to a fixed list of sections
an agent can fill. Rules:
1) Use only the section names given. Never invent one.
2) A heading with no good match gets an empty section name. That is the expected answer
   for topics like budget, hiring or headcount, which the agent has no data for.
3) Do not translate or rewrite the heading. Return it exactly as given.
4) confidence is 0.0-1.0, how sure you are of the match."""

MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string", "description": "exactly as given"},
                    "section": {"type": "string", "description": "a section name, or empty"},
                    "confidence": {"type": "number"},
                },
                "required": ["heading", "section"],
            },
        }
    },
    "required": ["matches"],
}

SURE = 0.6  # below this the match is a question, not a template entry


# ------------------------------------------------------------------ reading a file
def from_docx(path: str) -> dict:
    """A Word file's own structure. Exact — the format records what is a heading."""
    from docx import Document

    doc = Document(path)
    headings, tables, preamble = [], [], []
    for block in doc.paragraphs:
        text = (block.text or "").strip()
        if not text:
            continue
        style = (block.style.name or "").lower() if block.style else ""
        if "heading" in style or "title" in style:
            headings.append({"text": text, "level": _level(style)})
        elif len(headings) <= 1:
            # The line under the title — department, week, author. "Before the first
            # heading" would never fire, because the title is itself a heading, which is
            # why this was silently returning nothing.
            preamble.append(text)
    for table in doc.tables:
        if table.rows:
            tables.append([(c.text or "").strip() for c in table.rows[0].cells])
    return {
        "source": os.path.basename(path),
        "format": "docx",
        "title": headings[0]["text"] if headings else "",
        "preamble": preamble[:2],
        "headings": [h for h in headings[1:]] if headings else [],
        "tables": tables,
        "read_exactly": True,  # no model was involved, so nothing here is inferred
    }


def _level(style: str) -> int:
    for n in range(1, 6):
        if str(n) in style:
            return n
    return 0


def from_image(path: str, caller=None) -> dict:
    """A PDF or a photo. No structure to read, so a model reads the marks on the page.

    Everything here is an inference and is labelled as one. Document AI's layout parser
    would replace this call and give better table boundaries; the shape it returns is the
    same, which is why the rest of this module does not care which produced it.
    """
    from pmo_agent import ingest

    ask = (
        "This is a company's weekly report. List its section headings in order, and for "
        "each table list only its column headers. Do not summarise the content."
    )
    parts = ingest.build_parts(ask, [path])
    raw = (caller or ingest.call)(parts)
    text = ingest.parse(raw)
    lines = [ln.strip() for ln in str(text.get("transcript") or "").splitlines() if ln.strip()]
    return {
        "source": os.path.basename(path),
        "format": os.path.splitext(path)[1].lstrip("."),
        "title": lines[0] if lines else "",
        "preamble": [],
        "headings": [{"text": ln, "level": 1} for ln in lines[1:]],
        "tables": [],
        "read_exactly": False,  # a model read this; treat every line as inferred
    }


def read(path: str, caller=None) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return from_docx(path)
    return from_image(path, caller)


# ------------------------------------------------------------------ matching
def call(headings: list) -> dict:
    listed = "\n".join(f"  {name}: {what}" for name, what in render.SECTIONS.items())
    asked = "\n".join(f"- {h}" for h in headings)
    return llm.generate(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"Sections available:\n{listed}\n\nHeadings:\n{asked}"}],
                }
            ],
            "systemInstruction": {"parts": [{"text": MATCH_SYSTEM}]},
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": MATCH_SCHEMA,
            },
        }
    )


def parse_matches(resp: dict) -> list:
    import json

    raw = "".join(
        p.get("text", "")
        for p in (((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    ).strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return []
    return list(data.get("matches") or [])


def template(found: dict, caller=call) -> dict:
    """The document's shape → a spec `render.compose` can fill, plus what it cannot.

    The result keeps every heading the original had, in the original order. Sections this
    agent can fill are named; the rest are carried as `unfillable` so the report can show
    the heading and say plainly that nothing here could fill it.
    """
    headings = [h["text"] for h in found.get("headings") or []]
    if not headings:
        return {**render.clean({}), "source": found.get("source", ""), "unfillable": []}

    try:
        matches = parse_matches(caller(headings))
    except Exception as e:
        spec = render.clean({}, "")
        spec["error"] = f"the headings could not be matched: {str(e)[:120]}"
        spec["source"] = found.get("source", "")
        spec["unfillable"] = [{"heading": h, "why": "not matched"} for h in headings]
        return spec

    by_heading = {m.get("heading", ""): m for m in matches}
    # The order is the template. A report whose sections arrive in a different order from
    # the one somebody approved gets reordered by hand, which is the tedium this removes —
    # so every heading is kept in place, whether or not anything here can fill it.
    order: list = []
    sections, unfillable, questions = [], [], []
    for heading in headings:
        match = by_heading.get(heading) or {}
        name = str(match.get("section") or "").strip()
        sure = float(match.get("confidence") or 0.0)
        if name not in render.SECTIONS:
            # Kept, not dropped. The reader sees their own heading and is told plainly
            # that nothing here could fill it.
            unfillable.append({"heading": heading, "why": "no data for this"})
            order.append({"heading": heading, "section": ""})
            continue
        if sure < SURE:
            unfillable.append({"heading": heading, "why": f"unsure it means {name} ({sure:.2f})"})
            order.append({"heading": heading, "section": ""})
            questions.append(f"“{heading}” might mean {name}, read at {sure:.2f}. Is that right?")
            continue
        sections.append({"heading": heading, "section": name})
        order.append({"heading": heading, "section": name})

    spec = render.clean(
        {
            "title": found.get("title") or "Project report",
            "sections": [s["section"] for s in sections],
            "rows_per_section": 6,
        }
    )
    spec.update(
        {
            "source": found.get("source", ""),
            "read_exactly": found.get("read_exactly", False),
            "headings": {s["section"]: s["heading"] for s in sections},
            "preamble": found.get("preamble") or [],
            "unfillable": unfillable,
            "order": order,
            "questions": questions,
            "note": _note(sections, unfillable, found),
        }
    )
    return spec


def _note(sections: list, unfillable: list, found: dict) -> str:
    how = "read from the file's own structure" if found.get("read_exactly") else "read by the model"
    said = f"{len(sections)} of {len(sections) + len(unfillable)} sections matched, {how}."
    if unfillable:
        names = ", ".join(u["heading"] for u in unfillable[:3])
        said += (
            f" {len(unfillable)} could not be filled and are kept empty rather than dropped"
            f" or invented: {names}."
        )
    return said
