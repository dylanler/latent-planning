from __future__ import annotations

import json
import random
import re
import statistics
import textwrap
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

DEFAULT_MODEL_REPO = "mlx-community/gemma-4-e2b-it-4bit"
DEFAULT_CRITERIA = ("ORCHID", "release", "amber")

PROJECTS = ["ORCHID", "EMBER", "NOVA", "LATTICE"]
STAGES = ["draft", "review", "release"]
MARKERS = ["amber", "teal", "violet"]
SEALS = ["AX7", "BZ3", "CM9", "DQ4", "ER8", "FT2", "GV5", "HW1", "JK6", "LP0", "MN4", "QR7", "ST8"]
NOTES = [
    "Nightly cache drift forced a retry, but the pipeline stabilized afterward.",
    "Vendor reconciliation surfaced a harmless mismatch in the rehearsal worksheet.",
    "Pager rotation changed immediately after the smoke test completed cleanly.",
    "A stale checklist item lingered even though the dependency had already landed.",
]

@dataclass(frozen=True)
class Record:
    record_id: str
    project: str
    stage: str
    marker: str
    phase: int
    seal: str
    note: str
    section_index: int

    def render(self) -> str:
        return textwrap.dedent(
            f"""\
            Record ID: {self.record_id}
            Project: {self.project}
            Stage: {self.stage}
            Marker: {self.marker}
            Phase: {self.phase}
            Seal: {self.seal}
            Note: {self.note}
            """
        ).strip()


@dataclass(frozen=True)
class Task:
    seed: int
    sections: int
    distractors_per_section: int
    note_repeats: int
    criteria: tuple[str, str, str]
    section_texts: list[str]
    records_by_id: dict[str, Record]
    expected_record_ids: list[str]
    expected_answer: str
    full_report: str


@dataclass(frozen=True)
class ConditionResult:
    answer: str
    exact_match: bool
    latency_seconds: float
    model_calls: int
    raw_output: str
    candidate_record_ids: list[str]


class MLXPromptModel:
    def __init__(self, model_path_or_repo: str) -> None:
        self.model_path_or_repo = model_path_or_repo
        self.model, self.tokenizer = load(model_path_or_repo)
        self.sampler = make_sampler(temp=0.0)

    def generate(self, user_prompt: str, *, max_tokens: int) -> tuple[str, float]:
        prompt = (
            (self.tokenizer.bos_token or "")
            + "<|turn>user\n"
            + user_prompt.strip()
            + "<turn|>\n<|turn>model\n"
        )
        started = time.perf_counter()
        output = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
            sampler=self.sampler,
        ).strip()
        return output, time.perf_counter() - started


def build_results_path(model_path_or_repo: str | Path) -> Path:
    model_value = str(model_path_or_repo)
    cache_repo_match = re.search(r"models--([^/]+)--([^/]+)/snapshots/", model_value)
    if cache_repo_match:
        model_name = f"{cache_repo_match.group(1)}-{cache_repo_match.group(2)}"
    else:
        model_name = Path(model_value).name if "/" in model_value else model_value
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", model_name).strip("-").lower()
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("results") / f"{timestamp}-{safe_name}-pilot.json"


def discover_local_model_snapshot(model_repo: str) -> Path | None:
    repo_dir = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{model_repo.replace('/', '--')}"
    refs_main = repo_dir / "refs" / "main"
    if refs_main.exists():
        revision = refs_main.read_text().strip()
        snapshot = repo_dir / "snapshots" / revision
        if snapshot.exists():
            return snapshot
    snapshots = sorted((repo_dir / "snapshots").glob("*")) if (repo_dir / "snapshots").exists() else []
    return snapshots[0] if snapshots else None


def expand_note(rng: random.Random, note_repeats: int) -> str:
    return " ".join(rng.choice(NOTES) for _ in range(note_repeats))


def generate_task(seed: int, *, sections: int, distractors_per_section: int, note_repeats: int) -> Task:
    rng = random.Random(seed)
    section_texts: list[str] = []
    records_by_id: dict[str, Record] = {}
    expected_record_ids: list[str] = []
    expected_pairs: list[tuple[int, str]] = []
    criteria = DEFAULT_CRITERIA

    for section_index in range(1, sections + 1):
        target_id = f"T{section_index}"
        target = Record(
            record_id=target_id,
            project=criteria[0],
            stage=criteria[1],
            marker=criteria[2],
            phase=section_index,
            seal=rng.choice(SEALS),
            note=expand_note(rng, note_repeats),
            section_index=section_index,
        )
        expected_record_ids.append(target.record_id)
        expected_pairs.append((target.phase, target.seal))

        records = [target]
        for distractor_index in range(distractors_per_section):
            while True:
                project = rng.choice(PROJECTS)
                stage = rng.choice(STAGES)
                marker = rng.choice(MARKERS)
                if (project, stage, marker) != criteria:
                    break
            record = Record(
                record_id=f"D{section_index}_{distractor_index}",
                project=project,
                stage=stage,
                marker=marker,
                phase=rng.randint(1, sections + distractors_per_section),
                seal=rng.choice(SEALS),
                note=expand_note(rng, note_repeats),
                section_index=section_index,
            )
            records.append(record)

        rng.shuffle(records)
        section_body = "\n\n".join(record.render() for record in records)
        section_texts.append(f"=== SECTION {section_index} ===\n{section_body}")
        for record in records:
            records_by_id[record.record_id] = record

    expected_answer = "-".join(seal for _, seal in sorted(expected_pairs))
    return Task(
        seed=seed,
        sections=sections,
        distractors_per_section=distractors_per_section,
        note_repeats=note_repeats,
        criteria=criteria,
        section_texts=section_texts,
        records_by_id=records_by_id,
        expected_record_ids=expected_record_ids,
        expected_answer=expected_answer,
        full_report="\n\n".join(section_texts),
    )


