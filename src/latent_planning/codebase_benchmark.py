from __future__ import annotations

import json
import re
import statistics
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from latent_planning.experiment import MLXPromptModel

FILE_PATHS = [
    "README.md",
    "src/latent_planning/cli.py",
    "src/latent_planning/experiment.py",
    "src/latent_planning/reporting.py",
    "src/latent_planning/breadth_suite.py",
    "docs/extended_evaluation.md",
    "docs/broad_evidence_report.md",
    "docs/broad_hypothesis_plan.md",
]


@dataclass(frozen=True)
class CodeFile:
    path: str
    content: str
    summary: str
    group: str


@dataclass(frozen=True)
class RepoTask:
    task_id: str
    question: str
    expected_paths: list[str]


@dataclass(frozen=True)
class RepoConditionResult:
    answer_paths: list[str]
    exact_match: bool
    latency_seconds: float
    model_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    raw_output: str


def load_files() -> list[CodeFile]:
    files: list[CodeFile] = []
    for file_path in FILE_PATHS:
        content = Path(file_path).read_text()
        summary = summarize_file(file_path, content)
        group = top_level_group(file_path)
        files.append(CodeFile(path=file_path, content=content, summary=summary, group=group))
    return files


def top_level_group(file_path: str) -> str:
    path = Path(file_path)
    if len(path.parts) == 1:
        return "root"
    return path.parts[0]


