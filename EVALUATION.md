# Evaluation

What we measured, how, and what we have not shown yet. Passing tests is not evidence of AI quality, so every
number below says what it measures and where it comes from. Figures are from 2026-10-05 unless noted. "Local"
means the 10-03 production snapshot loaded on a development machine; "production" means the Cloud SQL database
behind the deployed service.

## Summary

| Area | What we can show | What is still open |
| --- | --- | --- |
| Dictionary pipeline | 11,292 terms, 7,651 verified; every published meaning passed a rule gate that needs a matching reference document | Meaning accuracy against people beyond the 20-case sealed set |
| Human review | 107 review decisions and 121 human-approved meanings in production | Reviews cover about 1.6% of verified terms |
| List filtering | Korea "in use now" list 2,564 → 712 after rules that drop non-meme catalogue entries | Precision and recall: 230-item labelled sample prepared, labels not yet done |
| Risk verdicts | Every verified term judged by rules; 51 avoid, 823 caution, 73 no issue | 6,708 terms lack enough classified evidence to judge |
| Recommendation and copy | Same 12 cases, rounds 4 to 9 (10-10 data): fitting picks 40% → 91%, no risky pick shown as safe, copy usability 2.50/3. Round 10 on production after the 10-14 refresh: 11/12 completed, 12/28 picks fit (more candidates per case), still no risky pick shown as safe | Rounds 4–9: one reviewer, AI-drafted judgments; round 10: AI judges only |
| Auditor (Gemma 4 QLoRA) | Fine-tuned on Kaggle; the JSON verdict format goes from 0/32 to 32/32 | Stopped 10-09: separation of "fix" from "ok" was not established, so the adapter is not used |

## 1. Dictionary pipeline

Gemma (local) and Gemini draft meanings from evidence the pipeline collected. Code decides what is published:
`verification.gate` requires a reference document (Namuwiki, Wikipedia, Know Your Meme, pixiv, Moegirlpedia)
that contains the term, rejects empty or restated meanings, and since October also rejects three kinds of model
output we found in the real data:

| Rejected output | Example | Found among verified meanings |
| --- | --- | ---: |
| A note about the evidence instead of a meaning | "The evidence does not describe its use as a meme." | 162 |
| A meaning that only says it is a meme | "Used as an internet meme." | 56 |
| A guess or the plain word sense | "seems to mean resignation", "used in its general sense" | 78 |

Held-back meanings stay out of the browsing lists and go to the human review queue; the dictionary and copy check
still find them. Meanings a person approved are never overwritten by automatic research.

## 2. Human review

Reviewers approve, correct or reject meanings and set risk levels in the admin queue. Production holds 107 review
decisions and 121 human-approved meanings. The production data refresh copies these decisions onto every new
snapshot and checks that none is lost before switching (`scripts/refresh_production.py`).

## 3. List filtering

Wiki "internet meme" categories also list the people, songs and objects a meme is about, and 10,906 of 11,292
terms came from such categories. Rules drop entries whose meaning only introduces the subject (auditor flag),
catalogue entries with no evidence of use after risk checking, and the rejected outputs in section 1.

- Korea, "in use now": 2,564 → 712 entries; the top entry changed from a politician's name to the slang "밤티".
- Evaluation design: `apps/trend-api/scripts/export_meme_eval_sample.py` draws 230 items in five strata (first
  page, dropped by each reason, kept with and without confirmed use); `score_meme_eval.py` reports stratified
  precision and recall. **The labels are not done yet, so we report no precision or recall.**

## 4. Risk verdicts

Risk levels are rules over classified evidence sentences, quoted reasons and the dictionary's own warnings
(`pipeline/risk.py`). "Avoid" needs at least three risky sentences from two or more sources and, since 10-05,
more than half of the classified uses; this moved four terms such as 懶人包 ("summary pack") from avoid to caution
because their only risky evidence was unrelated news headlines.

