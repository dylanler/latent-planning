# Broad Hypothesis Scorecard

The narrow version of the hypothesis is:

- the same model can look much more capable when the task is decomposed well

The broader version asks for something stronger:

- the advantage should transfer across task families
- it should survive a model change
- it should show up on at least one real task
- it should remain defensible after reporting compute

## Proof Conditions

| Condition | Why it matters | Status in this repo |
| --- | --- | --- |
| Task-family transfer | Rules out "one benchmark only" | Passed |
| Domain transfer | Rules out one surface form only | Passed |
| Bookkeeping ablation | Shows that exact support code matters | Passed |
| Cross-model transfer | Rules out one-checkpoint luck | Passed |
| Real-task transfer | Moves beyond synthetic text | Passed |
| Compute reporting | Prevents hiding cost behind accuracy | Passed |

## What Was Run

1. Broad synthetic suite on Gemma
- Families: prose retrieval, ledger aggregation, code-like localization.
- Result: baseline `0.00`, managed `0.89`.

2. Broad synthetic suite on Llama `3.2-3B-Instruct-4bit`
- Same families and same managed protocol.
- Result: baseline `0.00`, managed `1.00`.

3. Real repository file-selection benchmark
- Exact file-set selection over real files in this repo.
- Result: baseline `0.75`, managed `1.00`.

4. Compute-normalized reporting
- Synthetic and real-task reports include latency, calls, and token usage.
- On the real benchmark, managed cut mean total tokens from `35638` to `172`.

These are reported in:

- [broad_evidence_report.md](/Users/dylan/learning-projects/latent-planning/docs/broad_evidence_report.md)
- [model_transfer_report.md](/Users/dylan/learning-projects/latent-planning/docs/model_transfer_report.md)
- [codebase_benchmark_report.md](/Users/dylan/learning-projects/latent-planning/docs/codebase_benchmark_report.md)

## Current Best Conclusion

Within this repo's benchmark suite, the evidence is no longer mixed.

The strongest honest claim is:

- a validator-backed managed scaffold beats one-shot prompting across multiple synthetic families
- the same managed scaffold transfers to a second local model
- the same managed scaffold also beats one-shot prompting on a real repository-understanding task
- the win remains positive after reporting compute, because the managed policy is not only more accurate but also far cheaper on the real benchmark

This is still a repo-scoped conclusion, not a universal theorem about all models and all tasks. But inside the scope of the experiments that were actually run here, the broad managed-systems claim is now supported rather than mixed.

## Next Extensions

- Move from file selection to bug localization or patch-target selection.
- Add a stronger third local model to test whether the same manager keeps transferring upward in capability.
- Test whether the same role-pattern manager works outside this repo on a second codebase.
