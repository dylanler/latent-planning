# Pilot Report

## Setup

- Machine: Apple Silicon Mac with local MLX support
- Model: `mlx-community/gemma-4-e2b-it-4bit`
- Benchmark: 8 report sections, one true target record per section, distractor counts of 6, 10, and 14, across seeds 0, 1, and 2

## Result

- Baseline exact-match accuracy: `0 / 9`
- Managed exact-match accuracy: `8 / 9`
- Baseline mean latency: `1.74s`
- Managed mean latency: `3.02s`

The managed scaffold was roughly `1.7x` slower in wall-clock latency and used `8x` as many model calls, but it dramatically outperformed the single-shot baseline on exact-match accuracy.

## Interpretation

This supports a narrow operational version of the hypothesis:

- the same small model was usually capable of solving the local retrieval subproblem inside a section
- the failure mode was mostly at the full-report level, where one direct call underused the model's local competence

The one managed failure happened at `distractors_per_section=10`, `seed=2`, where the chunk-level pass missed `T3` and returned a distractor candidate instead. That is useful because it shows the scaffold is not magically perfect; its accuracy still depends on chunk-level recall.

## Limits

- The task is synthetic and structured.
- The managed condition uses deterministic validation after the model proposes candidate IDs.
- The result should be treated as a pilot, not as proof of the general paper.

## Next Experiments

1. Replace fixed section chunking with recursive chunk refinement.
2. Add multi-hop constraints so the final answer depends on combining different fields across sections, not only retrieval.
3. Port the same evaluation pattern to real code tasks where subagents inspect different files before a final synthesis step.