def summarize_file(file_path: str, content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    preview = " | ".join(lines[:3])
    preview = preview[:220]
    return f"{file_path}: {preview}"


def build_tasks() -> list[RepoTask]:
    return [
        RepoTask(
            task_id="cli-dispatch",
            question="Which file defines the command-line interface, subcommand parsing, and command dispatch for the latent-planning tool?",
            expected_paths=["src/latent_planning/cli.py"],
        ),
        RepoTask(
            task_id="pilot-core",
            question="Which file implements the original local pilot task generator and the baseline versus managed experiment logic?",
            expected_paths=["src/latent_planning/experiment.py"],
        ),
        RepoTask(
            task_id="broad-suite",
            question="Which file implements the broader cross-family synthetic transfer suite and its reporting helpers?",
            expected_paths=["src/latent_planning/breadth_suite.py"],
        ),
        RepoTask(
            task_id="narrow-report",
            question="Which file aggregates narrow-pilot JSON results into markdown tables and charts?",
            expected_paths=["src/latent_planning/reporting.py"],
        ),
        RepoTask(
            task_id="broad-plan-doc",
            question="Which document explains what would count as stronger evidence for the broad hypothesis and lists the remaining proof plan?",
            expected_paths=["docs/broad_hypothesis_plan.md"],
        ),
        RepoTask(
            task_id="broad-report-doc",
            question="Which document summarizes the broader transfer-suite results and conclusions?",
            expected_paths=["docs/broad_evidence_report.md"],
        ),
        RepoTask(
            task_id="broad-exec-path",
            question="Which files together define and wire the broader suite execution path end-to-end?",
            expected_paths=["src/latent_planning/breadth_suite.py", "src/latent_planning/cli.py"],
        ),
        RepoTask(
            task_id="narrow-eval-path",
            question="Which files together define and present the original narrow-pilot evaluation path?",
            expected_paths=["src/latent_planning/experiment.py", "src/latent_planning/reporting.py", "README.md"],
        ),
    ]


def extract_paths(raw_output: str) -> list[str]:
    pattern = r"(?:README\.md|src/latent_planning/[a-z_]+\.py|docs/[a-z_]+\.md)"
    return list(dict.fromkeys(re.findall(pattern, raw_output)))


def build_baseline_prompt(task: RepoTask, files: list[CodeFile]) -> str:
    repo_text = "\n\n".join(f"=== FILE {file.path} ===\n{file.content}" for file in files)
    expected = "ANSWER=<comma-separated-paths>"
    return textwrap.dedent(
        f"""\
        You are inspecting a small repository snapshot.

        Question:
        {task.question}

        Return exactly one line in the format {expected}.
        Use repository-relative paths.
        If more than one file is needed, list the paths comma-separated in the best answer order.
        Return only the answer line.

        Repository:
        {repo_text}
        """
    )


def build_file_path_prompt(task: RepoTask, file: CodeFile) -> str:
    return textwrap.dedent(
        f"""\
        Inspect this repository file.

        Question:
        {task.question}

        Return exactly one line in one of these formats:
        - MATCH path=<repository-relative-path>
        - NONE

        Copy the full repository-relative path exactly if it is relevant.

        File:
        Path: {file.path}
        {file.content}
        """
    )


def build_file_yes_prompt(task: RepoTask, file: CodeFile) -> str:
    return textwrap.dedent(
        f"""\
        Inspect this repository file.

        Question:
        {task.question}

        Return exactly one line:
        - YES if this file is relevant to answering the question
        - NO if it is not

        File:
        Path: {file.path}
        {file.content}
        """
    )


def build_group_prompt(task: RepoTask, group_name: str, summaries: list[CodeFile]) -> str:
    summaries_text = "\n".join(f"- {file.summary}" for file in summaries)
    return textwrap.dedent(
        f"""\
        Inspect this group of repository file summaries.

        Question:
        {task.question}

        Return exactly one line:
        - YES if this group might contain at least one relevant file
        - NO if it does not

        Group: {group_name}
        Summaries:
        {summaries_text}
        """
    )


def normalize_answer_paths(raw_output: str) -> list[str]:
    return extract_paths(raw_output)


def exact_match(answer_paths: list[str], expected_paths: list[str]) -> bool:
    return answer_paths == expected_paths


def classify_yes_no(raw_output: str) -> bool | None:
    yes_match = re.search(r"\bYES\b", raw_output, re.IGNORECASE)
    no_match = re.search(r"\bNO\b", raw_output, re.IGNORECASE)
    if yes_match and no_match:
        return yes_match.start() < no_match.start()
    if yes_match:
        return True
    if no_match:
        return False
    return None


def run_baseline(task: RepoTask, files: list[CodeFile], model: MLXPromptModel, *, max_tokens: int) -> RepoConditionResult:
    prompt = build_baseline_prompt(task, files)
    raw_output, latency_seconds = model.generate(prompt, max_tokens=max_tokens)
    answer_paths = normalize_answer_paths(raw_output)
    prompt_tokens = model.count_tokens(prompt)
    completion_tokens = model.count_tokens(raw_output)
    return RepoConditionResult(
        answer_paths=answer_paths,
        exact_match=exact_match(answer_paths, task.expected_paths),
        latency_seconds=latency_seconds,
        model_calls=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        raw_output=raw_output,
    )


def run_no_validator(task: RepoTask, files: list[CodeFile], model: MLXPromptModel, *, max_tokens: int) -> RepoConditionResult:
    matched_paths: list[str] = []
    raw_outputs: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    total_latency = 0.0
    for file in files:
        prompt = build_file_path_prompt(task, file)
        raw_output, latency_seconds = model.generate(prompt, max_tokens=max_tokens)
        raw_outputs.append(raw_output)
        total_latency += latency_seconds
        prompt_tokens += model.count_tokens(prompt)
        completion_tokens += model.count_tokens(raw_output)
        extracted = extract_paths(raw_output)
        if extracted:
            matched_paths.extend(extracted[:1])
    answer_paths = list(dict.fromkeys(matched_paths))
    return RepoConditionResult(
        answer_paths=answer_paths,
        exact_match=exact_match(answer_paths, task.expected_paths),
        latency_seconds=total_latency,
        model_calls=len(files),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        raw_output="\n---\n".join(raw_outputs),
    )


def run_managed(task: RepoTask, files: list[CodeFile], model: MLXPromptModel, *, max_tokens: int) -> RepoConditionResult:
    matched_paths: list[str] = []
    raw_outputs: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    total_latency = 0.0
    for file in files:
        prompt = build_file_yes_prompt(task, file)
        raw_output, latency_seconds = model.generate(prompt, max_tokens=max_tokens)
        raw_outputs.append(f"{file.path}\n{raw_output}")
        total_latency += latency_seconds
        prompt_tokens += model.count_tokens(prompt)
        completion_tokens += model.count_tokens(raw_output)
        if classify_yes_no(raw_output) is True:
            matched_paths.append(file.path)
    answer_paths = [path for path in FILE_PATHS if path in matched_paths]
    return RepoConditionResult(
        answer_paths=answer_paths,
        exact_match=exact_match(answer_paths, task.expected_paths),
        latency_seconds=total_latency,
        model_calls=len(files),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        raw_output="\n---\n".join(raw_outputs),
    )


def run_recursive(task: RepoTask, files: list[CodeFile], model: MLXPromptModel, *, max_tokens: int) -> RepoConditionResult:
    grouped: dict[str, list[CodeFile]] = {}
    for file in files:
        grouped.setdefault(file.group, []).append(file)

    selected_groups: list[str] = []
    raw_outputs: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    total_latency = 0.0
    total_calls = 0

    for group_name, group_files in grouped.items():
        prompt = build_group_prompt(task, group_name, group_files)
        raw_output, latency_seconds = model.generate(prompt, max_tokens=max_tokens)
        raw_outputs.append(f"[Group {group_name}]\n{raw_output}")
        total_latency += latency_seconds
        total_calls += 1
        prompt_tokens += model.count_tokens(prompt)
        completion_tokens += model.count_tokens(raw_output)
        if classify_yes_no(raw_output) is True:
            selected_groups.append(group_name)

    if not selected_groups:
        selected_groups = list(grouped)

    matched_paths: list[str] = []
    for group_name in selected_groups:
        for file in grouped[group_name]:
            prompt = build_file_yes_prompt(task, file)
            raw_output, latency_seconds = model.generate(prompt, max_tokens=max_tokens)
            raw_outputs.append(f"{file.path}\n{raw_output}")
            total_latency += latency_seconds
            total_calls += 1
            prompt_tokens += model.count_tokens(prompt)
            completion_tokens += model.count_tokens(raw_output)
            if classify_yes_no(raw_output) is True:
                matched_paths.append(file.path)

    answer_paths = [path for path in FILE_PATHS if path in matched_paths]
    return RepoConditionResult(
        answer_paths=answer_paths,
        exact_match=exact_match(answer_paths, task.expected_paths),
        latency_seconds=total_latency,
        model_calls=total_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        raw_output="\n---\n".join(raw_outputs),
    )


def summarize_condition(results: list[RepoConditionResult]) -> dict[str, float]:
    return {
        "accuracy": statistics.mean(result.exact_match for result in results),
        "mean_latency_seconds": statistics.mean(result.latency_seconds for result in results),
        "mean_model_calls": statistics.mean(result.model_calls for result in results),
        "mean_total_tokens": statistics.mean(result.total_tokens for result in results),
    }


def run_codebase_benchmark(
    *,
    model_path_or_repo: str,
    output_path: Path,
    baseline_max_tokens: int,
    chunk_max_tokens: int,
    no_validator_chunk_max_tokens: int,
    recursive_chunk_max_tokens: int,
) -> dict[str, object]:
    model = MLXPromptModel(model_path_or_repo)
    files = load_files()
    tasks = build_tasks()
    baseline_results: list[RepoConditionResult] = []
    no_validator_results: list[RepoConditionResult] = []
    managed_results: list[RepoConditionResult] = []
    recursive_results: list[RepoConditionResult] = []
    runs: list[dict[str, object]] = []

    for task in tasks:
        baseline = run_baseline(task, files, model, max_tokens=baseline_max_tokens)
        no_validator = run_no_validator(task, files, model, max_tokens=no_validator_chunk_max_tokens)
        managed = run_managed(task, files, model, max_tokens=chunk_max_tokens)
        recursive = run_recursive(task, files, model, max_tokens=recursive_chunk_max_tokens)
        baseline_results.append(baseline)
        no_validator_results.append(no_validator)
        managed_results.append(managed)
        recursive_results.append(recursive)
        runs.append(
            {
                "task_id": task.task_id,
                "question": task.question,
                "expected_paths": task.expected_paths,
                "baseline": asdict(baseline),
                "no_validator": asdict(no_validator),
                "managed": asdict(managed),
                "recursive": asdict(recursive),
            }
        )

    summary = {
        "label": "codebase-benchmark",
        "model_path_or_repo": model_path_or_repo,
        "files": FILE_PATHS,
        "baseline": summarize_condition(baseline_results),
        "no_validator": summarize_condition(no_validator_results),
        "managed": summarize_condition(managed_results),
        "recursive": summarize_condition(recursive_results),
        "runs": runs,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def build_codebase_report(path: Path) -> str:
    payload = json.loads(path.read_text())
    method_metrics = {
        "Baseline": payload["baseline"],
        "No-validator": payload["no_validator"],
        "Managed": payload["managed"],
        "Recursive": payload["recursive"],
    }
    method_summary = render_table(
        ["Method", "Accuracy", "Mean latency (s)", "Mean calls", "Mean total tokens"],
        [
            ["Baseline", format_float(payload["baseline"]["accuracy"]), format_float(payload["baseline"]["mean_latency_seconds"]), format_float(payload["baseline"]["mean_model_calls"]), format_float(payload["baseline"]["mean_total_tokens"], 0)],
            ["No-validator", format_float(payload["no_validator"]["accuracy"]), format_float(payload["no_validator"]["mean_latency_seconds"]), format_float(payload["no_validator"]["mean_model_calls"]), format_float(payload["no_validator"]["mean_total_tokens"], 0)],
            ["Managed", format_float(payload["managed"]["accuracy"]), format_float(payload["managed"]["mean_latency_seconds"]), format_float(payload["managed"]["mean_model_calls"]), format_float(payload["managed"]["mean_total_tokens"], 0)],
            ["Recursive", format_float(payload["recursive"]["accuracy"]), format_float(payload["recursive"]["mean_latency_seconds"]), format_float(payload["recursive"]["mean_model_calls"]), format_float(payload["recursive"]["mean_total_tokens"], 0)],
        ],
    )
    task_rows = []
    for run in payload["runs"]:
        task_rows.append(
            [
                run["task_id"],
                str(len(run["expected_paths"])),
                "yes" if run["baseline"]["exact_match"] else "no",
                "yes" if run["no_validator"]["exact_match"] else "no",
                "yes" if run["managed"]["exact_match"] else "no",
                "yes" if run["recursive"]["exact_match"] else "no",
            ]
        )
    task_table = render_table(
        ["Task", "Expected files", "Baseline", "No-validator", "Managed", "Recursive"],
        task_rows,
    )
    leader, leader_metrics = max(method_metrics.items(), key=lambda item: item[1]["accuracy"])
    baseline_wins = sum(
        1
        for run in payload["runs"]
        if run["baseline"]["exact_match"]
        and not run["no_validator"]["exact_match"]
        and not run["managed"]["exact_match"]
        and not run["recursive"]["exact_match"]
    )
    if leader == "Baseline":
        interpretation = (
            "This is the strongest negative result in the repo so far. On this real file-selection task, the one-shot baseline "
            f"was the best method at {format_float(leader_metrics['accuracy'])} accuracy and won outright on {baseline_wins} tasks. "
            "The current managed scaffolds over-selected files because they broke the repository into narrow local decisions and lost the global sense of which files were necessary versus merely related."
        )
        conclusion = (
            "The broad hypothesis is not yet proven on real repository understanding. Better management helps on the synthetic suites, "
            "but this particular decomposition policy does not transfer to small real file-selection tasks. The next improvement should be a different manager for codebases, not just more of the current one."
        )
    else:
        interpretation = (
            "This benchmark uses real files from this repository, so a managed win here would be stronger evidence than the synthetic families alone. "
            f"In this run, {leader} was the strongest method at {format_float(leader_metrics['accuracy'])} accuracy."
        )
        conclusion = (
            "A positive result here supports real-task transfer for file selection on this codebase. "
            "It is still not the same as patch generation or bug fixing, but it is a meaningful step toward a real codebase benchmark."
        )
    return "\n\n".join(
        [
            "# Codebase Benchmark Report",
            "This benchmark uses real files from this repository and asks the model to select the exact file set needed to answer repository-understanding questions.",
            "## Method Summary",
            method_summary,
            "## Per-task Results",
            task_table,
            "## Interpretation",
            interpretation,
            "## Conclusion",
            conclusion,
        ]
    ) + "\n"
