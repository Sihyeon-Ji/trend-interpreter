# Evaluation cases

The **5 success / 5 failure-and-edge** cases the team workflow document asks for (there are 7
on the restraint side). `../tools/evaluate.py` runs them.

```bash
cd prototype/pmo-agent
python tools/evaluate.py          # the result table
python tools/evaluate.py --json   # machine-readable (exit 1 on failure)
```

## Where the answer key comes from

Answers are never hardcoded into a case. `src/pmo_agent/seeds/world.py` simulates the project
one day at a time and records **what the real cause was** in `World.truths`. The evaluation
reads that answer key at run time.

```
world.simulate()  →  truths (the answer key)  →  referenced by each case's truth field
                  →  board / repo / calendar projections  →  the engine computes
                                                              ↓
                                                        do they agree?
```

It has to work this way because task keys shift with the date. Write `ECHO-8` into a case and
it breaks tomorrow.

## Two groups

### detect — does it find what was planted

| id | what was planted |
|---|---|
| `root-cause-visible` | an external IdP spec change blocked authentication for 8 business days |
| `stalled-detected` | a task started and then dropped (the board says In Progress) |
| `undeclared-progress-detected` | there are commits, but the board says To Do |
| `premature-done-detected` | the board says Done while a pull request is open |
| `meeting-overload-detected` | whoever has the most meetings ahead |

### restraint — does it refrain from inventing

| id | what it checks |
|---|---|
| `no-evidence-no-warning` | with no author, timing, path or vocabulary, it links nothing |
| `cycle-is-error-not-crash` | a dependency cycle comes back as an error, not an exception |
| `invented-key-becomes-question` | a key the model made up is never applied; it becomes a question |
| `no-write-without-approval` | with nothing chosen, no write call goes out at all |
| `no-calendar-no-meeting-claim` | with no calendar, it never claims meetings were accounted for |
| `inference-declared` | an inferred link is declared an estimate, with a confidence |
| `assist-stays-in-candidates` | even with the model on, no invented key and no overturned rule link |

**The second group matters more.** Missing something is a pity; claiming something that is not
there, or writing without approval, loses the trust entirely.

## The shape of a case

```json
{
  "id": "stalled-detected",
  "group": "detect",
  "check": "signals_mismatch",
  "truth": "stalled",
  "ask": "is anything out of step between the board and the actual code",
  "why": "A task was started and then dropped"
}
```

- `check` — a check function registered in `CHECKS` in `tools/evaluate.py`
- `truth` — the kind of answer to look up in `World.truths` (the detect group only)
- `ask` — the sentence a person would really put to the agent. It is the input when the model
  path is wired in

## No ticket keys

The commits in the demo repository carry **no** `ECHO-12`-style key. Real repositories are like
that, and joining things up when there is no key is what this agent does. Put the keys in and
we would only ever solve the easy version, the one string matching already handles.

The same goes for the handwritten demo note (`tools/make_note.py`): it names the work the way a
person would, and `ingest.resolve()` has to work out which task each line means.

`src/pmo_agent/linking.py` joins by author, timing, vocabulary and path, and leaves it alone
when it is close. The correct links live separately, in `world.to_repo()`'s `link_truth`, so
accuracy can be measured (currently precision 1.00 / recall 0.84 — the result of preferring no
link to a wrong one).

With `LINK_ASSIST=on`, only the links the rules gave up on go to the model. The evaluation
checks the boundary with a **fake model**: inventing a key outside the candidates, or
overturning a link the rules settled, is a failure.

## Not covered here

- **the quality of the model's prose** — code computes the numbers and the model only quotes
  them, so this only checks that the calculation is right. Evaluating prose is a separate job
- **real handwriting accuracy** — verified against synthetic images only (`tools/make_note.py`)
- **Gemini calls** — the evaluation never touches the network. It has to run without a key to
  belong in CI. The model assist's *performance* (recall 0.99 / precision 0.99) was measured by
  hand, not here
