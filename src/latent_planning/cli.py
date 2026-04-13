from __future__ import annotations

import argparse
import json
from pathlib import Path

from latent_planning.experiment import (
    DEFAULT_MODEL_REPO,
    build_results_path,
    discover_local_model_snapshot,
    run_pilot,
)
from latent_planning.breadth_suite import build_breadth_report, run_breadth_suite
from latent_planning.codebase_benchmark import build_codebase_report, run_codebase_benchmark
from latent_planning.reporting import build_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="latent-planning",
        description="Run local MLX pilots for the mismanaged geniuses hypothesis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_model = subparsers.add_parser(
        "check-model",
        help="Report whether the MLX Gemma pilot model already exists in the local Hugging Face cache.",
    )
    check_model.add_argument(
        "--model-repo",
        default=DEFAULT_MODEL_REPO,
        help="Model repo to inspect. Defaults to the MLX 4-bit Gemma pilot.",
    )

    run = subparsers.add_parser(
        "run-pilot",
        help="Run the baseline-vs-managed long-context pilot and write a JSON report.",
    )
    run.add_argument(
        "--model",
        default=None,
        help="Local model path or HF repo. Defaults to the discovered local snapshot when available.",
    )
    run.add_argument(
        "--sections",
        type=int,
        default=8,
        help="Number of report sections and target records per task.",
    )
    run.add_argument(
        "--distractors-per-section",
        type=int,
        nargs="+",
        default=[6, 10, 14],
        help="Distractor counts to test for each section.",
    )
    run.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0, 1, 2],
        help="Random seeds for task generation.",
    )
    run.add_argument(
        "--label",
        default=None,
        help="Optional label for grouping result files into an experiment family.",
    )
    run.add_argument(
        "--note-repeats",
        type=int,
        default=1,
        help="How many note sentences to concatenate per record to increase context length.",
    )
    run.add_argument(
        "--chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each managed chunk pass.",
    )
    run.add_argument(
        "--include-no-validator-manager",
        action="store_true",
        help="Also evaluate a section-by-section manager without deterministic validation.",
    )
    run.add_argument(
        "--no-validator-chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each no-validator manager call.",
    )
    run.add_argument(
        "--include-recursive-manager",
        action="store_true",
        help="Also evaluate a recursive within-section manager.",
    )
    run.add_argument(
        "--recursive-chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each recursive manager call.",
    )
    run.add_argument(
        "--recursive-leaf-records",
        type=int,
        default=4,
        help="Maximum records per recursive leaf chunk.",
    )
    run.add_argument(
        "--recursive-branching-factor",
        type=int,
        default=3,
        help="How many child groups to create at each recursive split.",
    )
    run.add_argument(
        "--baseline-max-tokens",
        type=int,
        default=160,
        help="Generation budget for the single-shot baseline.",
    )
    run.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON output path. Defaults to results/<timestamped-file>.json",
    )

    report = subparsers.add_parser(
        "build-report",
        help="Aggregate one or more JSON result files into a markdown report with tables and charts.",
    )
    report.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Result JSON files to aggregate.",
    )
    report.add_argument(
        "--output",
        type=Path,
        default=Path("docs/extended_evaluation.md"),
        help="Markdown output path.",
    )

    breadth = subparsers.add_parser(
        "run-breadth-suite",
        help="Run a broader cross-family suite to test whether management advantages transfer beyond one benchmark shape.",
    )
    breadth.add_argument(
        "--model",
        default=None,
        help="Local model path or HF repo. Defaults to the discovered local snapshot when available.",
    )
    breadth.add_argument(
        "--families",
        nargs="+",
        choices=["records", "ledger", "code"],
        default=["records", "ledger", "code"],
        help="Benchmark families to include.",
    )
    breadth.add_argument(
        "--sections",
        type=int,
        default=6,
        help="Number of sections or files per task.",
    )
    breadth.add_argument(
        "--distractors-per-section",
        type=int,
        default=8,
        help="Distractor items per section.",
    )
    breadth.add_argument(
        "--context-scale",
        type=int,
        default=3,
        help="How much filler text to add within each family.",
    )
    breadth.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0, 1, 2],
        help="Random seeds for task generation.",
    )
    breadth.add_argument(
        "--baseline-max-tokens",
        type=int,
        default=180,
        help="Generation budget for the single-shot baseline.",
    )
    breadth.add_argument(
        "--chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each managed chunk pass.",
    )
    breadth.add_argument(
        "--no-validator-chunk-max-tokens",
        type=int,
        default=96,
        help="Generation budget for each no-validator chunk pass.",
    )
    breadth.add_argument(
        "--recursive-chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each recursive chunk pass.",
    )
    breadth.add_argument(
        "--recursive-leaf-items",
        type=int,
        default=4,
        help="Maximum items per recursive leaf chunk.",
    )
    breadth.add_argument(
        "--recursive-branching-factor",
        type=int,
        default=3,
        help="How many child groups to create at each recursive split.",
    )
    breadth.add_argument(
        "--output",
        type=Path,
        default=Path("results/breadth-suite.json"),
        help="JSON output path.",
    )

    breadth_report = subparsers.add_parser(
        "build-breadth-report",
        help="Aggregate one or more breadth-suite JSON files into a markdown report.",
    )
    breadth_report.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Breadth-suite JSON files to aggregate.",
    )
    breadth_report.add_argument(
        "--output",
        type=Path,
        default=Path("docs/broad_evidence_report.md"),
        help="Markdown output path.",
    )

    codebase = subparsers.add_parser(
        "run-codebase-benchmark",
        help="Run a real repository file-selection benchmark over this codebase.",
    )
    codebase.add_argument(
        "--model",
        default=None,
        help="Local model path or HF repo. Defaults to the discovered local snapshot when available.",
    )
    codebase.add_argument(
        "--baseline-max-tokens",
        type=int,
        default=120,
        help="Generation budget for the single-shot baseline.",
    )
    codebase.add_argument(
        "--chunk-max-tokens",
        type=int,
        default=40,
        help="Generation budget for each managed file pass.",
    )
    codebase.add_argument(
        "--no-validator-chunk-max-tokens",
        type=int,
        default=48,
        help="Generation budget for each no-validator file pass.",
    )
    codebase.add_argument(
        "--recursive-chunk-max-tokens",
        type=int,
        default=40,
        help="Generation budget for each recursive group and file pass.",
    )
    codebase.add_argument(
        "--output",
        type=Path,
        default=Path("results/codebase-benchmark.json"),
        help="JSON output path.",
    )

    codebase_report = subparsers.add_parser(
        "build-codebase-report",
        help="Convert a codebase benchmark JSON file into a markdown report.",
    )
    codebase_report.add_argument(
        "input",
        type=Path,
        help="Codebase benchmark JSON file.",
    )
    codebase_report.add_argument(
        "--output",
        type=Path,
        default=Path("docs/codebase_benchmark_report.md"),
        help="Markdown output path.",
    )
    return parser


