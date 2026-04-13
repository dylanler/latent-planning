# Broad Evidence Report

This report does not prove the broad hypothesis, but it defines what broader support should look like and evaluates the first local suite against that bar.

## What Would Count As Broader Support

- task-family transfer: the scaffold should help on more than one benchmark shape

- domain transfer: the advantage should survive prose, arithmetic-style ledgers, and code-like text

- bookkeeping ablation: simply making more calls should not be enough; removing deterministic support should reduce performance

- hierarchical robustness: recursive routing should help when flat decomposition starts to break

- model transfer: ideally the same pattern should later be rerun on more than one model family

## Local Suite Setup

- families: prose retrieval, ledger aggregation, code-like localization

- shared configuration: 4 sections, 6 distractors per section, context scale 3, seeds 0/1/2

- methods: baseline, no-validator, validator-backed managed, recursive

## Family Results

| Family | Task type | Runs | Avg chars | Baseline acc | No-validator acc | Managed acc | Recursive acc | Baseline latency (s) | No-validator latency (s) | Managed latency (s) | Recursive latency (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Prose records | retrieval in prose | 3 | 9446 | 0.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.11 | 0.99 | 1.92 |
| Ledger aggregation | retrieval plus arithmetic | 3 | 9075 | 0.00 | 0.00 | 0.67 | 0.67 | 0.57 | 1.23 | 1.00 | 1.65 |
| Code localization | code-like localization | 3 | 15128 | 0.00 | 0.67 | 1.00 | 1.00 | 0.57 | 1.21 | 1.07 | 1.96 |

## Aggregate Accuracy Means

| Method | Mean accuracy across families |
| --- | --- |
| Baseline | 0.00 |
| No-validator | 0.56 |
| Managed | 0.89 |
| Recursive | 0.89 |

## Scorecard

| Claim | Result |
| --- | --- |
| Managed beats baseline across families | 3/3 |
| No-validator beats baseline across families | 2/3 |
| Recursive beats flat managed across families | 0/3 |
| Recursive matches or beats flat managed across families | 3/3 |

## Interpretation

If the hypothesis were only an artifact of one synthetic retrieval task, the improvement should disappear when the surface form changes. Instead, the same pattern persisting across prose, arithmetic-ledger, and code-like tasks is stronger evidence that the bottleneck is partly in decomposition rather than only in raw model weights.

At the same time, the no-validator condition remains much weaker than the validator-backed manager. That means the broad claim still cannot be stated as 'the model alone already does everything once decomposed.' The more accurate statement is that the model plus a better management policy and exact support code unlocks capabilities that one-shot prompting leaves on the table.

## Conclusion

The broader local suite supports a stronger but still bounded claim: management advantages transfer across multiple task families, not just the original prose retrieval benchmark. That is meaningful evidence for the mismanaged-geniuses hypothesis, but not a proof of the full general version yet. To get closer to that, the next step is model transfer and a real codebase benchmark rather than synthetic text alone.