| Level (production on 10-05: 7,655 verified terms; the 7,651 above is the local copy) | Terms |
| --- | ---: |
| Avoid | 51 |
| Caution | 823 |
| No issue found | 73 |
| Not enough evidence to judge | 6,708 |

The large "not enough evidence" share is the main gap: evidence classification has reached 247 terms. A developer
review of 20 sampled verdicts agreed 16/20 (80%) before the September 29 rule changes; a team review is pending.

## 5. Recommendation and copy generation

`apps/trend-api/scripts/eval_recommend.py` with request-time Gemini on Vertex AI, run on a read-only copy of the
production database so the evaluation does not use production's daily call ledger. Cases: Korea, Japan and an
English-language group × cosmetics, a drink, running shoes and a budgeting app = 12. Each round fixes something the
previous round's judgments pointed to, then measures the same 12 cases again.

| | Round 4 (10-09) | Round 9 (10-10) | Round 10 (10-15) |
| --- | --- | --- | --- |
| Cases completed end to end | 7 / 12 | 8 / 12 | 11 / 12 |
| Picks that fit the product | 6 / 15 (40%) | **10 / 11 (91%)** | 12 / 28 (43%) |
| The pick the copy was written with fits | – | – | 7 / 11 |
| Risky picks shown as "no issue" | 0 | **0** | **0** |
| Copy uses the meme in its meaning | 4 / 7 | 7 / 8 | 9 / 11 |
| Copy usability (1 unusable – 3 ready) | 2.0 | **2.50** | 2.00 |
| Copy ready to post as is | 2 / 7 | 4 / 8 | 2 / 11 |

What changed between rounds: copy no longer introduces the meme by name ("like …") and is re-checked for that;
non-meme entries (site names, generic words) were removed by reviewer decision; a person fixed the usage words
that rank candidates for 56 of 170 candidates; 36 candidates with no risk verdict got a human
one; mixed-language copy is now rejected and regenerated. Round 8 dropped to 67% after the 10-09 data refresh
brought new, unjudged candidates, which is why round 9 follows the human risk decisions.

Round 10 ran on the production service itself after the 10-14 data refresh (snapshot `20261014T134313-8887867`)
and the 10-15 cleanup (14 non-meme entries retired, two human risk decisions), through the same web API the
Create screen uses. It is not directly comparable to round 9: the refreshed dictionary gives most cases three
candidates instead of one or two (28 picks against 11), and the judgments were made by Claude Sonnet agents with a
written rubric and were not reviewed by a person (rounds 4–9: AI drafts reviewed by one team member). Weak spots
the judges named: Backrooms-core and Wojak suggested for a cushion and a budgeting app, an outfit hashtag (OOTD)
for a cushion, a part-time-job word for a budgeting app; the Korean budgeting-app case ended with no copy because
the rules removed every line. No pick with risk "none" was judged risky.

Latency in round 4: recommend p50 6.6 s (max 14.1 s), create p50 16.3 s (max 27.9 s). Round 10 (production,
cached product briefs on repeat words): recommend p50 1.5 s (max 7.6 s), create p50 11.4 s (max 14.2 s).

Per-round totals are in [`evals/recommend-rounds.csv`](evals/recommend-rounds.csv). To run the cases again
against a database (a read-only copy of production, so the evaluation does not use production's daily call
ledger), from `apps/trend-api`:

```bash
uv run scripts/eval_recommend.py                          # request-time Gemini, 12 cases
uv run scripts/eval_recommend.py --briefs <earlier run>   # reuse that run's product briefs to compare rules only
```

The script measures what rules can (latency, picks, dropped lines by code, risk and lifecycle of picks) and
writes a table for people to fill in: fit, risky picks shown as safe, meaning and usability. Generated copy and
the filled tables stay outside the repository.