def build_baseline_prompt(task: Task) -> str:
    project, stage, marker = task.criteria
    return textwrap.dedent(
        f"""\
        Read the full report and solve the task exactly.

        Task:
        1. Select only records where Project={project}, Stage={stage}, and Marker={marker}.
        2. Sort those records by Phase ascending.
        3. Return exactly one line in the format ANSWER=<seal-1>-<seal-2>-... and nothing else.

        Report:
        {task.full_report}
        """
    )


def build_chunk_prompt(task: Task, section_text: str) -> str:
    project, stage, marker = task.criteria
    return textwrap.dedent(
        f"""\
        Inspect this section only.

        Return a plain comma-separated list of record IDs that might satisfy all three exact conditions:
        - Project={project}
        - Stage={stage}
        - Marker={marker}

        Be permissive: if you are unsure, include the record ID.
        If no record is even plausible, return NONE.
        Return only the IDs or NONE.

        Section:
        {section_text}
        """
    )


def normalize_baseline_answer(raw_output: str) -> str:
    match = re.search(r"ANSWER=([A-Z0-9-]+)", raw_output)
    return match.group(1) if match else raw_output.strip()


def extract_candidate_ids(raw_output: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"(?:T\d+|D\d+_\d+)", raw_output)))


def validate_candidates(task: Task, candidate_ids: Iterable[str]) -> list[Record]:
    validated: dict[str, Record] = {}
    for record_id in candidate_ids:
        record = task.records_by_id.get(record_id)
        if not record:
            continue
        if (record.project, record.stage, record.marker) == task.criteria:
            validated[record_id] = record
    return sorted(validated.values(), key=lambda record: record.phase)


def run_baseline(task: Task, model: MLXPromptModel, *, max_tokens: int) -> ConditionResult:
    raw_output, latency_seconds = model.generate(build_baseline_prompt(task), max_tokens=max_tokens)
    answer = normalize_baseline_answer(raw_output)
    return ConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=latency_seconds,
        model_calls=1,
        raw_output=raw_output,
        candidate_record_ids=[],
    )


def run_managed(task: Task, model: MLXPromptModel, *, max_tokens: int) -> ConditionResult:
    raw_outputs: list[str] = []
    candidate_ids: list[str] = []
    total_latency = 0.0
    for section_text in task.section_texts:
        raw_output, latency_seconds = model.generate(build_chunk_prompt(task, section_text), max_tokens=max_tokens)
        raw_outputs.append(raw_output)
        total_latency += latency_seconds
        candidate_ids.extend(extract_candidate_ids(raw_output))

    validated_records = validate_candidates(task, candidate_ids)
    answer = "-".join(record.seal for record in validated_records)
    return ConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=total_latency,
        model_calls=len(task.section_texts),
        raw_output="\n---\n".join(raw_outputs),
        candidate_record_ids=[record.record_id for record in validated_records],
    )


def summarize_condition(results: list[ConditionResult]) -> dict[str, float]:
    return {
        "accuracy": sum(result.exact_match for result in results) / len(results),
        "mean_latency_seconds": statistics.mean(result.latency_seconds for result in results),
        "mean_model_calls": statistics.mean(result.model_calls for result in results),
    }


def run_pilot(
    *,
    model_path_or_repo: str,
    label: str | None,
    sections: int,
    distractors_per_section: list[int],
    seeds: list[int],
    note_repeats: int,
    output_path: Path,
    baseline_max_tokens: int,
    chunk_max_tokens: int,
) -> dict[str, object]:
    model = MLXPromptModel(model_path_or_repo)
    runs: list[dict[str, object]] = []
    baseline_results: list[ConditionResult] = []
    managed_results: list[ConditionResult] = []

    for distractor_count in distractors_per_section:
        for seed in seeds:
            task = generate_task(
                seed,
                sections=sections,
                distractors_per_section=distractor_count,
                note_repeats=note_repeats,
            )
            baseline = run_baseline(task, model, max_tokens=baseline_max_tokens)
            managed = run_managed(task, model, max_tokens=chunk_max_tokens)
            baseline_results.append(baseline)
            managed_results.append(managed)
            runs.append(
                {
                    "label": label,
                    "seed": seed,
                    "sections": sections,
                    "distractors_per_section": distractor_count,
                    "note_repeats": note_repeats,
                    "report_characters": len(task.full_report),
                    "mean_section_characters": statistics.mean(len(section) for section in task.section_texts),
                    "expected_answer": task.expected_answer,
                    "expected_record_ids": task.expected_record_ids,
                    "baseline": asdict(baseline),
                    "managed": asdict(managed),
                }
            )

    summary = {
        "label": label,
        "model_path_or_repo": model_path_or_repo,
        "criteria": {
            "project": DEFAULT_CRITERIA[0],
            "stage": DEFAULT_CRITERIA[1],
            "marker": DEFAULT_CRITERIA[2],
        },
        "sections": sections,
        "distractors_per_section": distractors_per_section,
        "seeds": seeds,
        "note_repeats": note_repeats,
        "baseline": summarize_condition(baseline_results),
        "managed": summarize_condition(managed_results),
        "runs": runs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary
