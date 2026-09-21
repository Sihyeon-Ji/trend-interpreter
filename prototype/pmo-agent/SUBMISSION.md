# Echo PMO — submission material

Working notes for the 2026 Google AI Builder Cup form, numbered to match its sections.
Everything here is taken from the code and the measurements; where a number appears, the
command that produces it is next to it.

Two sections are **not** filled in, because they are decisions rather than work:

- **§14 GitHub Public Repository** — this lives in a private team repository with push
  disabled, and only `prototype/pmo-agent/` belongs to this candidate project
- **§14 Final Product Link** — needs a Cloud Run deployment, which needs a GCP project

---

## 1. Brief about the idea

A PMO agent that answers the question every project-management tool leaves out: **why did
this stop?**

Jira knows a task's status. Git knows the last commit was twelve days ago. The calendar
knows its owner spent those days in incident calls. A meeting note holds the only sentence
that says what the incident *was*. No one of them can answer, and nobody joins them up by
hand, so the question gets asked in a standup instead.

For a delivery lead or PM running work across those four tools.

## 2. Opportunities

A PM's week goes on reconstruction: reading a board, guessing which commits belong to
which ticket, asking people what happened. The board says what someone last remembered to
type; the code says what actually happened; the two disagree constantly and nothing
notices.

The schedule is worse. Every tool forecasts from dependencies alone, so it promises dates
that assume a person can do three tasks at once. On the demo project that gap is **three
weeks** — against the live Jira board, dependencies say 13 October and
one-task-at-a-time says 3 November.

Work has moved into more tools, not fewer, and the joining-up is still manual. The same
reconstruction applies to any team whose record of work is split across a tracker, a
repository, a calendar and a document store.

## 3. Difference from existing solutions

| What is common | What this does |
|---|---|
| Needs `ECHO-12` in the commit message | Infers the link from author, timing, vocabulary and path — **precision 1.00, recall 0.85** at eight dates, zero wrong links |
| Forecasts from dependencies only | Adds who is free, and says what the difference costs |
| The model produces the numbers | The model chooses and explains; every number comes from `schedule.py` |
| An agent writes to your board | No adapter here has a write method except the board's, and that one needs a person |
| Answers with what it found | States what it *cannot* account for, in days |

The last row is the one that is hard to copy. An agent that always has an answer is an
agent whose answers cannot be trusted.

## 4. How it solves the problem

The same eight steps as `tools/demo.py`, which is the product:

1. **The schedule now** — CPM over the board's dependencies
2. **The constraints, added one at a time** — plus one-task-per-person, plus the hours
   meetings ate. The gap between step 1 and step 2 is the honest forecast
3. **What moving something would buy** — offered only to someone the repository shows has
   worked in that area
4. **The board against the code** — links commits to tasks with no ticket key, then reports
   where the two disagree
5. **Why it stopped** — all four tools at once, with the unaccounted days stated
6. **A photo of a meeting note** — Gemini reads the handwriting; the code decides
7. **What was read out** — proposals, `applied: false`, and questions where it is unsure
8. **Approval** — only what a person ticked is written

Before: open four tools, reconstruct by hand, ask in standup.
After: one answer with its evidence, and an explicit list of what to go and ask.

## 5. USP

**It does not say what it cannot show.**

Concretely, and each one is checked by a test:

- a link is made only when the winner clears the runner-up; otherwise the commit is
  reported as unlinked. **Zero wrong links** across eight dates and ~490 commits
- every cause carries the business days it accounts for, **counted once each**, and the
  remainder is stated rather than filled in
- a day the owner left no trace in any connected tool is named as a **blind spot**, not
  folded into the same number as a day they were visibly at work
- the model cannot reach the write path. `tools.py` contains no `approve=True`, and the
  repository, calendar and notes adapters have **no write methods at all**
- a write to a site outside `WRITE_ALLOWLIST` never leaves the process

## 6. Features

1. **Keyless board ↔ code linking** — author, timing, vocabulary and path, with a margin
   over the runner-up, and the confidence attached
2. **Root-cause reconstruction** — four tools lined up, honest accounting of the days
3. **Achievable scheduling** — dependencies, then capacity, then meeting load
4. **Vetted rebalancing** — a handover only to someone with history in that area
5. **Free-form and handwritten input** — a typed note or a photo becomes proposals
6. **Approval-gated writes** — nothing reaches the board until a person picks it
7. **Drift detection** — where the board and the code disagree, with the evidence

## 7. Process flow

```
                    ┌─ Jira ──────── status, dependencies, due dates
                    ├─ GitHub ────── commits, pull requests, changed paths
  read (no keys) ───┤
                    ├─ Calendar ──── meeting hours per person
                    └─ Notion ────── meeting notes (prose, no ticket keys)
                             │
                             ▼
            ┌────────────────────────────────────┐
            │  linking.py    commit → task        │  author · time · words · path
            │                (margin, or unlinked)│
            └────────────────┬───────────────────┘
                             ▼
            ┌────────────────────────────────────┐
            │  schedule.py   CPM, slack, slip     │  ← every number comes from here
            │  capacity.py   one task per person  │
            │  cause.py      why it stopped       │
            └────────────────┬───────────────────┘
                             ▼
     free-form note ──► ingest.py ──► Gemini ──► proposals  (applied: false)
     or a photo                       reads,     ├─ confident  → for approval
                                      never       ├─ unsure    → a question
                                      computes    └─ unknown key → refused
                             │
                             ▼
                    a person ticks what they want
                             │
                             ▼
              approve.py ──► WRITE_ALLOWLIST ──► Jira (audit log)
```

