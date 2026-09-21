# Echo PMO — submission material

Working notes for the 2026 Google AI Builder Cup form, numbered to match its sections.
Everything here is taken from the code and the measurements; where a number appears, the
command that produces it is next to it.

Two sections are **not** filled in, because they are decisions rather than work:

- **§14 GitHub Public Repository** — this lives in a private team repository, and only
  `prototype/pmo-agent/` belongs to this candidate project
- **§14 Final Product Link** — needs a Cloud Run deployment, which needs a GCP project

---

## 1. Brief about the idea

A PMO agent that opens on **the work already waiting for a yes or a no**, not on another
status panel.

The measured problem is not a shortage of information. Knowledge workers give 60% of their
time to work *about* work and 352 hours a year to talking about it; adding a dashboard adds
to that number. What the coordination actually consists of is a handful of small things
nobody has got round to — somebody should be told their work is blocked, a date agreed in a
meeting is not on the board, a handover is still worth making but will not be next week.
Each is five minutes of thinking and twenty of chasing.

So the agent prepares them and stops. The first screen is that queue, most perishable
first, and the only thing a person supplies is the decision.

Underneath it sits the join that makes the queue checkable: Jira knows a task's status, Git
knows the last commit was twelve days ago, the calendar knows its owner spent those days in
incident calls, and a meeting note holds the only sentence saying what the incident *was*.
No one of them can account for the silence. That accounting is not the product — it is the
evidence each row rests on, and the reason a person can act on a row without re-deriving it.

For a delivery lead or PM running work across those four tools, and for the executive who
will open one screen rather than five.

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

**The front door**

1. **Today's queue** (`queue.py`) — the decisions, messages and board edits waiting on a
   person, most perishable first. Rows for one colleague fold into one question, every row
   names its source, nothing is done, and a queue that could not run says so instead of
   reporting a clear day
2. **Options, costed** (`decide.py`) — what each move buys in business days and when it
   stops being worth making. The agent prices the choices; it does not pick one

**The join underneath**

3. **Keyless board ↔ code linking** (`linking.py`) — author, timing, vocabulary and path,
   with a margin over the runner-up, and the confidence attached
4. **Root-cause accounting** (`cause.py`) — four tools lined up, each day counted once, the
   overlap stated and the remainder left unexplained rather than filled in
5. **Achievable scheduling** (`schedule.py`, `capacity.py`) — dependencies, then capacity,
   then meeting load, with the cost of each constraint shown separately
6. **Drift detection** (`signals.py`) — where the board and the code disagree, with evidence
7. **Vetted rebalancing** (`familiarity.py`) — a handover only to someone the repository
   shows has worked in that area

**Reading and writing prose**

8. **Meeting notes against the board** (`reconcile.py`) — only the differences, as proposed
   edits with the sentence each was read from
9. **Free-form, handwritten and spoken input** (`ingest.py`) — a typed note, a photo or an
   audio file becomes proposals
10. **Report templates from a document** (`extract.py`, `render.py`) — feed it last
    quarter's report and it extracts the section order, then issues the next one in that
    shape as md, docx, xlsx or pptx
11. **Approval-gated writes** (`approve.py`) — nothing reaches the board until a person
    picks it, and a site outside `WRITE_ALLOWLIST` never leaves the process

**Across projects, over time**

12. **Several projects at once** (`projects.py`) — build work and operations work, each
    judged by what it actually has. Operations gets arrival and closing rates and a median
    age; it never gets a finish date
13. **Issue register** (`register.py`) — what went wrong, who it reaches downstream, and a
    `LAPSED` state for a problem that stopped being reported without being fixed
14. **Executive roll-up** (`rollup.py`) — every project on one line, worst first, carrying
    its unexplained days rather than folding them away
15. **Warehouse export** (`warehouse.py`) — flat rows and a partitioned BigQuery schema, so
    the answer is kept every day instead of only computed today