def handle_check_model(model_repo: str) -> int:
    snapshot = discover_local_model_snapshot(model_repo)
    payload = {
        "model_repo": model_repo,
        "local_snapshot": str(snapshot) if snapshot else None,
        "download_complete": bool(snapshot),
    }
    print(json.dumps(payload, indent=2))
    return 0


def handle_run_pilot(args: argparse.Namespace) -> int:
    model = args.model or discover_local_model_snapshot(DEFAULT_MODEL_REPO) or DEFAULT_MODEL_REPO
    output = args.output or build_results_path(model)
    summary = run_pilot(
        model_path_or_repo=str(model),
        label=args.label,
        sections=args.sections,
        distractors_per_section=args.distractors_per_section,
        seeds=args.seeds,
        note_repeats=args.note_repeats,
        output_path=output,
        baseline_max_tokens=args.baseline_max_tokens,
        chunk_max_tokens=args.chunk_max_tokens,
        no_validator_chunk_max_tokens=args.no_validator_chunk_max_tokens,
        include_no_validator_manager=args.include_no_validator_manager,
        recursive_chunk_max_tokens=args.recursive_chunk_max_tokens,
        include_recursive_manager=args.include_recursive_manager,
        recursive_leaf_records=args.recursive_leaf_records,
        recursive_branching_factor=args.recursive_branching_factor,
    )
    print(json.dumps(summary, indent=2))
    return 0


def handle_build_report(inputs: list[Path], output: Path) -> int:
    report = build_report(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(str(output))
    return 0


def handle_run_breadth_suite(args: argparse.Namespace) -> int:
    model = args.model or discover_local_model_snapshot(DEFAULT_MODEL_REPO) or DEFAULT_MODEL_REPO
    summary = run_breadth_suite(
        model_path_or_repo=str(model),
        families=args.families,
        sections=args.sections,
        distractors_per_section=args.distractors_per_section,
        context_scale=args.context_scale,
        seeds=args.seeds,
        output_path=args.output,
        baseline_max_tokens=args.baseline_max_tokens,
        chunk_max_tokens=args.chunk_max_tokens,
        no_validator_chunk_max_tokens=args.no_validator_chunk_max_tokens,
        recursive_chunk_max_tokens=args.recursive_chunk_max_tokens,
        recursive_leaf_items=args.recursive_leaf_items,
        recursive_branching_factor=args.recursive_branching_factor,
    )
    print(json.dumps(summary, indent=2))
    return 0


def handle_build_breadth_report(inputs: list[Path], output: Path) -> int:
    report = build_breadth_report(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(str(output))
    return 0


def handle_run_codebase_benchmark(args: argparse.Namespace) -> int:
    model = args.model or discover_local_model_snapshot(DEFAULT_MODEL_REPO) or DEFAULT_MODEL_REPO
    summary = run_codebase_benchmark(
        model_path_or_repo=str(model),
        output_path=args.output,
        baseline_max_tokens=args.baseline_max_tokens,
        chunk_max_tokens=args.chunk_max_tokens,
        no_validator_chunk_max_tokens=args.no_validator_chunk_max_tokens,
        recursive_chunk_max_tokens=args.recursive_chunk_max_tokens,
    )
    print(json.dumps(summary, indent=2))
    return 0


def handle_build_codebase_report(input_path: Path, output: Path) -> int:
    report = build_codebase_report(input_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(str(output))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "check-model":
        return handle_check_model(args.model_repo)
    if args.command == "run-pilot":
        return handle_run_pilot(args)
    if args.command == "build-report":
        return handle_build_report(args.inputs, args.output)
    if args.command == "run-breadth-suite":
        return handle_run_breadth_suite(args)
    if args.command == "build-breadth-report":
        return handle_build_breadth_report(args.inputs, args.output)
    if args.command == "run-codebase-benchmark":
        return handle_run_codebase_benchmark(args)
    if args.command == "build-codebase-report":
        return handle_build_codebase_report(args.input, args.output)
    parser.error(f"Unknown command: {args.command}")
    return 2
