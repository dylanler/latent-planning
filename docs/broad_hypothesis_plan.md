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

This repo now includes the first step toward the broader version:

- a cross-family local suite over prose retrieval, ledger aggregation, and code-like localization
- the same local model
- the same shared configuration
- the same four methods: baseline, no-validator, validator-backed managed, recursive

That is reported in [broad_evidence_report.md](/Users/dylan/learning-projects/latent-planning/docs/broad_evidence_report.md).

## Next Experiments In Order

1. Real codebase benchmark
- Convert a small set of real repository tasks into graded file-selection or symbol-selection problems.
- Compare one-shot prompting against flat managed and recursive managed.

2. Cross-model replication
- Rerun the broad suite on a stronger local MLX model.
- Check whether management still adds value or whether better weights erase most of the gain.

3. Harder context ladder
- Take each family and raise context systematically until flat management breaks.
- Measure whether recursive routing consistently extends that boundary.

4. Compute-normalized comparison
- Add token-count accounting and report accuracy versus compute, not just accuracy versus method.

## Current Best Conclusion

The repo is now past “one synthetic benchmark only,” but it is not at “broad proof.”

The strongest honest claim at this point is:

- management advantages transfer across multiple synthetic task families
- deterministic support code matters on some tasks
- recursion matters when the flat policy starts to miss evidence
- broader proof still requires model transfer and at least one real code task
