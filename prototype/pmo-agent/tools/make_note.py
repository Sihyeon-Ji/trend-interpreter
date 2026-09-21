"""Generate a meeting-note image for the demo, to exercise ingest.py multimodal path for real.

This is not real handwriting. It is a synthetic image with paper texture, a slight tilt,
ink bleed and wobbling line spacing, to get close to "a photo of a notepad".
How well real handwriting reads still needs one check against a photo a person wrote
(see the limitations in the README).

Run: python tools/make_note.py [output path]
"""

from __future__ import annotations

import datetime as dt
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pmo_agent import capacity, schedule
from pmo_agent.env import samples_dir
from pmo_agent.seeds import world as world_mod

OUT = str(samples_dir() / "meeting-note.png")
FONTS = (  # Ink Free is a handwriting face shipped with Windows; Segoe Script is the fallback
    r"C:\Windows\Fonts\Inkfree.ttf",
    r"C:\Windows\Fonts\segoesc.ttf",
)
PAPER = (250, 247, 238)
INK = (32, 38, 60)

# The note names the work the way a person would — **no ticket keys.**
# Real meeting notes do not carry them, and working out which task each line means is
# exactly what ingest.resolve() is for. Put the keys in and the demo proves nothing.
#
# It is built from the current world rather than typed out once. A note that says "the
# API client finished today" is worth nothing the week the board already has it done:
# the proposal becomes a no-op and the "here is what this would do to the schedule" line
# comes out unchanged. Deriving it keeps the note true to the data it is read against.


def _short(summary: str) -> str:
    """The task named the way someone would say it out loud, with the phase dropped."""
    return summary.split("]")[-1].strip().lower()


def lines(today: dt.date | None = None) -> list:
    """The note's content, in (text, indent) pairs."""
    world = world_mod.simulate(today)
    board = world_mod.to_board(world)
    tasks = schedule.from_jira_issues(board["issues"])
    day = world.today

    blocked = tasks.get(world.incident["key"])
    loaded = capacity.levelled(tasks, day)["bottleneck"]
    busy = (loaded or {}).get("assignee", "")

    # Something genuinely unfinished, so "it is done" is a real change to propose
    finished = next(
        (
            t
            for t in tasks.values()
            if not t.is_done and not schedule.status_alike(t.status, "To Do")
        ),
        None,
    )
    # Something the overloaded person is holding, so the handover line has a point
    hand_over = next(
        (t for t in tasks.values() if not t.is_done and t.assignee == busy and t is not blocked),
        None,
    )
    relief = next((t.assignee for t in tasks.values() if t.assignee and t.assignee != busy), "")
    undated = next(
        (
            t
            for t in tasks.values()
            if not t.is_done and t is not finished and t is not hand_over and t is not blocked
        ),
        None,
    )
    later = schedule.add_workdays(day, 10)

    out = [(f"{day.month}/{day.day} weekly", 0), ("", 0)]
    if blocked:
        out += [
            (f"- {_short(blocked.summary)}: still waiting on the IdP decision", 1),
            (f"   -> push the due date to {later.month}/{later.day}", 2),
        ]
    if finished:
        out.append((f"- {_short(finished.summary)} finished today (done)", 1))
    if hand_over and relief:
        out += [
            (f"- {busy.split()[0]} is overloaded", 1),
            (f"   look at moving {_short(hand_over.summary)} to {relief.split()[0]}", 2),
        ]
    out.append(("- team sync cancelled next Monday", 1))
    if undated:
        out += [("", 0), (f"* {_short(undated.summary)} needs a fresh date", 0)]
    return out


LINES = lines()


def _font(size: int):
    """The first handwriting face that is actually installed."""
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(path: str = OUT, seed: int = 7) -> str:
    rnd = random.Random(seed)
    W, H = 1000, 720
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # Paper grain: faint blotches and horizontal rules
    for _ in range(1400):
        x, y = rnd.randrange(W), rnd.randrange(H)
        v = rnd.randint(-6, 6)
        d.point((x, y), fill=(PAPER[0] + v, PAPER[1] + v, PAPER[2] + v))
    for y in range(120, H - 40, 52):
        d.line([(60, y), (W - 60, y)], fill=(214, 220, 228), width=1)

    y = 70
    for text, indent in LINES:
        if not text:
            y += 26
            continue
        size = 40 if indent == 0 and text.startswith("9/") else 32
        font = _font(size)
        x = 70 + indent * 34 + rnd.randint(-3, 3)  # wobble each line a little
        # Nudge each glyph up and down a touch, for a handwritten feel
        for ch in text:
            dy = rnd.randint(-2, 2)
            d.text(
                (x, y + dy),
                ch,
                font=font,
                fill=(
                    INK[0] + rnd.randint(-12, 12),
                    INK[1] + rnd.randint(-12, 12),
                    INK[2] + rnd.randint(-12, 12),
                ),
            )
            x += d.textlength(ch, font=font) + rnd.uniform(-0.6, 1.2)
        y += size + 22

    img = img.rotate(rnd.uniform(-1.6, 1.6), resample=Image.BICUBIC, fillcolor=PAPER)
    img = img.filter(ImageFilter.GaussianBlur(0.6))  # camera focus blur
    # Lighting gradient (one side darker)
    grad = Image.linear_gradient("L").resize((W, H)).rotate(70, fillcolor=128)
    img = Image.composite(
        img, Image.blend(img, Image.new("RGB", (W, H), (200, 197, 190)), 0.35), grad
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, quality=88)
    return path


if __name__ == "__main__":
    p = render(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print("written:", p, os.path.getsize(p), "bytes")
