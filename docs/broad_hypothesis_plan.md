# Plan For A Broader Version Of The Hypothesis

The narrow version of the hypothesis is:

- a small local model can look much more capable when the task is decomposed well

The broad version would be stronger:

- this effect should transfer across task families, domains, and models
- it should survive matched-compute comparisons
- it should continue to hold on real tasks, not only synthetic ones

## What Would Count As Stronger Evidence

1. Task-family transfer
- A managed scaffold should beat one-shot prompting on more than one benchmark shape.
- It should help on retrieval, aggregation, and code-like tasks, not just one of them.

2. Domain transfer
- The advantage should appear in prose-like text, ledger-like text, and code-like text.

3. Bookkeeping ablation
- A no-validator version should underperform a validator-backed version on at least some tasks.
- That would show the gain is not only “more calls,” but also “better allocation of fuzzy work versus exact work.”

4. Hierarchical robustness
- Recursive routing should become helpful when flat section-by-section management starts to break under context growth.

5. Model transfer
- The same suite should be rerun on at least one stronger local model.
- If the effect survives, it is less likely to be a quirk of one checkpoint.

6. Real-task transfer
- The scaffold should help on at least one real codebase task such as file selection, bug localization, or patch target selection.

7. Matched-compute fairness
- Comparisons should report wall-clock latency, model calls, and ideally token cost.
- A stronger claim requires showing that the managed gain is not only purchased by an unreasonable compute multiplier.

## What Was Run In This Repo Now

This repo now includes all four of the originally listed extensions:

- a cross-family local suite over prose retrieval, ledger aggregation, and code-like localization
- compute-normalized reporting with prompt, completion, and total-token accounting
- a Gemma context ladder at context scales `1`, `3`, and `5`
- a real codebase file-selection benchmark over this repository
- a second-model replication on `mlx-community/Llama-3.2-3B-Instruct-4bit`

These are reported in:

- [broad_evidence_report.md](/Users/dylan/learning-projects/latent-planning/docs/broad_evidence_report.md)
- [context_ladder_report.md](/Users/dylan/learning-projects/latent-planning/docs/context_ladder_report.md)
- [codebase_benchmark_report.md](/Users/dylan/learning-projects/latent-planning/docs/codebase_benchmark_report.md)
- [model_transfer_report.md](/Users/dylan/learning-projects/latent-planning/docs/model_transfer_report.md)

## Completed Extensions

1. Real codebase benchmark
- Implemented as a graded file-selection benchmark over real repo files.
- Result: negative transfer for the current scaffold. One-shot baseline was best on this task.

2. Cross-model replication
- Reran the broad suite on `mlx-community/Llama-3.2-3B-Instruct-4bit`.
- Result: the Gemma scaffold pattern did not transfer cleanly to the second model.

3. Harder context ladder
- Reran the broad suite on Gemma at context scales `1`, `3`, and `5`.
- Result: flat managed stayed strong overall, but recursive routing was not consistently better across families.

4. Compute-normalized comparison
- Added token accounting to the synthetic breadth suite and the codebase benchmark.
- Result: managed methods usually buy their gains with extra tokens, not free capability.

## Remaining Gaps

1. Better real-task managers
- The current codebase manager loses too much global context and over-selects files.
- The next real-task scaffold should compare or rank candidate files instead of asking independent yes/no questions.

2. Stronger model transfer
- One weaker second model is not enough to characterize transfer.
- The next informative replication is a stronger local model with enough capacity to follow the decomposition language reliably.

3. Real bug-localization or patch-target tasks
- File selection is a real task, but still a shallow one.
- The next proof point should require choosing patch targets or isolating a failing subsystem.

## Current Best Conclusion

The repo is now well past “one synthetic benchmark only,” but it is still not at “broad proof.”

The strongest honest claim at this point is:

- management advantages transfer across multiple synthetic task families
- deterministic support code matters on some tasks
- the effect is not universal across scaffolds, tasks, or models
- broader proof still requires a stronger real-task manager and stronger model-transfer evidence
