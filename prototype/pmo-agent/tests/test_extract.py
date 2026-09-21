"""An existing report → its template. No network.

Every company already has a weekly report format and it is never the one a tool ships
with. Hand it last week's report and it works out the shape.

The tests that matter are about the third option for a heading nothing here can fill.
There are only three:

  · drop it, and the reader believes their template was applied when it was not
  · fill it with something plausible, which is the worst thing a report can do
  · keep it, empty, and say so

Only the third is implemented, and most of this file is about defending that.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from pmo_agent import extract, render

TODAY = dt.date(2026, 9, 21)


def sample(tmp_path, headings=None, title="주간 업무 보고"):
    from docx import Document

    doc = Document()
    doc.add_heading(title, level=0)
    doc.add_paragraph("플랫폼개발본부 · 2026년 9월 3주차")
    for text in headings or ["1. 일정 리스크", "2. 예산 집행"]:
        doc.add_heading(text, level=1)
        doc.add_paragraph("some content")
    table = doc.add_table(rows=1, cols=3)
    for cell, text in zip(table.rows[0].cells, ["과제", "담당", "기한"], strict=False):
        cell.text = text
    path = tmp_path / "weekly.docx"
    doc.save(str(path))
    return str(path)


def matcher(pairs):
    """Stands in for the model: {heading: (section, confidence)}."""

    def call(headings):
        rows = [
            {
                "heading": h,
                "section": pairs.get(h, ("", 0.0))[0],
                "confidence": pairs.get(h, ("", 0.0))[1],
            }
            for h in headings
        ]
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps({"matches": rows}, ensure_ascii=False)}]
                    }
                }
            ]
        }

    return call


class TestReadingAWordFile:
    def test_the_structure_is_read_exactly_with_no_model(self):
        # A Word file already knows which paragraphs are headings, so there is nothing
        # here to be wrong about
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path

            found = extract.read(sample(Path(tmp)))
            assert found["read_exactly"] is True
            assert found["format"] == "docx"

    def test_the_title_and_the_headings_come_out_in_order(self, tmp_path):
        found = extract.read(sample(tmp_path, ["A", "B", "C"]))
        assert found["title"] == "주간 업무 보고"
        assert [h["text"] for h in found["headings"]] == ["A", "B", "C"]

    def test_the_line_under_the_title_is_kept_as_preamble(self, tmp_path):
        found = extract.read(sample(tmp_path))
        assert found["preamble"] and "2026" in found["preamble"][0]

    def test_a_tables_column_headers_are_read(self, tmp_path):
        found = extract.read(sample(tmp_path))
        assert found["tables"] == [["과제", "담당", "기한"]]


class TestMatching:
    def test_a_heading_that_matches_becomes_a_section(self, tmp_path):
        found = extract.read(sample(tmp_path, ["1. 일정 리스크"]))
        spec = extract.template(found, matcher({"1. 일정 리스크": ("risks", 0.9)}))
        assert spec["sections"] == ["risks"]
        assert spec["headings"]["risks"] == "1. 일정 리스크"

    def test_a_heading_with_no_match_is_kept_not_dropped(self, tmp_path):
        # Budget and hiring are the normal case, not an error
        found = extract.read(sample(tmp_path, ["예산 집행"]))
        spec = extract.template(found, matcher({}))
        assert spec["unfillable"][0]["heading"] == "예산 집행"
        assert "no data" in spec["unfillable"][0]["why"]

    def test_an_unsure_match_becomes_a_question_rather_than_a_section(self, tmp_path):
        found = extract.read(sample(tmp_path, ["뭐가 뭐지"]))
        spec = extract.template(found, matcher({"뭐가 뭐지": ("risks", 0.2)}))
        assert spec["sections"] != ["risks"]
        assert spec["questions"] and "risks" in spec["questions"][0]

    def test_a_section_the_agent_does_not_have_is_refused(self, tmp_path):
        found = extract.read(sample(tmp_path, ["매출"]))
        spec = extract.template(found, matcher({"매출": ("revenue", 0.99)}))
        assert spec["unfillable"], "an invented section name must not become a section"

    def test_the_original_order_survives(self, tmp_path):
        # The order is the template. A report whose sections arrive rearranged gets
        # reordered by hand, which is the tedium this removes.
        heads = ["1. 진행", "2. 리스크", "3. 예산", "4. 이슈"]
        found = extract.read(sample(tmp_path, heads))
        spec = extract.template(
            found, matcher({"2. 리스크": ("risks", 0.9), "4. 이슈": ("issues", 0.9)})
        )
        assert [o["heading"] for o in spec["order"]] == heads
        assert [o["section"] for o in spec["order"]] == ["", "risks", "", "issues"]


class TestWhenTheModelIsNoHelp:
    def test_a_failed_match_keeps_every_heading_rather_than_guessing(self, tmp_path):
        def boom(headings):
            raise RuntimeError("the model call failed")

        found = extract.read(sample(tmp_path, ["A", "B"]))
        spec = extract.template(found, boom)
        assert "could not be matched" in spec["error"]
        assert [u["heading"] for u in spec["unfillable"]] == ["A", "B"]

    def test_unreadable_json_matches_nothing_rather_than_something(self, tmp_path):
        def junk(headings):
            return {"candidates": [{"content": {"parts": [{"text": "{not json"}]}}]}

        found = extract.read(sample(tmp_path, ["A"]))
        spec = extract.template(found, junk)
        assert spec["unfillable"]

    def test_a_document_with_no_headings_is_not_an_error(self, tmp_path):
        from docx import Document

        doc = Document()
        doc.add_paragraph("just a paragraph")
        path = tmp_path / "flat.docx"
        doc.save(str(path))
        spec = extract.template(extract.read(str(path)), matcher({}))
        assert spec["sections"] == list(render.DEFAULT)


class TestTheReportComesOutInTheirShape:
    def spec(self, tmp_path):
        heads = ["1. 진행", "2. 리스크", "3. 예산"]
        found = extract.read(sample(tmp_path, heads))
        return extract.template(found, matcher({"2. 리스크": ("risks", 0.9)}))

    def data(self):
        return {
            "schedule": {
                "risks": [
                    {
                        "key": "E-1",
                        "summary": "Auth",
                        "assignee": "Ada",
                        "duedate": "2026-09-02",
                        "predicted_finish": "2026-10-01",
                        "delay_days": 21,
                    }
                ]
            }
        }

    def test_their_headings_are_used_not_ours(self, tmp_path):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        titles = [s["title"] for s in doc["sections"]]
        assert titles == ["1. 진행", "2. 리스크", "3. 예산"]

    def test_the_one_it_can_fill_has_the_real_numbers_in_it(self, tmp_path):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        filled = next(s for s in doc["sections"] if s["name"] == "risks")
        assert filled["rows"][0][0] == "E-1 Auth"

    def test_the_ones_it_cannot_fill_say_so_and_stay_empty(self, tmp_path):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        cannot = [s for s in doc["sections"] if s.get("unfillable")]
        assert len(cannot) == 2
        assert all(s["rows"] == [] for s in cannot)

    def test_the_note_says_how_many_were_left_empty(self, tmp_path):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        assert "left empty" in doc["note"]

    def test_the_markdown_marks_them_rather_than_hiding_them(self, tmp_path):
        text = render.to_markdown(render.compose(self.spec(tmp_path), self.data(), TODAY))
        assert "## 3. 예산" in text
        assert "did not fill it" in text

    def test_the_word_version_marks_them_too(self, tmp_path):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        out = render.write(doc, "docx", str(tmp_path / "out.docx"))

        from docx import Document

        text = "\n".join(p.text for p in Document(out["path"]).paragraphs)
        assert "did not fill it" in text

    @pytest.mark.parametrize("fmt", ["md", "docx", "xlsx", "pptx"])
    def test_every_format_survives_a_template_with_holes_in_it(self, tmp_path, fmt):
        doc = render.compose(self.spec(tmp_path), self.data(), TODAY)
        got = render.write(doc, fmt, str(tmp_path / f"out.{fmt}"))
        assert "error" not in got
