# latent-planning

This repo is a local pilot for the "mismanaged geniuses" hypothesis: can the same local model do materially better when we change how it is managed, rather than changing the model weights?

The current pilot uses `mlx-community/gemma-4-e2b-it-4bit` on Apple Silicon and tests one narrow question:

- The model sees a long synthetic report split into sections.
- Each section contains one true target record and many near-miss distractors.
- The task is to recover the exact ordered seal sequence for the target records.
- We compare one-shot prompting against several decomposition strategies on the same tasks.

This is not a full proof of the hypothesis. It is a controlled local benchmark for one claim: better decomposition can unlock capability that is mostly absent in a single direct prompt.

## What Is Being Compared

| Strategy | What the model has to do | Intuition |
| --- | --- | --- |
| Baseline | Read the whole report and answer in one call | One large exam question |
| No-validator manager | Search one section at a time, but still copy out exact `phase` and `seal` fields itself | Smaller exams, but still does all bookkeeping alone |
| Validator-backed manager | Search one section at a time, return candidate IDs, then let Python verify exact matches and assemble the answer | Smaller exams plus a calculator for exact bookkeeping |
| Recursive manager | Route over compact summaries first, then zoom into likely leaf chunks | First decide where to look, then inspect details |

## Architecture

What is implemented today:

```mermaid
flowchart TD
    A[MLX Gemma 4 E2B 4-bit<br/>local Apple Silicon model] --> B[Task generator<br/>synthetic long report with sections]
    B --> C[Baseline path<br/>single full-report prompt]
    B --> D[No-validator path<br/>one prompt per section]
    B --> E[Validator-backed path<br/>one prompt per section]
    B --> R[Recursive path<br/>route then zoom]
    C --> CP[Direct answer parser<br/>ANSWER=...]
    D --> DP[Model returns<br/>phase plus seal per section]
    E --> EP[Candidate record IDs<br/>high-recall retrieval]
    R --> RS[Compact group summaries<br/>recursive routing]
    RS --> RL[Leaf chunk search<br/>full records]
    EP --> V[Deterministic validator<br/>exact field match in Python]
    RL --> V
    DP --> O[Ordered seal sequence]
    V --> O
    CP --> S[Exact-match scorer]
    O --> S
    S --> J[JSON result artifact<br/>results/*.json]
    J --> K[README + docs report]
```

Runtime shape:

- `latent-planning check-model` verifies that the local MLX snapshot exists.
- `latent-planning run-pilot` loads one model instance and evaluates the selected conditions over the same generated tasks.
- `latent-planning build-report` aggregates JSON result files into tables and charts.

## Why MLX

MLX is the right backend on this machine:

- the MLX 4-bit Gemma snapshot is already present in the local Hugging Face cache
- `mlx_lm` loads and runs the model successfully
- `llama-cli` and `ollama` are not installed locally, so GGUF would require extra setup with no clear upside for this pilot

## Commands

Check whether the local MLX snapshot exists:

```bash
uv run latent-planning check-model
```

Run the default baseline-vs-managed pilot:

```bash
uv run latent-planning run-pilot
```

Run the full ablation on one context setting:

```bash
uv run latent-planning run-pilot \
  --label ablation-context-sweep \
  --sections 8 \
  --distractors-per-section 10 \
  --note-repeats 3 \
  --seeds 0 1 2 3 4 \
  --include-no-validator-manager \
  --include-recursive-manager
```

Rebuild the markdown report from saved JSON files:

```bash
uv run latent-planning build-report \
  results/distractor-sweep.json \
  results/section-sweep-s4.json \
  results/section-sweep-s8.json \
  results/section-sweep-s12.json \
  results/ablation-context-sweep-r1.json \
  results/ablation-context-sweep-r3.json \
  results/ablation-context-sweep-r5.json \
  --output docs/extended_evaluation.md
```

The full report lives in [docs/extended_evaluation.md](docs/extended_evaluation.md). The experiment plan lives in [docs/mgh_experiment_plan.md](docs/mgh_experiment_plan.md).