**Limits.** Judgments are AI drafts reviewed by one team member, not an independent panel. Four cases return no
pick (Korean cosmetics and three Japanese products): most Japanese cards are fading memes or entertainment-only.
Using a meme image such as Wojak in an ad needs a rights check that the tool does not do.

## 5b. Meaning check: rules alone vs rules + Gemini

Copy check finds a meme with rules and decides risk, lifecycle and market with rules; rules cannot tell whether the
meme is used in its dictionary sense. On 2026-10-17 we wrote 20 sentences for 10 memes in English, Korean and
Japanese – one using the meme as its dictionary entry defines it, one using it against that meaning (a literal or
different sense, e.g. "cooked" as food, 호갱 as a term of endearment for loyal customers) – and fixed the labels
before running. Each sentence went through the product's meaning-check prompt (`pipeline/copycheck.py`
`FIT_PROMPT`, Gemini 3.8 Flash on Vertex AI, temperature 0.1) once.

| | Misused memes flagged | Correct uses kept |
| --- | ---: | ---: |
| Rules alone (no meaning check exists) | 0 / 10 | 10 / 10 |
| Rules + Gemini meaning check | **10 / 10** | **10 / 10** |

Median 5.6 s per sentence, about 370 input and 420 output tokens (including thinking), US$0.04 for all 20. The set is
small and written by the team, so it shows that the check works on clear cases, not its accuracy on real copy.
Cases and verdicts: [`evals/meaning-check-ablation.json`](evals/meaning-check-ablation.json).

## 6. Auditor: Gemma 4 QLoRA (stopped 10-09)

A second model audits each published meaning against its cited sources and answers `ok` or `fix`. We stopped this
experiment on 10-09: the results below did not justify the team-wide reproduction and sealed-set comparison, and
the base model stays in use.

- Training: Gemma 4 12B-it, 4-bit QLoRA (r=16), 319 labelled rows (fix 160, ok 159), 160 steps on a Kaggle T4.
- Labels for training and for the 32-row test split are Claude judgments, not human ones.
- Diagnosis: for each test row we compare the model's log-probability of `{"verdict": "fix"}` and
  `{"verdict": "ok"}`, which works even when a model ignores the format.

| Condition | AUC (95% bootstrap) | Accuracy at 0.5 | Valid JSON verdicts |
| --- | --- | --- | --- |
| Base model | 0.50 (0.28–0.71) | 0.53 | 0 / 32 |
| Base model + 2 examples | 0.69 (0.49–0.87) | 0.41 | 0 / 32 |
| QLoRA, 80 steps | 0.64 (0.43–0.83) | 0.63 | 32 / 32 |
| QLoRA, 160 steps | 0.58 (0.36–0.77) | 0.56 | 32 / 32 |
| Always "fix" | – | 0.59 | – |

Fine-tuning reliably taught the verdict format. Whether it separates "fix" from "ok" is not established: every
interval includes 0.5, and the second epoch did worse than the first. A sealed set of 20 human verdicts (ok 10,
fix 10) was prepared as the independent test; the comparison was not run. The adapter is not used.

## 7. Operations

- Gemini on Vertex AI runs under a monthly spending cap enforced by an in-database ledger (US$20 decided on 10-03; production is
  currently set to US$15), separate from budget alerts. The development stack never calls a paid model.
- First request to the dictionary page took 21.3 s in production (10-05) because the background warm-up gets no
  CPU under request-based billing. The index is now built by the pipeline and stored (local first request 1.9 s);
  this reaches production with the next deployment and data refresh.

## What we have not shown

- Recommendation fit and copy quality judged by more than one person, or beyond the 12 cases.
- Meaning accuracy at scale, and precision and recall of the list filters (labels pending).
- That a fine-tuned auditor beats the base model (experiment stopped).
- Recommendations for every market and product: in round 9 Japan returned no pick for three of four products; in
  round 10 on the refreshed data 11 of 12 cases completed, and the Korean budgeting-app case ended with no copy.