The two gates are the point: **the model never reaches the last arrow**, and a write to a
site that is not on the allowlist never leaves the process.

## 8. Wireframe / screens

One page, four sections, no build step (`src/pmo_agent/static/index.html`, zero
dependencies):

- **Schedule** — forecast, critical path, what is at risk
- **Capacity** — the bottleneck, and what a handover would buy
- **Board against code** — where the two disagree, with evidence links
- **Why it stopped** — causes by source, what they account for, what is left over
- **Free-form input** — a note or a photo, and the proposals it produced

Screenshots in §12.

## 9. System architecture

```
  Browser (static HTML, no framework, no CDN)
        │  fetch
        ▼
  FastAPI  (src/pmo_agent/api.py)          ── Cloud Run, from the Dockerfile
        │
        ├── tools.py         the Gemini function-calling layer
        │      │             read tools run; write tools return a dry run
        │      ▼
        │   llm.py ──────►  Gemini  (AI Studio today · Vertex AI path present,
        │                            unverified — no GCP project yet)
        │
        ├── calculation (pure Python, no dependencies, no network)
        │      schedule.py · capacity.py · availability.py
        │      linking.py  · cause.py    · familiarity.py · signals.py
        │
        └── ports.py   Protocols: Board · Repo · Calendar · Notes
                │      (mypy enforces that the adapters are interchangeable)
                ├── adapters/jira.py     ─► Jira Cloud      (the only writer)
                ├── adapters/github.py   ─► gh CLI          read-only
                ├── adapters/ms_calendar ─► MS Graph        read-only, structure only
                ├── adapters/notion.py   ─► Notion API      read-only
                └── adapters/memory_*.py ─► local JSON      for a demo with no accounts
```

Every adapter has a local twin behind the same Protocol, so the whole product runs with no
accounts at all — which is what makes 487 tests hermetic.

## 10. Technology stack

| Layer | Used | Note |
|---|---|---|
| Frontend | Plain HTML/CSS/JS | No framework and no CDN, on purpose — see below |
| Backend | FastAPI · uvicorn · Pydantic | Python 3.12 |
| AI | Gemini (`gemini-3.6-flash`, fallback `3.5-flash`) | function calling, JSON mode, multimodal |
| Cloud | Dockerfile ready for Cloud Run | **not yet deployed** |
| Data | JSON files | no database yet |
| Auth | none | a prototype, not a hosted product |
| Quality | pytest · ruff · mypy | 487 tests, hermetic |

Two things to state plainly rather than dress up:

- **Vertex AI**: `GEMINI_BACKEND=vertex` exists and its request assembly is tested, but it
  has never been run against a real call, because there is no GCP project yet
- **The frontend has no framework** because the calculation layer has no dependencies
  either, and that is the claim being made: every number came from `schedule.py`, and a
  reader can check it

## 11. Estimated running cost

An MVP for one team, per month:

| Item | Estimate |
|---|---|
| Cloud Run | ~$0–5 — scales to zero; a PMO dashboard is idle most of the day |
| Gemini / Vertex | ~$1–5 — a few calls per run, not per page view. The free tier's 20/day cap is what forced this line to exist |
| Storage | ~$0 — JSON files today; Firestore's free tier would cover this shape |
| Jira / GitHub / Notion | $0 — read APIs, existing accounts |

**~$5–10 a month.** The calculation is pure Python and costs nothing to run; the model is
called only when someone hands it prose or a photo.

## 12. Prototype snapshots

Not captured yet. The dashboard is the thing to shoot, and it runs with no accounts:

```bash
PMO_BACKEND=memory REPO_BACKEND=memory python -m uvicorn pmo_agent.api:app --port 8080
```

Verified rendering at 1280px with every section populated: the four headline cards, the
constraint table, the load bars, the board-against-code table with its evidence links,
and the cause section with its overlap note.

## 13. Next steps

From the README's own limitations list, which is where this project keeps what it has not
proven:

- **Vertex AI on a real GCP project**, and Cloud Run — matches the track's suggested stack
  and removes the free tier's daily cap
- **Handwriting against a real photo** — verified only against generated images so far
- **The Outlook calendar against a real tenant** — structure only today (needs an Azure app
  registration)
- **A notes workspace this agent did not shape** — the Notion rows were written by
  `tools/notion_seed.py`, so the columns are the ones it expects
- **Postgres** for the board, matching what the team repository adopted

Beyond the prototype: the same reconstruction applies to any team whose record of work is
split across a tracker, a repository, a calendar and a document store. Nothing in
`cause.py` is specific to software.

## 14. Project links

- **GitHub Public Repository** — *pending: this lives in a private team repository*
- **Demo Video (≤3 min)** — the full live demo now runs in **40.6 seconds**, so it fits
- **Final Product Link** — *pending: needs a Cloud Run deployment*
