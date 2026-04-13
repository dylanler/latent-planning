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
        "--chunk-max-tokens",
        type=int,
        default=80,
        help="Generation budget for each managed chunk pass.",
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
        sections=args.sections,
        distractors_per_section=args.distractors_per_section,
        seeds=args.seeds,
        output_path=output,
        baseline_max_tokens=args.baseline_max_tokens,
        chunk_max_tokens=args.chunk_max_tokens,
    )
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "check-model":
        return handle_check_model(args.model_repo)
    if args.command == "run-pilot":
        return handle_run_pilot(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
