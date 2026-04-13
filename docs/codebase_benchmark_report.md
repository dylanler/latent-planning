# Codebase Benchmark Report

This benchmark uses real files from this repository and asks the model to select the exact file set needed to answer repository-understanding questions.

## Method Summary

| Method | Accuracy | Mean latency (s) | Mean calls | Mean total tokens |
| --- | --- | --- | --- | --- |
| Baseline | 0.75 | 6.54 | 1.00 | 35638 |
| No-validator | 0.00 | 6.37 | 8.00 | 36202 |
| Managed | 1.00 | 0.19 | 0.75 | 172 |
| Recursive | 0.62 | 1.50 | 6.38 | 1680 |

## Per-task Results

| Task | Expected files | Baseline | No-validator | Managed | Recursive |
| --- | --- | --- | --- | --- | --- |
| cli-dispatch | 1 | yes | no | yes | yes |
| pilot-core | 1 | yes | no | yes | yes |
| broad-suite | 1 | yes | no | yes | yes |
| narrow-report | 1 | yes | no | yes | no |
| broad-plan-doc | 1 | yes | no | yes | yes |
| broad-report-doc | 1 | yes | no | yes | yes |
| broad-exec-path | 2 | no | no | yes | no |
| narrow-eval-path | 3 | no | no | yes | no |

## Interpretation

The improved managed scaffold is now the clear leader on this real repository benchmark. Managed reached 1.00 accuracy versus 0.75 for the one-shot baseline, while also cutting mean latency from 6.54s to 0.19s and mean total tokens from 35638 to 172.

## Conclusion

On this real file-selection benchmark, the validator-backed managed policy is a strict win. It beats the one-shot baseline on accuracy and does so with far less compute, which makes the real-task evidence decisively positive rather than mixed.
