# pmo-agent — a PMO agent that computes an achievable schedule

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

The commits in the demo repository (`onzl-c/echo-app`) look like a real repository's — no keys:

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
commit alone — a wrong link is worse than no link.

```
69 commits → right 58 / wrong 0 / unlinked 11
precision 1.00 | recall 0.84 | mean confidence 0.85
```

The accuracy is **measurable**, because the world simulation knows the answer (`link_truth`).
And when a link was inferred, the result says so — state an inference as fact and nobody can
catch it when it is wrong.

The demo data is honest about difficulty: the first commit on a task names it in full, and
later ones drop into the team's shorthand ("the sign-in flow", "the alert board"), the way real
history reads. That is where linking gets hard, and it is the realistic case.

#### The model only speaks where the rules were silent (`LINK_ASSIST=on`)

The 11 unlinked commits are the ones the rules could not separate from the runner-up. Only
those go to Gemini (`link_assist.py`). It picks **from the candidate list only**, answers
`unknown` when it does not know, and every answer is validated. A link the rules already
settled is out of the model's reach.

```
rules only       right 56 / wrong 0   recall 0.81 | precision 1.00
rules + model    right 68 / wrong 1   recall 0.99 | precision 0.99
```

**Turning it on raises recall and lowers precision.** So it is off by default. A model-decided
link is marked `how="model"`, and the result's note says separately that some links were the
model's call.

*(Those two measurements come from the Korean-language dataset this was first built on; the
English dataset measures 0.84 recall at 1.00 precision for the rules alone.)*

### 2. "A possible schedule" and "an achievable schedule" are different things

Add the constraints one at a time and the finish date moves. Each step's cost is shown
separately:

```
dependencies only      2026-10-12
plus people's capacity 2026-10-30   (+13 business days)
plus meeting time      2026-11-05   (+4 more)

bottleneck: Maya Okonkwo — 18 hours of meetings in the next 10 business days, 7.7 usable days
3 moves → 13 business days earlier
```

Someone holding 38 business days of work while the project finishes in 22 only adds up under
**the assumption that they run eight tasks at once.** Jira assumes it. So do most Gantt plugins.

Meeting data is in neither the board nor the repository. It is only in the calendar — **that is
the reason for connecting more than one tool.**

### 3. The model does not produce the numbers

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

### 4. Every write waits for a person

- the only write tools the model can call are `propose_*`, and they return dry-run results
- the application happens in exactly one place, `approve.py`, which the model cannot call
- it takes a chosen number and then `yes` typed again. `y` does not approve everything
- what was applied is recorded in `logs/approvals.jsonl`
- a write aimed at anything but the sandbox is stopped with `WriteBlocked` — and the attempt
  itself is recorded

### 5. The input is free-form

Nothing has to be structured. A sentence from a meeting note works, and so does **a photo of a
handwritten one**. Gemini reads it, code validates it, a person approves it.

The demo note carries no ticket keys either — working out that "unit tests" means a particular
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
   └─→ calendar   where the time **went**      (past and future meetings)
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
  linking.py      ties commits to tasks with no ticket key                       (stdlib only)
  link_assist.py  asks the model only about links the rules could not settle     (Gemini, off by default)
  signals.py      board status against code activity                             (stdlib only)
  report.py       the weekly report (no model)
  ingest.py       notes and photos → validated change proposals                  (Gemini multimodal)
  tools.py        the Gemini function-calling tool layer
  approve.py      the approval gate — the only write path
  llm.py          Gemini calls, retries, fallback model, Vertex switch
  run.py          the agent loop
  api.py          the FastAPI service and demo UI
  ports.py        adapter interfaces (Protocols — enforced by mypy)
  adapters/       jira · memory (board) / github · memory_repo (repository)
                  ms_calendar · memory_calendar (calendar)
  seeds/          world (the simulation) → board · repo · calendar projections
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

