# Evaluation

What we measured, how, and what we have not shown yet. Passing tests is not evidence of AI quality, so every
number below says what it measures and where it comes from. Figures are from 2026-10-05 unless noted. "Local"
means the 10-03 production snapshot loaded on a development machine; "production" means the Cloud SQL database
behind the deployed service.

## Summary

| Area | What we can show | What is still open |
| --- | --- | --- |
| Dictionary pipeline | 11,292 terms, 7,651 verified; every published meaning passed a rule gate that needs a matching reference document | Meaning accuracy against people beyond the 20-case sealed set |
| Human review | 107 review decisions and 121 human-approved meanings in production | Reviews cover about 1.6% of verified meanings |
| List filtering | Korea "in use now" list 2,564 → 712 after rules that drop non-meme catalogue entries | Precision and recall: 230-item labelled sample prepared, labels not yet done |
| Risk verdicts | Every verified term judged by rules; 51 avoid, 823 caution, 73 no issue | 6,708 terms lack enough classified evidence to judge |
| Recommendation and copy | 20-case run: 12/20 complete for Korea, Japan and Taiwan | Fit and meaning accuracy judged by people; Thailand and Indonesia return nothing |
| Auditor (Gemma 4 QLoRA) | Fine-tuned on Kaggle; the JSON verdict format goes from 0/32 to 32/32 | Separation of "fix" from "ok" is not established (AUC interval includes 0.5) |

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

| Level (production, verified terms) | Terms |
| --- | ---: |
| Avoid | 51 |
| Caution | 823 |
| No issue found | 73 |
| Not enough evidence to judge | 6,708 |

The large "not enough evidence" share is the main gap: evidence classification has reached 247 terms. A developer
review of 20 sampled verdicts agreed 16/20 (80%) before the September 29 rule changes; a team review is pending.

## 5. Recommendation and copy generation

`apps/trend-api/scripts/eval_recommend.py`: 5 markets × 4 products = 20 cases, local model, run 2026-09-30.

| | Round 2 | Round 3 |
| --- | --- | --- |
| Cases completed end to end | 5 / 20 | 12 / 20 (Korea, Japan, Taiwan) |
| Memes recommended | 21 | 60 |

Thailand and Indonesia returned no recommendations. Of the 60 recommendations, 48 had an unknown lifecycle and 51
an undecided risk, so "use it now?" could not be judged for most of them. Generated copy is re-checked by rules
(the chosen meme is present, no profanity, X length, the brief's "avoid" list); in ten runs of the same Japan case
one failed. **Fit and meaning accuracy have not been judged by people.**

## 6. Auditor: Gemma 4 QLoRA

A second model audits each published meaning against its cited sources and answers `ok` or `fix`.

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
fix 10) is the independent test; the comparison on it is pending. The adapter is not used in production.

## 7. Operations

- Gemini on Vertex AI runs under a monthly spending cap of US$20 enforced by an in-database ledger, separate from
  budget alerts. The development stack never calls a paid model.
- First request to the dictionary page took 21.3 s in production (10-05) because the background warm-up gets no
  CPU under request-based billing. The index is now built by the pipeline and stored (local first request 1.9 s);
  this reaches production with the next deployment and data refresh.

## What we have not shown

- People judging recommendation fit, generated copy and meaning accuracy at scale.
- Precision and recall of the list filters (labels pending).
- That the fine-tuned auditor is better than the base model with examples.
- Coverage outside Korea, Japan and Taiwan; English meanings exist for 121 terms.
