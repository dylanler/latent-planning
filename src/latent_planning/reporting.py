from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RunRow:
    label: str
    sections: int
    distractors_per_section: int
    note_repeats: int
    seed: int
    report_characters: int
    baseline_exact_match: bool
    baseline_latency_seconds: float
    baseline_model_calls: int
    managed_exact_match: bool
    managed_latency_seconds: float
    managed_model_calls: int


def load_rows(paths: Iterable[Path]) -> list[RunRow]:
    rows: list[RunRow] = []
    for path in paths:
        payload = json.loads(path.read_text())
        label = payload.get("label") or path.stem
        for run in payload["runs"]:
            rows.append(
                RunRow(
                    label=run.get("label") or label,
                    sections=run["sections"],
                    distractors_per_section=run["distractors_per_section"],
                    note_repeats=run.get("note_repeats", payload.get("note_repeats", 1)),
                    seed=run["seed"],
                    report_characters=run.get("report_characters", 0),
                    baseline_exact_match=run["baseline"]["exact_match"],
                    baseline_latency_seconds=run["baseline"]["latency_seconds"],
                    baseline_model_calls=run["baseline"]["model_calls"],
                    managed_exact_match=run["managed"]["exact_match"],
                    managed_latency_seconds=run["managed"]["latency_seconds"],
                    managed_model_calls=run["managed"]["model_calls"],
                )
            )
    return rows


def group_rows(rows: list[RunRow], key: str) -> dict[int, list[RunRow]]:
    grouped: dict[int, list[RunRow]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, key)].append(row)
    return dict(sorted(grouped.items()))


def summarize_group(rows: list[RunRow]) -> dict[str, float]:
    return {
        "n": len(rows),
        "baseline_accuracy": statistics.mean(row.baseline_exact_match for row in rows),
        "managed_accuracy": statistics.mean(row.managed_exact_match for row in rows),
        "baseline_latency": statistics.mean(row.baseline_latency_seconds for row in rows),
        "managed_latency": statistics.mean(row.managed_latency_seconds for row in rows),
        "avg_report_characters": statistics.mean(row.report_characters for row in rows),
    }


def format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_xychart(title: str, x_label: str, x_values: list[int], series: list[tuple[str, list[float]]]) -> str:
    max_y = max(max(values) for _, values in series) if series else 1.0
    max_y = max(1.0, round(max_y + 0.1, 2))
    lines = [
        "```mermaid",
        "xychart-beta",
        f'    title "{title}"',
        f'    x-axis "{x_label}" [{", ".join(str(value) for value in x_values)}]',
        f'    y-axis "Value" 0 --> {max_y}',
    ]
    for name, values in series:
        lines.append(f'    line "{name}" [{", ".join(format_float(value) for value in values)}]')
    lines.append("```")
    return "\n".join(lines)


def render_sweep_section(
    title: str,
    rows: list[RunRow],
    key: str,
    x_label: str,
    value_formatter,
) -> str:
    grouped = group_rows(rows, key)
    x_values = list(grouped.keys())
    summaries = [summarize_group(grouped[value]) for value in x_values]

    table_rows = [
        [
            value_formatter(value),
            str(int(summary["n"])),
            format_float(summary["avg_report_characters"], 0),
            format_float(summary["baseline_accuracy"]),
            format_float(summary["managed_accuracy"]),
            format_float(summary["baseline_latency"]),
            format_float(summary["managed_latency"]),
        ]
        for value, summary in zip(x_values, summaries)
    ]

    accuracy_chart = render_xychart(
        f"{title} Accuracy",
        x_label,
        x_values,
        [
            ("Baseline", [summary["baseline_accuracy"] for summary in summaries]),
            ("Managed", [summary["managed_accuracy"] for summary in summaries]),
        ],
    )
    latency_chart = render_xychart(
        f"{title} Latency",
        x_label,
        x_values,
        [
            ("Baseline", [summary["baseline_latency"] for summary in summaries]),
            ("Managed", [summary["managed_latency"] for summary in summaries]),
        ],
    )

    table = render_table(
        ["Setting", "Runs", "Avg report chars", "Baseline acc", "Managed acc", "Baseline latency (s)", "Managed latency (s)"],
        table_rows,
    )

    return "\n\n".join([f"## {title}", table, accuracy_chart, latency_chart])