PMO_BACKEND=memory REPO_BACKEND=memory CALENDAR_BACKEND=memory python tools/demo.py
```

### Connected for real

Copy `.env.example` to `.env` and fill it in (it is never committed).

```bash
python tools/check_env.py                      # verifies every item with a real call
python -m pmo_agent.seeds.jira_seed --approve  # create the seed in Jira
python tools/push_demo_repo.py --approve       # create the demo repository on GitHub
python -m pmo_agent.run "is the current schedule realistically achievable"
```

Backends swap through environment variables. The code does not change.

| variable | values | for |
|---|---|---|
| `PMO_BACKEND` | `jira` / `memory` | the board |
| `REPO_BACKEND` | `github` / `memory` | the repository |
| `CALENDAR_BACKEND` | `msgraph` / `memory` | the calendar |
| `LLM_BACKEND` | `aistudio` / `vertex` | the model |
| `LINK_ASSIST` | `off` / `on` | model help for unsettled links |

### As a web service

```bash
uvicorn pmo_agent.api:app --port 8080
```

| endpoint | what it gives |
|---|---|
| `GET /api/schedule` | critical path and tasks at risk |
| `GET /api/capacity` | the achievable schedule and the bottleneck |
| `GET /api/rebalance` | a rebalancing proposal |
| `GET /api/signals` | board against code |
| `GET /api/calendar` | meeting load per owner |
| `POST /api/ingest` | note or photo → proposals (`applied:false`) |
| `POST /api/approve` | apply the chosen proposals (`confirm:true` required) |
| `GET /api/report` | the weekly report (Markdown) |

Container: `docker build -t pmo-agent prototype/pmo-agent`

---

## Checks

The same standards as the repository root (py312, ruff `E/F/I/UP/B`, line-length 100, mypy
`check_untyped_defs`).

```bash
ruff check . && ruff format --check . && mypy && pytest -q
python tools/evaluate.py     # the 12 evaluation cases
```

**333 tests, under four seconds.** No network, no accounts.

| file | what it covers |
|---|---|
| `test_schedule.py` | CPM, business days, delay propagation, cycle detection, status aliases |
| `test_capacity.py` | non-overlapping intervals, no wasted idle time, bottleneck, rebalance |
| `test_availability.py` | meetings → availability, unchanged behaviour with no calendar |
| `test_link_assist.py` | the boundary the model must not cross |
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

The cases live in [evaluation-cases/](evaluation-cases/) — 5 detect, **7 restraint**.
Restraint matters more: missing something is a pity, but claiming something that is not there,
or writing without approval, loses the trust entirely.

---

## Known limitations

- rule-based link recall is **0.84**. The rest is left unlinked — the result of preferring no
  link to a wrong one
- with `LINK_ASSIST=on` recall reaches **0.99**, but precision drops from 1.00 to **0.99**.
  Which trade is right is the using team's call, so it is off by default and offered as a choice
- when a commit email is not tied to a GitHub account, one person can split in two (they are
  merged by email, which is not perfect)
- **1 story point = 1 business day** is an assumption (`DAYS_PER_POINT`). Change the constant
  once the team's velocity is known
- **one concurrent task** and an **eight-hour day** are the defaults. Adjust via the `capacity`
  argument
- the rebalance search is **greedy**. It offers candidates for a person to judge, not an optimum
- it does not model whether a handover is possible, or differences in skill
- handwriting recognition is **verified only against synthetic images** (`tools/make_note.py`).
  A check against real handwriting is still outstanding
- the Outlook calendar is **structure only** and unverified against a real call (it needs an
  Azure app registration)
- the Vertex AI path is **unverified** too (it needs a GCP project)
- the PostgreSQL the team repository recently adopted is not used here yet. The local board is
  a JSON file

## Safety guards

- `.env` is never committed
- no write request leaves for a domain outside `WRITE_ALLOWLIST`. The live Jira is not on it
- every write function defaults to `dry_run`
- the repository and calendar adapters have **no write methods at all** — there is no code path
  that could create anything in someone else's repository or calendar
- every person and every task in the demo data is fictional
