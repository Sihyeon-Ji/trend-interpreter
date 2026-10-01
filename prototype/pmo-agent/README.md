# pmo-agent – a PMO agent that computes an achievable schedule

A standalone candidate project under `prototype/`. It is kept apart from the repository root's
development stack and uses only its own dependencies.

**Code computes the schedule numbers, Gemini reads and explains them, and nothing is written
until a person has approved it.**

---

## What is different about it

### 1. It joins the board to the code with no ticket key

Most "Jira ↔ GitHub integrations" assume a convention: write `ECHO-12` in the commit message.
Few teams actually keep that convention, and **joining things up when they do not is what this
agent is for.** Assume the key and you have built a tool that only works for teams who were
already integrated.

The commits in the demo repository (`onzl-c/echo-app`) look like a real repository's – no keys:

```
fix: handle edge cases in search              apps/api/src/builder_cup/search.py
refactor: tidy the response shape of …        apps/api/src/builder_cup/qa-round1.py
docs: draft information architecture          docs/information-architecture.md
```

`linking.py` joins them with four signals, all observable from the board and the repository:

| signal | what it asks | weight |
|---|---|---|
| author | did the commit author own that task | 0.30 |
| words | do the message and branch share vocabulary with the title | 0.35 |
| path | do the changed files match the task's area | 0.20 |
| time | does the commit date fall in the task's active window | 0.15 |

**It links only when the winner pulls clear of the runner-up.** When it is close, it leaves the
commit alone – a wrong link is worse than no link.

```
$ python tools/measure_links.py --dates 8

2026-09-21   53 commits  right 49 / wrong 0 / unlinked 4   precision 1.00 | recall 0.93
2026-10-02   49 commits  right 42 / wrong 0 / unlinked 7   precision 1.00 | recall 0.86
2026-11-04   52 commits  right 48 / wrong 0 / unlinked 4   precision 1.00 | recall 0.92
…
worst of 8: precision 1.00 | recall 0.86 – no wrong links at any date
```

**precision 1.00**, **recall 0.85** at worst, measured at **8 dates** – roughly 410 commits,
not one lucky run. The two are not equally important and are not treated as such. A wrong
link puts somebody else's commit on a task and every number built on top inherits it
silently, so there is no acceptable rate of that and `test_linking_accuracy.py` admits
none. A commit it refuses to place is merely reported as unlinked, which is the restraint
working; recall has a floor rather than a target.

The accuracy is **measurable** because the world simulation knows the answer (`link_truth`),
and the adapters never expose it – the linker sees what a real repository would give it and
nothing else. The measurement runs at several dates because the world regenerates from
`today`, so a rule that happens to suit this week shows up straight away. And when a link
was inferred, the result says so: state an inference as fact and nobody can catch it when
it is wrong.

The demo data is honest about difficulty: the first commit on a task names it in full, and
later ones drop into the team's shorthand ("the sign-in flow", "the alert board"), the way real
history reads. That is where linking gets hard, and it is the realistic case.

#### The model only speaks where the rules were silent (`LINK_ASSIST=on`)

The 7 unlinked commits are the ones the rules could not separate from the runner-up. Only
those go to Gemini (`link_assist.py`). It picks **from the candidate list only**, answers
`unknown` when it does not know, and every answer is validated. A link the rules already
settled is out of the model's reach.

```
$ python tools/measure_links.py --assist

rules only       right 53 / wrong 0 / unlinked 8   recall 0.87 | precision 1.00
rules + model    right 61 / wrong 0 / unlinked 0   recall 1.00 | precision 1.00
                 the model placed 8 of the 8 commits the rules left open
```

That last line is there because of a mistake this made while being measured. A
rate-limited call leaves the commit unlinked, which is honest at runtime – but from the
outside an assisted run where every call was refused is **indistinguishable** from a
rules-only run, and it was reported as assisted twice before anyone noticed the numbers
had not moved. `assistant()` now records what the model was asked and what came back, and
the measurement refuses to label a run assisted when the model answered nothing.

It is still off by default, and the reason is worth stating plainly: **that result is three
runs on one 63-commit dataset.** On the Korean dataset this was first built against, the same
mechanism reached 0.99 recall while dropping precision to 0.99 – one wrong link. A wrong link
is the thing the rules exist to avoid, so paying per call for a result that can go either way
is the caller's decision, not a default.

A model-decided link is marked `how="model"`, and the result's note says separately that some
links were the model's call rather than the rules'.

### 2. It answers "why", which no single tool can

Every other part of this says *what* is wrong: this task will slip, the board and the code
disagree. A PM cannot act on that. They need why.

No one tool holds the answer. The board knows a dependency is open. The repository knows the
last commit was three weeks ago – and that the owner kept committing elsewhere. The calendar
knows that person spent those same days in incident calls. And a meeting note, if anyone
wrote one, holds the only sentence that says what the incident actually *was*. Put all four
side by side:

```
ECHO-16 [Build] Authentication  silent 10d  (Maya Okonkwo)
  [notes   ] External IdP spec change: the identity provider changed its token
             format, forcing a redesign. Authentication cannot move until we
             agree the new shape.
             written in: Incident response – Maya Okonkwo, 2026-09-04
  [calendar] Maya Okonkwo lost 22.0h to meetings over this stretch,
             15.0h of it "Incident response"
  [repo    ] Maya Okonkwo made 2 commits in this stretch, none of them here
  -> 4.5 of 11 silent business days are accounted for; 6.5 are not.
     They left a trace in the repository or the calendar on 9 of those 11 days;
     on the other 2 there is none at all, which is a blind spot rather than a reason.
```

**The days are counted once each.** The causes are not added together: a person who spent
Tuesday in meetings *and* committed to another task on Tuesday has one Tuesday, not two.
Adding them up is the obvious implementation and it was the one here – on real data two
causes came to 15.4 days of a 16-day silence when the honest figure was 6.6. Worse, it was
invisible: the total was capped at the length of the window, so the overcount came out as
"all 14 silent business days are accounted for", the most confident sentence this module
can produce. **A cap is not a check.** Each cause still reports what it accounts for on
its own, and the report states how far they overlap, so the list and the total can both
be read as true.

That last line separates two things that land in the same leftover number and are opposite
problems. A day the owner was demonstrably at work – a commit to another task, a meeting –
and did not come here is a question to ask them. A day they left no trace anywhere is not
unexplained so much as **unobserved**, and the question is which system nobody connected.
Reported as one number, "5.2 days unexplained" reads like ignorance in both cases; it is
only ignorance in the second. Every commit counts towards a trace, including the ones the
linker could not place – using only the linked set would turn the agent's own uncertainty
into somebody's missing week.

That note carries no ticket key – a team writing minutes does not annotate them with issue
IDs – so tying it to the task is the same inference problem as tying a commit to one, and
`linking.py` does both. A note that fits two tasks equally well is used for neither.

The notes come from Notion (`NOTES_BACKEND=notion`), which is where most teams actually keep
them, or from the local archive for a demo without accounts. Both are read-only: there is no
method on either adapter that edits a page, because an agent has no business rewriting what
someone typed in a meeting.

When there are no notes to read, the answer says so and why – a backend that is configured
but empty looks exactly like one that was never set up, and an explanation that quietly
arrives thinner is the failure this whole project is built to avoid.

The Notion database needs three columns: a **Title**, a **Date**, and a person or short text
column for the author. Their names do not matter – they are matched by type, so a workspace
that calls them anything still works.

To fill an empty one:

```bash
python tools/notion_seed.py --approve   # creates the pages and the two missing columns
python tools/notion_csv.py              # or a CSV for ⋯ → Merge with CSV, by hand
```

Both are *setup* scripts. The adapter itself stays read-only – an agent writing into
someone's workspace is not a capability worth having – and the seeder refuses a database
that already has rows, because an empty one is a demo fixture and a full one is somebody's
actual notes.

This is the argument for connecting a fourth tool rather than polishing one: the status is
in Jira, the silence is in Git, the hours are in the calendar, and the sentence is in the
minutes. No single one of them can answer the question.

**Every cause carries the business days it accounts for**, so they rank by how much they
actually explain, and the remainder is stated out loud:

```
ECHO-32 [Hardening] Security review  silent 17d
  -> 8.2 of 17 silent business days are accounted for; 8.8 are not.
```

When nothing explains it, that is the answer – `cause.py` never names a cause it cannot
show evidence for. A named cause ends the conversation; an admitted gap starts one.

### 3. "A possible schedule" and "an achievable schedule" are different things

Add the constraints one at a time and the finish date moves. Each step's cost is shown
separately:

```
dependencies only      2026-10-12
plus people's capacity 2026-10-30   (+13 business days)
plus meeting time      2026-11-05   (+4 more)

bottleneck: Maya Okonkwo – 18 hours of meetings in the next 10 business days, 7.7 usable days
3 moves → 13 business days earlier
```

Someone holding 38 business days of work while the project finishes in 22 only adds up under
**the assumption that they run eight tasks at once.** Jira assumes it. So do most Gantt plugins.

Meeting data is in neither the board nor the repository. It is only in the calendar – **that is
the reason for connecting more than one tool.**

### 4. The model does not produce the numbers

- schedule, delay, critical path and load all come from `schedule.py` / `capacity.py`
  (standard library only)
- the system prompt requires Gemini to quote values from tool responses and nothing else
- a task key the model invented (`ECHO-9999`) or a relative date ("next Tuesday") is caught by
  `ingest.validate()` and turned into **a question for a person**

A test pins it down:

```python
def test_the_tool_layer_never_passes_approve_true(self):
    self.assertNotIn("approve=True", inspect.getsource(tools))
```

### 5. Every write waits for a person

- the only write tools the model can call are `propose_*`, and they return dry-run results
- the application happens in exactly one place, `approve.py`, which the model cannot call
- it takes a chosen number and then `yes` typed again. `y` does not approve everything
- what was applied is recorded in `logs/approvals.jsonl`
- a write aimed at anything but the sandbox is stopped with `WriteBlocked` – and the attempt
  itself is recorded

### 6. The input is free-form

Nothing has to be structured. A sentence from a meeting note works, and so does **a photo of a
handwritten one**. Gemini reads it, code validates it, a person approves it.

The demo note carries no ticket keys either – working out that "unit tests" means a particular
task is `ingest.resolve()`'s job. Where a phrase genuinely fits two tasks, it becomes a
question rather than a guess.

---

## The data comes from one story

Fake data built per tool **cannot answer "why was it late".** So the project is simulated one
day at a time, and each tool records only its own cross-section of that world.

```
world.simulate()          what actually happened (18 business days back + 25 forward)
   │  meetings take time first → what is left pushes tasks → the incident blocks one
   │
   ├─→ board      what people **wrote down**   (where it diverges is the signal)
   ├─→ repo       what was actually **done**   (commits and PRs, no ticket keys)
   ├─→ calendar   where the time **went**      (past and future meetings)
   └─→ notes      what was **decided**         (prose, no ticket keys either)
```

The story planted in it: *an external IdP changed its spec, authentication stalled for 8
business days, and its owner spent that stretch in incident calls.* That causal chain is
scattered across three tools, and the agent reconstructs it by lining them up.

`World.truths` is the answer key. It records what the real cause was, and the evaluation checks
that the engine finds it.

---

## Layout