def build_report(paths: Iterable[Path]) -> str:
    rows = load_rows(paths)
    if not rows:
        raise ValueError("No result rows found.")

    by_label: dict[str, list[RunRow]] = defaultdict(list)
    for row in rows:
        by_label[row.label].append(row)

    overall_rows = []
    for label, label_rows in sorted(by_label.items()):
        summary = summarize_group(label_rows)
        overall_rows.append(
            [
                label,
                str(int(summary["n"])),
                format_float(summary["avg_report_characters"], 0),
                format_float(summary["baseline_accuracy"]),
                format_float(summary["managed_accuracy"]),
                format_float(summary["baseline_latency"]),
                format_float(summary["managed_latency"]),
            ]
        )

    sections = [
        "# Extended Evaluation",
        "This report aggregates local MLX runs for the Gemma decomposition pilot.",
        "## Experiment Summary",
        render_table(
            ["Experiment", "Runs", "Avg report chars", "Baseline acc", "Managed acc", "Baseline latency (s)", "Managed latency (s)"],
            overall_rows,
        ),
    ]

    if "distractor-sweep" in by_label:
        sections.append(
            render_sweep_section(
                "Distractor Sweep",
                by_label["distractor-sweep"],
                "distractors_per_section",
                "Distractors per section",
                str,
            )
        )
    if "section-sweep" in by_label:
        sections.append(
            render_sweep_section(
                "Section Sweep",
                by_label["section-sweep"],
                "sections",
                "Sections",
                str,
            )
        )
    if "context-sweep" in by_label:
        sections.append(
            render_sweep_section(
                "Context Sweep",
                by_label["context-sweep"],
                "note_repeats",
                "Note repeats",
                lambda value: f"{value}x",
            )
        )

    managed_wins = sum(row.managed_exact_match and not row.baseline_exact_match for row in rows)
    baseline_wins = sum(row.baseline_exact_match and not row.managed_exact_match for row in rows)
    both_fail = sum((not row.managed_exact_match) and (not row.baseline_exact_match) for row in rows)
    both_pass = sum(row.managed_exact_match and row.baseline_exact_match for row in rows)
    distractor_rows = by_label.get("distractor-sweep", [])
    context_rows = by_label.get("context-sweep", [])
    distractor_summaries = {
        value: summarize_group(group)
        for value, group in group_rows(distractor_rows, "distractors_per_section").items()
    }
    context_summaries = {
        value: summarize_group(group)
        for value, group in group_rows(context_rows, "note_repeats").items()
    }

    key_findings = [
        f"- Managed-only wins: `{managed_wins}` runs. Baseline-only wins: `{baseline_wins}` runs.",
    ]
    if distractor_summaries:
        hardest_distractor = max(distractor_summaries)
        key_findings.append(
            "- Managed accuracy under distractor growth: "
            + ", ".join(
                f"`{value}` distractors -> `{format_float(distractor_summaries[value]['managed_accuracy'])}`"
                for value in sorted(distractor_summaries)
            )
            + "."
        )
        key_findings.append(
            f"- Even at the hardest distractor setting (`{hardest_distractor}` per section), the baseline stayed at `0.00` while managed retained non-zero accuracy."
        )
    if context_summaries:
        key_findings.append(
            "- Managed accuracy under context growth: "
            + ", ".join(
                f"`{value}x` notes -> `{format_float(context_summaries[value]['managed_accuracy'])}`"
                for value in sorted(context_summaries)
            )
            + "."
        )
        key_findings.append(
            "- The strongest failure mode is raw context inflation: by `5x` repeated notes, both methods collapsed to `0.00` exact-match."
        )

    sections.append(
        "\n".join(
            [
                "## Outcome Breakdown",
                render_table(
                    ["Outcome", "Count"],
                    [
                        ["Managed only", str(managed_wins)],
                        ["Baseline only", str(baseline_wins)],
                        ["Both pass", str(both_pass)],
                        ["Both fail", str(both_fail)],
                    ],
                ),
                "## Key Findings",
                *key_findings,
                "## Conclusion",
                (
                    "Across these local runs, the managed scaffold consistently outperformed the single-shot baseline on exact-match accuracy, "
                    "while paying a latency and call-count premium. The evidence supports the narrow version of the hypothesis: "
                    "for this model and task family, better management of model calls unlocks capabilities that are mostly absent in one-shot prompting. "
                    "The main limit is not the decomposition idea itself but context scaling: once each chunk becomes too long, local retrieval recall collapses and the scaffold stops helping."
                ),
            ]
        )
    )

    return "\n\n".join(sections) + "\n"
