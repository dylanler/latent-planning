# Mismanaged Geniuses Pilot Plan

## Objective

Test a narrow version of the "mismanaged geniuses" hypothesis on a local Apple Silicon setup:

- Hold model weights fixed.
- Compare a single direct LM call against a decomposition scaffold that uses the same LM multiple times.
- Use exact grading so the result is not subjective.

## Working Hypothesis

`google/gemma-4-E2B-it` in MLX form is already capable enough to solve the local subproblems in-distribution, but underperforms when forced to solve the full long-context task in one shot.

## Null Hypothesis

Decomposition does not materially improve exact-match accuracy relative to a single direct prompt once the same model and same underlying task are held fixed.

## Pilot Benchmark

The pilot task is a synthetic long report with these properties:

- The report is split into sections.
- Each section contains exactly one true target record.
- Each section also contains many structured distractors that differ from the target criteria by at least one field.
- The final answer is an ordered seal sequence derived from every target record across the full report.

Why this benchmark:

- It is hard for a small model to do reliably in one pass once context grows.
- It naturally decomposes into section-level retrieval.
- It is exactly gradeable.
- It isolates management of context and call allocation from world knowledge.

## Conditions

### Baseline

- One model call sees the entire report.
- It must return the final ordered seal sequence directly.

### Managed

- The same model is called once per section.
- Each call returns a permissive list of candidate record IDs that might match the target criteria.
- Python validates those candidate IDs exactly against the structured records.
- The validated targets are then sorted deterministically into the final answer.

## Metrics

- Exact-match accuracy
- Mean latency per task
- Mean number of model calls per task

## Success Criterion

The managed condition should beat the baseline on exact-match accuracy across multiple seeds and distractor counts. A clear win would look like:

- baseline accuracy near zero or low
- managed accuracy materially higher, ideally close to perfect on the pilot

## Threats To Validity

- The benchmark is synthetic and retrieval-heavy.
- The managed condition includes deterministic validation, which removes bookkeeping errors.
- A positive result supports only a narrow operational claim, not the full paper.

## Extensions

After this pilot, the next experiments should become progressively less scaffold-friendly:

1. Multi-hop report QA where each section contributes a different constraint.
2. Code-edit tasks where subagents inspect different files before proposing a patch.
3. Recursive plan execution with variable-depth decomposition rather than fixed section chunking.
4. Training or fine-tuning the decomposition policy instead of hand-writing it.