```
src/pmo_agent/
  schedule.py     CPM critical path, business days, delay propagation, forecast  (stdlib only)
  capacity.py     resource-constrained scheduling, bottleneck, rebalance search  (stdlib only)
  availability.py meeting hours → availability                                   (stdlib only)
  cause.py        why a task stopped, from all four tools                        (stdlib only)
  familiarity.py  who has worked where, so a handover is one that could happen    (stdlib only)
  linking.py      ties commits to tasks with no ticket key                       (stdlib only)
  link_assist.py  asks the model only about links the rules could not settle     (Gemini, off by default)
  signals.py      board status against code activity                             (stdlib only)
  report.py       the weekly report (no model)
  ingest.py       notes and photos → validated change proposals                  (Gemini multimodal)
  tools.py        the Gemini function-calling tool layer
  approve.py      the approval gate – the only write path
  llm.py          Gemini calls, retries, fallback model, Vertex switch
  run.py          the agent loop
  api.py          the FastAPI service and demo UI
  ports.py        adapter interfaces (Protocols – enforced by mypy)
  adapters/       jira · memory (board) / github · memory_repo (repository)
                  ms_calendar · memory_calendar (calendar)
                  notion · memory_notes (meeting notes)
  seeds/          world (the simulation) → board · repo · calendar · notes projections
```

The calculation has no external dependencies. **Every unit test runs with no API key and no
account.**

The Protocols in `ports.py` make "adapters of the same kind have the same shape" a type-check
rather than a claim. The moment they went in, they exposed that `Jira.search` took its
arguments in a different order from the local board and so was not actually interchangeable.

---

## Running it

### Without any account

```bash
cd prototype/pmo-agent
pip install -e ".[dev]"

python -m pmo_agent.seeds.board      # 40 issues
python -m pmo_agent.seeds.repo       # the repository (commits and PRs)
python -m pmo_agent.seeds.calendar   # the calendar (past and future meetings)
python -m pmo_agent.seeds.notes      # the meeting notes

PMO_BACKEND=memory REPO_BACKEND=memory python tools/demo.py
```

### Connected for real

Copy `.env.example` to `.env` and fill it in (it is never committed).

```bash
python tools/check_env.py                      # verifies every item with a real call
python -m pmo_agent.seeds.jira_seed --approve  # create the seed in Jira
python tools/push_demo_repo.py --approve       # create the demo repository on GitHub
python -m pmo_agent.run "is the current schedule realistically achievable"
```

**Against a real GitHub repository, turn on `REPO_FILES`.** The commit list API does not
include which files a commit touched, and the path is what separates two tasks the same
person has open. Fetching them costs one API call per commit and buys roughly a quarter
more links at noticeably higher confidence (measured on `onzl-c/echo-app`: 39 links at
0.73 → 50 at 0.83). The local backend has the paths already and ignores the flag.

Those answers are kept in `data/commit_files.json`, which took the same repository from
**50 seconds to 5** on the second run – and a demo reads the snapshot more than once. This
is the one cache here that needs no staleness rule: a git sha *is* the hash of the commit's
content, so the files it touched cannot change. What the cache deliberately does **not**
keep is a failed call. That yields an empty file list too, and remembering it would turn
one bad network moment into a commit that looks permanently empty. Delete the file to
rebuild it.

**The live data is a snapshot and drifts.** The simulation rebuilds its dates from *today*
on every run; a seeded Jira board and a pushed repository are frozen at the moment they were
created. After a day or two nobody notices. After a week the board says a task is due next
Wednesday while the world has it three weeks late, and every explanation built on top reads
wrong. Before a demo, re-sync:

```bash
python tools/retitle_jira.py --approve            # summaries, owners, due dates, statuses
python tools/push_demo_repo.py --approve --reset  # commits and pull requests
```

`retitle_jira.py` updates the existing issues rather than seeding new ones, so the keys stay
put. It restores statuses too, which is what makes the demo repeatable – run it with
`--approve` once and a task moves to Done, and without putting the board back the next run
has nothing left to change. Note that recreating the repository resets every pull request's creation time, so any
"waiting on review for N days" signal starts from zero again.

Backends swap through environment variables. The code does not change.

| variable | values | for |
|---|---|---|
| `PMO_BACKEND` | `jira` / `memory` | the board |
| `REPO_BACKEND` | `github` / `memory` | the repository |
| `CALENDAR_BACKEND` | `memory` / `msgraph` | the calendar – local unless Graph is set up |
| `NOTES_BACKEND` | `notion` / `memory` | the meeting notes |
| `LLM_BACKEND` | `aistudio` / `vertex` | the model |
| `LINK_ASSIST` | `off` / `on` | model help for unsettled links |
| `REPO_FILES` | `off` / `on` | fetch each commit's paths (slower, better links) |
| `REPO_SNAPSHOT_TTL` | `60` | seconds to reuse one repository reading; `0` reads every time |

### As a web service

```bash
uvicorn pmo_agent.api:app --port 8080
```

| endpoint | what it gives |
|---|---|
| `GET /api/board` | which backends are connected |
| `GET /api/projects` | every project this agent watches, and what kind of work each is |
| `GET /api/queue` | what is waiting for a person today – the front door |
| `GET /api/rollup` | every project on one line, worst first |
| `GET /api/health` | an operations project's queue, instead of a finish date |
| `GET /api/sources` | the four tools behind every answer, and which one can write |
| `GET /api/schedule` | critical path and tasks at risk |
| `GET /api/capacity` | the achievable schedule and the bottleneck |
| `GET /api/rebalance` | a rebalancing proposal |
| `GET /api/signals` | board against code |
| `GET /api/cause` | why a task stopped (empty key = the worst offenders) |
| `GET /api/calendar` | meeting load per owner |
| `POST /api/ingest` | note or photo → proposals (`applied:false`) |
| `POST /api/approve` | apply the chosen proposals (`confirm:true` required) |
| `GET /api/approvals` | what was applied recently (the audit log) |
| `GET /api/report` | the weekly report (Markdown) |

Container: `docker build -t pmo-agent prototype/pmo-agent`

---

## Checks

The same standards as the repository root (py312, ruff `E/F/I/UP/B`, line-length 100, mypy
`check_untyped_defs`).

```bash
ruff check . && ruff format --check . && mypy && pytest -q
python tools/evaluate.py         # the 15 evaluation cases
python tools/evaluate.py --dates 13   # and at 13 dates, four months out
python tools/measure_links.py    # link precision and recall against the answer key
```

**768 tests, around twenty seconds.** No network, no accounts – every one of them runs on
a laptop with the wifi off. Most finish in under a second. The slow ones are the honest
kind: `test_readme.py` spawns a collection pass to check that the number in this very
sentence is still true, and `test_linking_accuracy.py` rebuilds the world at eight
different dates because one good day is not a result.

| file | what it covers |
|---|---|
| `test_schedule.py` | CPM, business days, delay propagation, cycle detection, status aliases |
| `test_capacity.py` | non-overlapping intervals, no wasted idle time, bottleneck, rebalance |
| `test_availability.py` | meetings → availability, unchanged behaviour with no calendar |
| `test_cause.py` | root-cause reconstruction, and silence when there is no evidence |
| `test_familiarity.py` | handover plausibility, and getting out of the way without evidence |
| `test_link_assist.py` | the boundary the model must not cross |
| `test_linking_accuracy.py` | the headline precision and recall, measured at several dates |
| `test_github_cache.py` | the changed-file cache, and what must never be cached |
| `test_projects.py` | the project registry, and the keys it refuses |
| `test_reconcile.py` | notes against the board, and the differences only |
| `test_register.py` | the issue register: identity, states, and what it refuses to merge |
| `test_health.py` | operations metrics, and the finish date it never produces |
| `test_rollup.py` | the roll-up: each kind's own headline, and the unknowns it keeps |
| `test_render.py` | report templates, and the content the spec has nowhere to put |
| `test_decide.py` | the options table, their expiry, and the choice it refuses to make |
| `test_warehouse.py` | the flat rows, and the finish date a queue never gets |
| `test_extract.py` | a template read from a document, and the headings it cannot fill |
| `test_queue.py` | the day's queue: what it refuses to invent, and what it never does |
| `test_i18n_queue.py` | the Korean queue, written from numbers, and the particles it never guesses |
| `test_notion.py` | reading a real Notion payload, and staying the same shape as the local archive |
| `test_readme.py` | this file's own checkable claims still match the code |
| `test_signals.py` | divergence detection, identity merge, silence without evidence |
| `test_tools.py` | declarations match implementations, read tools never write |
| `test_ingest.py` | image encoding, task matching, date validation |
| `test_approve.py` | nothing applies without approval, the audit log |
| `test_llm.py` | retries, fallback, Vertex request assembly |
| `test_jira_guard.py` | write-domain blocking |
| `test_memory_board.py` | the two adapters have the same shape |
| `test_offline_loop.py` | seed quality plus the whole loop |
| `test_report.py` | report numbers agree with the calculation |
| `test_evaluation.py` | every evaluation case passes |