16. **Korean throughout** (`i18n.py`) — re-rendered from the numbers each sentence was built
    from, never translated out of the English

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
            │  cause.py      days accounted for   │
            │  decide.py     what a move buys     │
            └────────────────┬───────────────────┘
                             ▼
     note · photo ─────► ingest.py ───► Gemini ──► proposals  (applied: false)
     or audio            reconcile.py   reads,     ├─ confident  → for approval
                                        never      ├─ unsure    → a question
                                        computes   └─ unknown key → refused
                             │
                             ▼
            ┌────────────────────────────────────┐
            │  queue.py      what needs a person  │  ← the first screen
            │                folded, sourced,     │
            │                nothing done         │
            └────────────────┬───────────────────┘
                             ▼
                    a person ticks what they want
                             │
                             ▼
              approve.py ──► WRITE_ALLOWLIST ──► Jira (audit log)

  alongside: register.py · health.py · rollup.py   → several projects on one screen
             extract.py · render.py               → a report in an existing shape
             warehouse.py                         → the same answers, kept daily
```

The two gates are the point: **the model never reaches the last arrow**, and a write to a
site that is not on the allowlist never leaves the process. The queue sits between the
calculation and the person for the same reason — it prepares, and stops.

## 8. Wireframe / screens

One page, no build step (`src/pmo_agent/static/index.html`, zero dependencies):

- **Waiting on you** — first, above everything. Each row is one decision, message or board
  edit: what it is, what it buys, when it stops being worth doing, and where it came from.
  Work landing on one colleague folds into a single row with the rest as chips; a drafted
  message stays collapsed until asked for. The footer says nothing here has been run
- **All projects** — one line each, worst first, build and operations judged by different
  headlines. Operations never shows a finish date, because it does not have one
- **The four tools** — Jira, GitHub, Outlook, Notion, each showing whether it is live or
  running on its local twin, what it supplies, and whether it can write. Only Jira can, and
  it says "only what a person approves"
- **The agent** — directly under them, with arrows from each: *joins* commits to tasks with
  no ticket key, *computes* every date, *asks* the model to read prose and pictures, *waits*
  for a person
- **Schedule** — forecast, critical path, what is at risk
- **Capacity** — the bottleneck, and what a handover would buy
- **Board against code** — where the two disagree, with the evidence
- **How much of the silence is accounted for** — each cause tagged with the tool it came
  from, the days it explains, how far the causes overlap, and what is left over. It is no
  longer a headline: it is what the *look* button on a queue row opens, because how far a
  row can be trusted is the question it actually answers
- **Read a note, or a photo of one** — and the proposals it produced
- **Weekly report** — a template extracted from an existing document, issued in its shape

Every section header carries the tools it drew on, so no number on the page is
unattributed. The whole page reads in English or Korean, re-rendered from the same numbers.

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

Verified rendering at 1280px in both languages with every section populated: the queue
with its folded rows and collapsed drafts, the roll-up, the four headline cards, the
constraint table, the load bars, the board-against-code table, and the accounting section
with its overlap note.

The queue costs every option and reads every note before it can answer, which takes about
half a minute. It claims its place on the page from the first paint and says it is working,
rather than landing late and pushing the reader down the page.

## 13. Next steps

From the README's own limitations list, which is where this project keeps what it has not
proven:

- **Vertex AI on a real GCP project**, and Cloud Run — matches the track's suggested stack
  and removes the free tier's daily cap. The team already has the project and a verified
  Cloud Run service; this needs its own service alongside it
- **Firestore for the issue register**, which is a JSON file today
- **Search over the register** (Vertex AI Search), so a recurring fault is found by
  description rather than by category
- **Handwriting against a real photo** — verified only against generated images so far
- **The Outlook calendar against a real tenant** — structure only today (needs an Azure app
  registration)
- **A notes workspace this agent did not shape** — the Notion rows were written by
  `tools/notion_seed.py`, so the columns are the ones it expects
- **Postgres** for the board, matching what the team repository adopted
- **The demo script** (`tools/demo.py`) still walks the eight steps of §4 and stops there.
  It predates the queue, the roll-up and the report templates, so the fastest path through
  the newer half of the product is the dashboard, not the script

Beyond the prototype: the same reconstruction applies to any team whose record of work is
split across a tracker, a repository, a calendar and a document store. Nothing in
`cause.py` is specific to software.

## 14. Project links

- **GitHub Public Repository** — *pending: this lives in a private team repository*
- **Demo Video (≤3 min)** — the full live demo now runs in **40.6 seconds**, so it fits
- **Final Product Link** — *pending: needs a Cloud Run deployment*