## Evaluation Snapshot

The current report set aggregates `50` runs across distractor growth, section growth, and the new context ablation.

### Experiment Summary

| Experiment | Runs | Avg report chars | Baseline acc | Managed acc | No-validator acc | Recursive acc | Baseline latency (s) | Managed latency (s) | No-validator latency (s) | Recursive latency (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ablation-context-sweep` | 15 | 28013 | 0.00 | 0.47 | 0.07 | 0.80 | 2.98 | 4.23 | 5.21 | 10.59 |
| `distractor-sweep` | 20 | 14497 | 0.00 | 0.75 | - | - | 2.07 | 3.73 | - | - |
| `section-sweep` | 15 | 14488 | 0.00 | 0.93 | - | - | 2.01 | 3.44 | - | - |

### How To Read The Main Ablation

Moving right means more repeated note text, so the report gets longer without changing the underlying task. Higher is better on the accuracy chart. Lower is better on the latency chart.

| Context size | Baseline acc | No-validator acc | Flat managed acc | Recursive acc |
| --- | --- | --- | --- | --- |
| `1x` notes | 0.00 | 0.20 | 0.80 | 0.80 |
| `3x` notes | 0.00 | 0.00 | 0.60 | 0.80 |
| `5x` notes | 0.00 | 0.00 | 0.00 | 0.80 |

```mermaid
xychart-beta
    title "Context Growth vs Accuracy"
    x-axis "Note repeats" [1, 3, 5]
    y-axis "Exact-match accuracy" 0 --> 1.0
    line "Baseline" [0.00, 0.00, 0.00]
    line "No-validator" [0.20, 0.00, 0.00]
    line "Flat managed" [0.80, 0.60, 0.00]
    line "Recursive" [0.80, 0.80, 0.80]
```

```mermaid
xychart-beta
    title "Context Growth vs Latency"
    x-axis "Note repeats" [1, 3, 5]
    y-axis "Latency seconds" 0 --> 12.81
    line "Baseline" [1.73, 2.66, 4.55]
    line "No-validator" [3.75, 5.18, 6.70]
    line "Flat managed" [2.98, 4.09, 5.62]
    line "Recursive" [8.07, 11.00, 12.71]
```

### What The Other Sweeps Say

The context ablation is the most important visual, but the simpler sweeps matter because they show the model is not failing everywhere.

| Sweep | What changes | Result |
| --- | --- | --- |
| Distractor sweep | More near-miss records per section | Flat managed stays above zero even at the hardest setting, baseline stays at zero |
| Section sweep | More sections to search | Flat managed remains very strong overall, baseline stays at zero |
| Context ablation | Same task, much longer repeated notes | Flat managed eventually breaks, recursive does not |

```mermaid
xychart-beta
    title "Distractor Sweep Accuracy"
    x-axis "Distractors per section" [4, 8, 12, 16]
    y-axis "Exact-match accuracy" 0 --> 1.1
    line "Baseline" [0.00, 0.00, 0.00, 0.00]
    line "Flat managed" [1.00, 1.00, 0.60, 0.40]
```

```mermaid
xychart-beta
    title "Section Sweep Accuracy"
    x-axis "Sections" [4, 8, 12]
    y-axis "Exact-match accuracy" 0 --> 1.1
    line "Baseline" [0.00, 0.00, 0.00]
    line "Flat managed" [1.00, 0.80, 1.00]
```

### Outcome Breakdown

| Outcome | Count |
| --- | --- |
| Flat managed beats baseline | 36 |
| No-validator beats baseline | 1 |
| Recursive rescues flat-managed failures | 5 |
| Baseline only | 0 |
| Any non-baseline method succeeds | 41 |
| All methods fail | 9 |

## Intuitive Read

The cleanest way to read these results is:

- Giving the model smaller subproblems helps a lot.
- Giving the model smaller subproblems is not enough by itself.
- The strongest gains come from combining decomposition with either exact external bookkeeping or better routing.

The no-validator line is the key ablation. It asks: what if we still decompose, but the model has to do the exact copying and ordering itself? The answer is that performance mostly disappears. That means the gain is not just "more calls"; it comes from structuring the task so the model only does the fuzzy part and deterministic code does the exact part.

The recursive line is the second key result. Flat section-by-section management works when the report is moderately sized, but it breaks when the context gets very long. Recursive routing fixes that by first asking where to look, then only reading those leaf chunks in detail.

## Conclusion

This repo started as a narrow pilot, but it no longer ends there.

The original lesson still holds: the same local model can fail badly in one-shot prompting and then recover once the job is decomposed into smaller, machine-checkable steps. What changed is that the repo now tests that claim across multiple task families, across two models, and on a real repository-understanding benchmark.

## Broader Suite

The repo now also includes a broader transfer test across three task families:

- prose retrieval
- ledger aggregation
- code-like localization

That broader run lives in [broad_evidence_report.md](/Users/dylan/learning-projects/latent-planning/docs/broad_evidence_report.md), and the explicit roadmap for what would count as a genuinely broader proof lives in [broad_hypothesis_plan.md](/Users/dylan/learning-projects/latent-planning/docs/broad_hypothesis_plan.md).

## Definitive Verdict

The repo now has a decisive managed-versus-baseline scorecard:

| Evidence slice | What was tested | Baseline | Managed | Result |
| --- | --- | --- | --- | --- |
| Gemma broad synthetic suite | Prose, ledger, and code-like transfer on `gemma-4-e2b-it-4bit` | `0.00` | `0.89` | Managed win |
| Llama broad synthetic suite | Same suite on `Llama-3.2-3B-Instruct-4bit` | `0.00` | `1.00` | Managed win |
| Real codebase benchmark | Exact repo file-set selection over real files in this repo | `0.75` | `1.00` | Managed win |

```mermaid
xychart-beta
    title "Managed vs Baseline Across The Final Evidence Slices"
    x-axis "Evidence slice" [GemmaSynthetic, LlamaSynthetic, RealCodebase]
    y-axis "Accuracy" 0 --> 1.0
    line "Baseline" [0.00, 0.00, 0.75]
    line "Managed" [0.89, 1.00, 1.00]
```

## Intuitive Explanation

Why the result is no longer mixed:

- The one-shot baseline asks the model to read everything, keep every exact detail straight, and produce the final answer in one pass.
- The managed policy does not ask the model to be perfect at everything. It asks the model to solve the fuzzy part, then keeps the exact parts structured enough to verify or combine cleanly.
- Once that management layer is added, the same underlying models look much more capable on the tasks that matter in this repo.

On the real codebase benchmark, the managed win is not only more accurate. It is also much cheaper:

- baseline mean total tokens: `35638`
- managed mean total tokens: `172`
- baseline mean latency: `6.54s`
- managed mean latency: `0.19s`

The most defensible statement now is:

- within this repo's benchmark suite, the evidence is decisively positive for the managed-systems version of the hypothesis
- the managed policy beats one-shot prompting across synthetic transfer, model transfer, and a real repository task
- the key win is not that every manager works, but that a well-specified manager can unlock capability that the same model leaves hidden in one-shot prompting

## Additional Reports

- [Broad synthetic transfer report](docs/broad_evidence_report.md)
- [Gemma context ladder report](docs/context_ladder_report.md)
- [Real codebase benchmark report](docs/codebase_benchmark_report.md)
- [Cross-model transfer report](docs/model_transfer_report.md)
- [Broader proof scorecard](docs/broad_hypothesis_plan.md)
- [Single-page definitive verdict](docs/definitive_verdict.md)

## Future Extensions

- Move from file selection to bug localization or patch-target selection.
- Test the same role-pattern manager on a second codebase rather than only this repo.
- Add a stronger third local model.
- Try richer decomposition languages than fixed summaries and IDs.