The cases live in [evaluation-cases/](evaluation-cases/) – 7 detect, **8 restraint**.
Restraint matters more: missing something is a pity, but claiming something that is not there,
or writing without approval, loses the trust entirely.

---

## Known limitations

- rule-based link recall is **0.89** on the simulated repository, where every signal is
  present. Against the real one it is lower: commit emails are not tied to GitHub accounts,
  and the paths cost an API call each (see `REPO_FILES` above) The rest is left unlinked – the result of preferring no
  link to a wrong one
- with `LINK_ASSIST=on` the remaining links were all correct across three runs here, but the
  same mechanism cost a point of precision on the earlier dataset. One dataset is not a
  measurement, so it stays off by default and is offered as a choice
- when a commit email is not tied to a GitHub account, one person can split in two (they are
  merged by email, which is not perfect)
- **1 story point = 1 business day** is an assumption (`DAYS_PER_POINT`). Change the constant
  once the team's velocity is known
- **one concurrent task** and an **eight-hour day** are the defaults. Adjust via the `capacity`
  argument
- the rebalance search is **greedy**. It offers candidates for a person to judge, not an optimum
- a handover is only offered to someone the repository shows has committed in that area
  (`familiarity.py`). That is evidence of having been there, not of being the right person –
  it cannot see who is learning it, who is on leave, or who would rather not. And it needs
  file paths, so against a real repository it needs `REPO_FILES=on` to work at all; when it
  cannot judge, the proposal says it was not vetted rather than implying it was
- the live Jira board and demo repository are snapshots. They drift from the simulation as
  soon as the date moves, so they need re-syncing before a demo (see above)
- a cause is only as good as what the tools recorded. Someone who was ill, or stuck on a
  problem they never wrote down, leaves no trace – `cause.py` counts those days and says
  they are a blind spot rather than guessing at one, which is the honest answer but not a
  satisfying one. It cannot tell leave from a repository nobody connected, and does not try
- handwriting recognition is **verified only against synthetic images** (`tools/make_note.py`).
  A check against real handwriting is still outstanding
- the Outlook calendar is **structure only** and unverified against a real call (it needs an
  Azure app registration)
- the Notion adapter reads a live workspace and the demo database now holds the notes, so a
  live run's "what was decided" line comes out of Notion. What is *not* proven is a workspace
  this agent did not shape: the rows were written by `tools/notion_seed.py`, so the columns
  are the ones it expects. A team's real notes database will be messier
- the Vertex AI path is **unverified** too (it needs a GCP project)
- the PostgreSQL the team repository recently adopted is not used here yet. The local board is
  a JSON file

## Safety guards

- `.env` is never committed
- no write request leaves for a domain outside `WRITE_ALLOWLIST`. The live Jira is not on it
- every write function defaults to `dry_run`
- the repository and calendar adapters have **no write methods at all** – there is no code path
  that could create anything in someone else's repository or calendar
- every person and every task in the demo data is fictional
