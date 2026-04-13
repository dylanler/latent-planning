# Broad Evidence Report

This report evaluates the family-transfer slice of the hypothesis: whether the same managed scaffold helps across more than one synthetic benchmark shape.

## What Would Count As Broader Support

- task-family transfer: the scaffold should help on more than one benchmark shape

- domain transfer: the advantage should survive prose, arithmetic-style ledgers, and code-like text

- bookkeeping ablation: simply making more calls should not be enough; removing deterministic support should reduce performance

- hierarchical robustness: recursive routing should help when flat decomposition starts to break

- model transfer: the same pattern should also survive a model change, which is reported separately in [model_transfer_report.md](/Users/dylan/learning-projects/latent-planning/docs/model_transfer_report.md)

## Local Suite Setup

- families: prose retrieval, ledger aggregation, code-like localization

- shared configuration: 4 sections, 6 distractors per section, context scale 3, seeds 0/1/2

- methods: baseline, no-validator, validator-backed managed, recursive

## Family Results

| Family | Task type | Runs | Avg chars | Baseline acc | No-validator acc | Managed acc | Recursive acc | Baseline latency (s) | No-validator latency (s) | Managed latency (s) | Recursive latency (s) | Baseline tokens | No-validator tokens | Managed tokens | Recursive tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Prose records | retrieval in prose | 3 | 9446 | 0.00 | 1.00 | 1.00 | 0.33 | 1.29 | 1.98 | 2.10 | 4.42 | 2263 | 2730 | 2838 | 2916 |
| Ledger aggregation | retrieval plus arithmetic | 3 | 9075 | 0.00 | 0.00 | 0.67 | 0.67 | 0.79 | 2.14 | 2.28 | 4.11 | 2478 | 2987 | 3051 | 3333 |
| Code localization | code-like localization | 3 | 15128 | 0.00 | 0.67 | 1.00 | 0.67 | 2.29 | 2.31 | 2.34 | 3.88 | 3176 | 3598 | 3714 | 3289 |

## Aggregate Accuracy Means

| Method | Mean accuracy across families |
| --- | --- |
| Baseline | 0.00 |
| No-validator | 0.56 |
| Managed | 0.89 |
| Recursive | 0.56 |

## Aggregate Compute Means

| Method | Mean total tokens across families |
| --- | --- |
| Baseline | 2639 |
| No-validator | 3105 |
| Managed | 3201 |
| Recursive | 3179 |

## Scorecard

| Claim | Result |
| --- | --- |
| Managed beats baseline across families | 3/3 |
| No-validator beats baseline across families | 2/3 |
| Recursive beats flat managed across families | 0/3 |
| Recursive matches or beats flat managed across families | 1/3 |

## Interpretation

If the hypothesis were only an artifact of one synthetic retrieval task, the improvement should disappear when the surface form changes. Instead, the same pattern persisting across prose, arithmetic-ledger, and code-like tasks is stronger evidence that the bottleneck is partly in decomposition rather than only in raw model weights.

At the same time, the no-validator condition remains much weaker than the validator-backed manager. That means the broad claim still cannot be stated as 'the model alone already does everything once decomposed.' The more accurate statement is that the model plus a better management policy and exact support code unlocks capabilities that one-shot prompting leaves on the table.

The compute-normalized view matters too. Managed and recursive methods use materially more tokens than the baseline, so this is not free capability. The evidence is therefore about better capability per task, not magical capability without extra compute.

## Conclusion

This family-transfer suite is decisively positive on its own terms: the managed scaffold beats baseline in all three synthetic families. It is only one slice of the overall verdict, but it now lines up with the separate cross-model and real-task reports instead of pointing to an unresolved next step.
