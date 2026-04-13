# Codebase Benchmark Report

This benchmark uses real files from this repository and asks the model to select the exact file set needed to answer repository-understanding questions.

## Method Summary

| Method | Accuracy | Mean latency (s) | Mean calls | Mean total tokens |
| --- | --- | --- | --- | --- |
| Baseline | 0.75 | 7.86 | 1.00 | 34497 |
| No-validator | 0.00 | 7.04 | 8.00 | 35056 |
| Managed | 0.00 | 6.76 | 8.00 | 34904 |
| Recursive | 0.00 | 6.19 | 9.50 | 30156 |

## Per-task Results

| Task | Expected files | Baseline | No-validator | Managed | Recursive |
| --- | --- | --- | --- | --- | --- |
| cli-dispatch | 1 | yes | no | no | no |
| pilot-core | 1 | yes | no | no | no |
| broad-suite | 1 | yes | no | no | no |
| narrow-report | 1 | yes | no | no | no |
| broad-plan-doc | 1 | yes | no | no | no |
| broad-report-doc | 1 | yes | no | no | no |
| broad-exec-path | 2 | no | no | no | no |
| narrow-eval-path | 3 | no | no | no | no |

## Interpretation

This is the strongest negative result in the repo so far. On this real file-selection task, the one-shot baseline was the best method at 0.75 accuracy and won outright on 6 tasks. The current managed scaffolds over-selected files because they broke the repository into narrow local decisions and lost the global sense of which files were necessary versus merely related.

## Conclusion

The broad hypothesis is not yet proven on real repository understanding. Better management helps on the synthetic suites, but this particular decomposition policy does not transfer to small real file-selection tasks. The next improvement should be a different manager for codebases, not just more of the current one.
