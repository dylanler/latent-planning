# latent-planning

This repo is a local pilot for the "mismanaged geniuses" hypothesis: can the same small frontier-ish model do meaningfully better on a long-context task when we replace a single prompt with a simple decomposition scaffold?

The current pilot uses `mlx-community/gemma-4-e2b-it-4bit` on Apple Silicon. The benchmark is synthetic on purpose so we can grade it exactly:

- The model sees a long report split into sections.
- Each section contains one true target record and many near-miss distractors.
- The baseline gets the whole report in one shot and must return the ordered seal sequence directly.
- The managed condition queries the same model section-by-section for high-recall candidate IDs, then validates those IDs deterministically before assembling the final answer.

That is not a complete test of the paper's hypothesis. It is a narrow pilot that asks a precise question: does a decomposition scaffold help the same local model recover structured evidence across a longer context than a single direct call?

## Why MLX

MLX is the right backend on this machine:

- the MLX 4-bit Gemma snapshot is already present in the local Hugging Face cache
- `mlx_lm` loads and runs the model successfully
- `llama-cli` and `ollama` are not installed locally, so GGUF would require extra setup with no obvious upside for this pilot

## Commands

Check whether the local MLX snapshot exists:

```bash
uv run latent-planning check-model
```

Run the pilot and write a JSON report:

```bash
uv run latent-planning run-pilot
```

The default run uses:

- `sections=8`
- `distractors_per_section=6 10 14`
- `seeds=0 1 2`

Results are written to `results/`.

## Current Pilot Result

On the first local run with the cached MLX 4-bit Gemma snapshot:

- baseline exact-match accuracy: `0.0` across `9` tasks
- managed exact-match accuracy: `0.8889` across `9` tasks
- baseline mean latency: `1.74s`
- managed mean latency: `3.02s`

That is the expected shape for this hypothesis: the scaffold buys a large accuracy jump at the cost of more calls and higher latency.

## Experiment Plan

The written plan lives in [docs/mgh_experiment_plan.md](/Users/dylan/learning-projects/latent-planning/docs/mgh_experiment_plan.md).

## Interpretation

If the managed condition materially outperforms the single-shot baseline, that supports a narrow version of the hypothesis:

- the model already contains enough local competence to solve the subproblems
- the failure mode is at least partly in how we allocate attention and calls, not only in model weights

If both conditions fail, the likely interpretations are:

- the task is still too hard for the model even after decomposition
- the scaffold is poorly chosen
- the hypothesis does not hold on this task family

The next step after this pilot is to move from structured retrieval into more open-ended tasks such as multi-file code repair, recursive planning, or tool-mediated long-horizon workflows.
