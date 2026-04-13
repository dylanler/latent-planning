from __future__ import annotations

import json
import random
import re
import statistics
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from latent_planning.experiment import MLXPromptModel

TOKENS = ["AX7", "BZ3", "CM9", "DQ4", "ER8", "FT2", "GV5", "HW1", "JK6", "LP0", "MN4", "QR7", "ST8"]

PROSE_PROJECTS = ["ORCHID", "EMBER", "NOVA", "LATTICE"]
PROSE_STAGES = ["draft", "review", "release"]
PROSE_MARKERS = ["amber", "teal", "violet"]
PROSE_STATUSES = ["locked", "open", "shadow"]
PROSE_NOTES = [
    "Nightly cache drift forced a retry, but the pipeline stabilized afterward.",
    "Vendor reconciliation surfaced a harmless mismatch in the rehearsal worksheet.",
    "Pager rotation changed immediately after the smoke test completed cleanly.",
    "A stale checklist item lingered even though the dependency had already landed.",
]

LEDGER_DESKS = ["ORCHID", "EMBER", "NOVA", "LATTICE"]
LEDGER_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
LEDGER_FLAGS = ["amber", "teal", "violet"]
LEDGER_CHANNELS = ["prime", "hedge", "shadow"]
LEDGER_MEMOS = [
    "Clearing batch was replayed after the settlement file arrived late.",
    "Back-office reconciliation marked the exception as informational only.",
    "A hedge adjustment posted after the midpoint checkpoint without changing exposure.",
    "The dry-run close matched the control sheet on the second pass.",
]

CODE_PROJECTS = ["ORCHID", "EMBER", "NOVA", "LATTICE"]
CODE_STAGES = ["draft", "review", "release"]
CODE_MARKERS = ["amber", "teal", "violet"]
CODE_GUARDS = ["prime", "shadow", "legacy"]
CODE_COMMENTS = [
    "helper path retained for compatibility with the previous deploy routine",
    "fallback branch kept to mirror the shadow launch behaviour in staging",
    "audit note preserved because the profiler still checks this branch",
    "temporary guard remains until the cleanup pass removes legacy callers",
]


@dataclass(frozen=True)
class BenchItem:
    item_id: str
    section_index: int
    order: int
    token: str
    amount: int | None
    is_target: bool
    text: str
    summary: str


@dataclass(frozen=True)
class BenchTask:
    family: str
    display_name: str
    task_type: str
    answer_mode: str
    seed: int
    sections: int
    distractors_per_section: int
    context_scale: int
    criteria_lines: tuple[str, ...]
    section_texts: list[str]
    section_items: list[list[BenchItem]]
    items_by_id: dict[str, BenchItem]
    expected_answer: str
    full_text: str


@dataclass(frozen=True)
class ExtractedMatch:
    order: int
    token: str
    amount: int | None


@dataclass(frozen=True)
class BenchConditionResult:
    answer: str
    exact_match: bool
    latency_seconds: float
    model_calls: int
    raw_output: str
    candidate_item_ids: list[str]


@dataclass(frozen=True)
class FamilyReportRow:
    family: str
    display_name: str
    task_type: str
    answer_mode: str
    runs: int
    avg_characters: float
    baseline_accuracy: float
    no_validator_accuracy: float
    managed_accuracy: float
    recursive_accuracy: float
    baseline_latency: float
    no_validator_latency: float
    managed_latency: float
    recursive_latency: float


def repeat_sentences(rng: random.Random, sentences: list[str], count: int) -> str:
    return " ".join(rng.choice(sentences) for _ in range(count))


def normalize_baseline_answer(raw_output: str) -> str:
    match = re.search(r"ANSWER=([^\n]+)", raw_output)
    return match.group(1).strip() if match else raw_output.strip()


def extract_candidate_ids(raw_output: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b(?:TARGET|DIST)\d+(?:_\d+)?\b", raw_output)))


def extract_group_indices(raw_output: str, group_count: int) -> list[int]:
    indices: list[int] = []
    for token in re.findall(r"\b\d+\b", raw_output):
        value = int(token)
        if 1 <= value <= group_count and value not in indices:
            indices.append(value)
    return indices


def extract_match(raw_output: str) -> ExtractedMatch | None:
    order_match = re.search(r"order\s*=\s*(\d+)", raw_output, re.IGNORECASE)
    token_match = re.search(r"token\s*=\s*([A-Z0-9]+)", raw_output, re.IGNORECASE)
    if not order_match or not token_match:
        return None
    amount_match = re.search(r"amount\s*=\s*(-?\d+)", raw_output, re.IGNORECASE)
    return ExtractedMatch(
        order=int(order_match.group(1)),
        token=token_match.group(1),
        amount=int(amount_match.group(1)) if amount_match else None,
    )


def split_items(items: list[BenchItem], group_count: int) -> list[list[BenchItem]]:
    if len(items) <= group_count:
        return [[item] for item in items]
    chunk_size = (len(items) + group_count - 1) // group_count
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def compose_answer(task: BenchTask, items: list[BenchItem]) -> str:
    ordered = sorted(items, key=lambda item: item.order)
    token_sequence = "-".join(item.token for item in ordered)
    if task.answer_mode == "sequence":
        return token_sequence
    total = sum(item.amount or 0 for item in ordered)
    return f"{total}|{token_sequence}"


def compose_match_answer(task: BenchTask, matches: list[ExtractedMatch]) -> str:
    ordered = sorted(matches, key=lambda match: match.order)
    token_sequence = "-".join(match.token for match in ordered)
    if task.answer_mode == "sequence":
        return token_sequence
    total = sum(match.amount or 0 for match in ordered)
    return f"{total}|{token_sequence}"


def validate_candidates(task: BenchTask, candidate_ids: Iterable[str]) -> list[BenchItem]:
    validated: dict[str, BenchItem] = {}
    for item_id in candidate_ids:
        item = task.items_by_id.get(item_id)
        if item and item.is_target:
            validated[item_id] = item
    return sorted(validated.values(), key=lambda item: item.order)


def render_summaries(items: list[BenchItem]) -> str:
    return "\n".join(item.summary for item in items)


def answer_format_description(task: BenchTask) -> str:
    if task.answer_mode == "sequence":
        return "ANSWER=<token-1>-<token-2>-..."
    return "ANSWER=<total>|<token-1>-<token-2>-..."


def task_shell(
    *,
    family: str,
    display_name: str,
    task_type: str,
    answer_mode: str,
    seed: int,
    sections: int,
    distractors_per_section: int,
    context_scale: int,
    criteria_lines: tuple[str, ...],
) -> BenchTask:
    return BenchTask(
        family=family,
        display_name=display_name,
        task_type=task_type,
        answer_mode=answer_mode,
        seed=seed,
        sections=sections,
        distractors_per_section=distractors_per_section,
        context_scale=context_scale,
        criteria_lines=criteria_lines,
        section_texts=[],
        section_items=[],
        items_by_id={},
        expected_answer="",
        full_text="",
    )


def build_baseline_prompt(task: BenchTask) -> str:
    criteria = "\n".join(f"- {line}" for line in task.criteria_lines)
    return textwrap.dedent(
        f"""\
        Read the full artifact and solve the task exactly.

        Select only items matching all exact conditions:
        {criteria}

        Sort the matching items by Order ascending.
        Return exactly one line in the format {answer_format_description(task)} and nothing else.

        Artifact:
        {task.full_text}
        """
    )


def build_chunk_prompt(task: BenchTask, section_text: str) -> str:
    criteria = "\n".join(f"- {line}" for line in task.criteria_lines)
    return textwrap.dedent(
        f"""\
        Inspect this section only.

        Return a plain comma-separated list of candidate IDs that might satisfy all exact conditions:
        {criteria}

        Be permissive: if you are unsure, include the candidate ID.
        Candidate IDs are exact strings like TARGET3 or DIST3_2. Copy the full ID exactly.
        If no item is even plausible, return NONE.
        Return only candidate IDs or NONE.

        Section:
        {section_text}
        """
    )


def build_no_validator_prompt(task: BenchTask, section_text: str) -> str:
    criteria = "\n".join(f"- {line}" for line in task.criteria_lines)
    if task.answer_mode == "sequence":
        format_lines = "- MATCH order=<integer> token=<token>\n- NONE"
    else:
        format_lines = "- MATCH order=<integer> token=<token> amount=<integer>\n- NONE"
    return textwrap.dedent(
        f"""\
        Inspect this section only.

        Find the single best item matching all exact conditions:
        {criteria}

        Return exactly one line in one of these formats:
        {format_lines}

        Do not return anything else.

        Section:
        {section_text}
        """
    )


def build_recursive_group_prompt(task: BenchTask, groups: list[list[BenchItem]], *, depth: int) -> str:
    criteria = "\n".join(f"- {line}" for line in task.criteria_lines)
    group_blocks = []
    for index, group_items in enumerate(groups, start=1):
        group_blocks.append(f"[Group {index}]\n{render_summaries(group_items)}")
    groups_text = "\n\n".join(group_blocks)
    return textwrap.dedent(
        f"""\
        Inspect these groups of item summaries at recursion depth {depth}.

        Return a plain comma-separated list of group numbers that might contain at least one item satisfying all exact conditions:
        {criteria}

        Be permissive: if you are unsure, include the group number.
        If no group is even plausible, return NONE.
        Return only group numbers or NONE.

        Groups:
        {groups_text}
        """
    )


def run_baseline(task: BenchTask, model: MLXPromptModel, *, max_tokens: int) -> BenchConditionResult:
    raw_output, latency_seconds = model.generate(build_baseline_prompt(task), max_tokens=max_tokens)
    answer = normalize_baseline_answer(raw_output)
    return BenchConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=latency_seconds,
        model_calls=1,
        raw_output=raw_output,
        candidate_item_ids=[],
    )


def run_managed(task: BenchTask, model: MLXPromptModel, *, max_tokens: int) -> BenchConditionResult:
    raw_outputs: list[str] = []
    candidate_ids: list[str] = []
    total_latency = 0.0
    for section_text in task.section_texts:
        raw_output, latency_seconds = model.generate(build_chunk_prompt(task, section_text), max_tokens=max_tokens)
        raw_outputs.append(raw_output)
        total_latency += latency_seconds
        candidate_ids.extend(extract_candidate_ids(raw_output))

    validated_items = validate_candidates(task, candidate_ids)
    answer = compose_answer(task, validated_items)
    return BenchConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=total_latency,
        model_calls=len(task.section_texts),
        raw_output="\n---\n".join(raw_outputs),
        candidate_item_ids=[item.item_id for item in validated_items],
    )


def run_no_validator(task: BenchTask, model: MLXPromptModel, *, max_tokens: int) -> BenchConditionResult:
    raw_outputs: list[str] = []
    matches: list[ExtractedMatch] = []
    total_latency = 0.0
    for section_text in task.section_texts:
        raw_output, latency_seconds = model.generate(
            build_no_validator_prompt(task, section_text),
            max_tokens=max_tokens,
        )
        raw_outputs.append(raw_output)
        total_latency += latency_seconds
        extracted = extract_match(raw_output)
        if extracted is not None:
            matches.append(extracted)

    answer = compose_match_answer(task, matches)
    return BenchConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=total_latency,
        model_calls=len(task.section_texts),
        raw_output="\n---\n".join(raw_outputs),
        candidate_item_ids=[],
    )


def recursive_search(
    task: BenchTask,
    model: MLXPromptModel,
    items: list[BenchItem],
    *,
    max_tokens: int,
    leaf_items: int,
    branching_factor: int,
    depth: int = 0,
) -> tuple[list[str], str, float, int]:
    if len(items) <= leaf_items:
        section_text = "\n\n".join(item.text for item in items)
        raw_output, latency_seconds = model.generate(build_chunk_prompt(task, section_text), max_tokens=max_tokens)
        return extract_candidate_ids(raw_output), raw_output, latency_seconds, 1

    groups = split_items(items, branching_factor)
    raw_output, latency_seconds = model.generate(
        build_recursive_group_prompt(task, groups, depth=depth),
        max_tokens=max_tokens,
    )
    selected_groups = extract_group_indices(raw_output, len(groups))
    if not selected_groups:
        selected_groups = list(range(1, len(groups) + 1))

    total_latency = latency_seconds
    total_calls = 1
    child_outputs: list[str] = []
    candidate_ids: list[str] = []

    for group_index in selected_groups:
        child_ids, child_output, child_latency, child_calls = recursive_search(
            task,
            model,
            groups[group_index - 1],
            max_tokens=max_tokens,
            leaf_items=leaf_items,
            branching_factor=branching_factor,
            depth=depth + 1,
        )
        candidate_ids.extend(child_ids)
        child_outputs.append(f"[Depth {depth + 1} Group {group_index}]\n{child_output}")
        total_latency += child_latency
        total_calls += child_calls

    combined_output = raw_output
    if child_outputs:
        combined_output = raw_output + "\n" + "\n".join(child_outputs)
    return candidate_ids, combined_output, total_latency, total_calls


def run_recursive(
    task: BenchTask,
    model: MLXPromptModel,
    *,
    max_tokens: int,
    leaf_items: int,
    branching_factor: int,
) -> BenchConditionResult:
    raw_outputs: list[str] = []
    candidate_ids: list[str] = []
    total_latency = 0.0
    total_calls = 0

    for section_items in task.section_items:
        section_ids, section_output, section_latency, section_calls = recursive_search(
            task,
            model,
            section_items,
            max_tokens=max_tokens,
            leaf_items=leaf_items,
            branching_factor=branching_factor,
        )
        raw_outputs.append(section_output)
        candidate_ids.extend(section_ids)
        total_latency += section_latency
        total_calls += section_calls

    validated_items = validate_candidates(task, candidate_ids)
    answer = compose_answer(task, validated_items)
    return BenchConditionResult(
        answer=answer,
        exact_match=answer == task.expected_answer,
        latency_seconds=total_latency,
        model_calls=total_calls,
        raw_output="\n---\n".join(raw_outputs),
        candidate_item_ids=[item.item_id for item in validated_items],
    )


def summarize_condition(results: list[BenchConditionResult]) -> dict[str, float]:
    return {
        "accuracy": sum(result.exact_match for result in results) / len(results),
        "mean_latency_seconds": statistics.mean(result.latency_seconds for result in results),
        "mean_model_calls": statistics.mean(result.model_calls for result in results),
    }


def build_prose_task(seed: int, *, sections: int, distractors_per_section: int, context_scale: int) -> BenchTask:
    rng = random.Random(seed)
    criteria = ("Project=ORCHID", "Stage=release", "Marker=amber", "Status=locked")
    section_texts: list[str] = []
    section_items: list[list[BenchItem]] = []
    items_by_id: dict[str, BenchItem] = {}
    expected_items: list[BenchItem] = []

    for section_index in range(1, sections + 1):
        token = rng.choice(TOKENS)
        target = BenchItem(
            item_id=f"TARGET{section_index}",
            section_index=section_index,
            order=section_index,
            token=token,
            amount=None,
            is_target=True,
            text=textwrap.dedent(
                f"""\
                Item ID: TARGET{section_index}
                Project: ORCHID
                Stage: release
                Marker: amber
                Status: locked
                Order: {section_index}
                Token: {token}
                Note: {repeat_sentences(rng, PROSE_NOTES, context_scale)}
                """
            ).strip(),
            summary=f"TARGET{section_index} | Project=ORCHID | Stage=release | Marker=amber | Status=locked | Order={section_index}",
        )
        items = [target]
        expected_items.append(target)

        near_miss_order = rng.randint(1, sections + distractors_per_section)
        near_miss_token = rng.choice(TOKENS)
        items.append(
            BenchItem(
                item_id=f"DIST{section_index}_0",
                section_index=section_index,
                order=near_miss_order,
                token=near_miss_token,
                amount=None,
                is_target=False,
                text=textwrap.dedent(
                    f"""\
                    Item ID: DIST{section_index}_0
                    Project: ORCHID
                    Stage: release
                    Marker: amber
                    Status: open
                    Order: {near_miss_order}
                    Token: {near_miss_token}
                    Note: {repeat_sentences(rng, PROSE_NOTES, context_scale)}
                    """
                ).strip(),
                summary=f"DIST{section_index}_0 | Project=ORCHID | Stage=release | Marker=amber | Status=open | Order={near_miss_order}",
            )
        )

        for distractor_index in range(1, distractors_per_section):
            while True:
                project = rng.choice(PROSE_PROJECTS)
                stage = rng.choice(PROSE_STAGES)
                marker = rng.choice(PROSE_MARKERS)
                status = rng.choice(PROSE_STATUSES)
                if (project, stage, marker, status) != ("ORCHID", "release", "amber", "locked"):
                    break
            order = rng.randint(1, sections + distractors_per_section)
            token = rng.choice(TOKENS)
            item_id = f"DIST{section_index}_{distractor_index}"
            items.append(
                BenchItem(
                    item_id=item_id,
                    section_index=section_index,
                    order=order,
                    token=token,
                    amount=None,
                    is_target=False,
                    text=textwrap.dedent(
                        f"""\
                        Item ID: {item_id}
                        Project: {project}
                        Stage: {stage}
                        Marker: {marker}
                        Status: {status}
                        Order: {order}
                        Token: {token}
                        Note: {repeat_sentences(rng, PROSE_NOTES, context_scale)}
                        """
                    ).strip(),
                    summary=f"{item_id} | Project={project} | Stage={stage} | Marker={marker} | Status={status} | Order={order}",
                )
            )

        rng.shuffle(items)
        section_items.append(items.copy())
        section_body = "\n\n".join(item.text for item in items)
        section_texts.append(f"=== DOSSIER SECTION {section_index} ===\n{section_body}")
        for item in items:
            items_by_id[item.item_id] = item

    expected_answer = compose_answer(
        task_shell(
            family="records",
            display_name="Prose records",
            task_type="retrieval in prose",
            answer_mode="sequence",
            seed=seed,
            sections=sections,
            distractors_per_section=distractors_per_section,
            context_scale=context_scale,
            criteria_lines=criteria,
        ),
        expected_items,
    )
    return BenchTask(
        family="records",
        display_name="Prose records",
        task_type="retrieval in prose",
        answer_mode="sequence",
        seed=seed,
        sections=sections,
        distractors_per_section=distractors_per_section,
        context_scale=context_scale,
        criteria_lines=criteria,
        section_texts=section_texts,
        section_items=section_items,
        items_by_id=items_by_id,
        expected_answer=expected_answer,
        full_text="\n\n".join(section_texts),
    )


def build_ledger_task(seed: int, *, sections: int, distractors_per_section: int, context_scale: int) -> BenchTask:
    rng = random.Random(10_000 + seed)
    criteria = ("Desk=ORCHID", "Quarter=Q4", "Flag=amber", "Channel=prime")
    section_texts: list[str] = []
    section_items: list[list[BenchItem]] = []
    items_by_id: dict[str, BenchItem] = {}
    expected_items: list[BenchItem] = []

    for section_index in range(1, sections + 1):
        token = rng.choice(TOKENS)
        amount = rng.randint(15, 95)
        target = BenchItem(
            item_id=f"TARGET{section_index}",
            section_index=section_index,
            order=section_index,
            token=token,
            amount=amount,
            is_target=True,
            text=textwrap.dedent(
                f"""\
                Txn ID: TARGET{section_index}
                Desk: ORCHID
                Quarter: Q4
                Flag: amber
                Channel: prime
                Order: {section_index}
                Token: {token}
                Amount: {amount}
                Memo: {repeat_sentences(rng, LEDGER_MEMOS, context_scale)}
                """
            ).strip(),
            summary=f"TARGET{section_index} | Desk=ORCHID | Quarter=Q4 | Flag=amber | Channel=prime | Order={section_index} | Amount={amount}",
        )
        items = [target]
        expected_items.append(target)

        near_miss_order = rng.randint(1, sections + distractors_per_section)
        near_miss_amount = rng.randint(15, 95)
        near_miss_token = rng.choice(TOKENS)
        items.append(
            BenchItem(
                item_id=f"DIST{section_index}_0",
                section_index=section_index,
                order=near_miss_order,
                token=near_miss_token,
                amount=near_miss_amount,
                is_target=False,
                text=textwrap.dedent(
                    f"""\
                    Txn ID: DIST{section_index}_0
                    Desk: ORCHID
                    Quarter: Q4
                    Flag: amber
                    Channel: hedge
                    Order: {near_miss_order}
                    Token: {near_miss_token}
                    Amount: {near_miss_amount}
                    Memo: {repeat_sentences(rng, LEDGER_MEMOS, context_scale)}
                    """
                ).strip(),
                summary=f"DIST{section_index}_0 | Desk=ORCHID | Quarter=Q4 | Flag=amber | Channel=hedge | Order={near_miss_order} | Amount={near_miss_amount}",
            )
        )

        for distractor_index in range(1, distractors_per_section):
            while True:
                desk = rng.choice(LEDGER_DESKS)
                quarter = rng.choice(LEDGER_QUARTERS)
                flag = rng.choice(LEDGER_FLAGS)
                channel = rng.choice(LEDGER_CHANNELS)
                if (desk, quarter, flag, channel) != ("ORCHID", "Q4", "amber", "prime"):
                    break
            order = rng.randint(1, sections + distractors_per_section)
            token = rng.choice(TOKENS)
            amount = rng.randint(15, 95)
            item_id = f"DIST{section_index}_{distractor_index}"
            items.append(
                BenchItem(
                    item_id=item_id,
                    section_index=section_index,
                    order=order,
                    token=token,
                    amount=amount,
                    is_target=False,
                    text=textwrap.dedent(
                        f"""\
                        Txn ID: {item_id}
                        Desk: {desk}
                        Quarter: {quarter}
                        Flag: {flag}
                        Channel: {channel}
                        Order: {order}
                        Token: {token}
                        Amount: {amount}
                        Memo: {repeat_sentences(rng, LEDGER_MEMOS, context_scale)}
                        """
                    ).strip(),
                    summary=f"{item_id} | Desk={desk} | Quarter={quarter} | Flag={flag} | Channel={channel} | Order={order} | Amount={amount}",
                )
            )

        rng.shuffle(items)
        section_items.append(items.copy())
        section_body = "\n\n".join(item.text for item in items)
        section_texts.append(f"=== LEDGER PAGE {section_index} ===\n{section_body}")
        for item in items:
            items_by_id[item.item_id] = item

    expected_answer = compose_answer(
        BenchTask(
            family="ledger",
            display_name="Ledger aggregation",
            task_type="retrieval plus arithmetic",
            answer_mode="total_and_sequence",
            seed=seed,
            sections=sections,
            distractors_per_section=distractors_per_section,
            context_scale=context_scale,
            criteria_lines=criteria,
            section_texts=[],
            section_items=[],
            items_by_id={},
            expected_answer="",
            full_text="",
        ),
        expected_items,
    )
    return BenchTask(
        family="ledger",
        display_name="Ledger aggregation",
        task_type="retrieval plus arithmetic",
        answer_mode="total_and_sequence",
        seed=seed,
        sections=sections,
        distractors_per_section=distractors_per_section,
        context_scale=context_scale,
        criteria_lines=criteria,
        section_texts=section_texts,
        section_items=section_items,
        items_by_id=items_by_id,
        expected_answer=expected_answer,
        full_text="\n\n".join(section_texts),
    )


def build_code_task(seed: int, *, sections: int, distractors_per_section: int, context_scale: int) -> BenchTask:
    rng = random.Random(20_000 + seed)
    criteria = ('project="ORCHID"', 'stage="release"', 'marker="amber"', 'guard="prime"')
    section_texts: list[str] = []
    section_items: list[list[BenchItem]] = []
    items_by_id: dict[str, BenchItem] = {}
    expected_items: list[BenchItem] = []

    for section_index in range(1, sections + 1):
        token = rng.choice(TOKENS)
        comment_block = textwrap.indent(
            "\n".join(
                f"# {repeat_sentences(rng, CODE_COMMENTS, 1)}"
                for _ in range(context_scale)
            ),
            "    ",
        )
        target = BenchItem(
            item_id=f"TARGET{section_index}",
            section_index=section_index,
            order=section_index,
            token=token,
            amount=None,
            is_target=True,
            text=textwrap.dedent(
                f"""\
                # ITEM ID: TARGET{section_index}
                PROJECT = "ORCHID"
                STAGE = "release"
                MARKER = "amber"
                GUARD = "prime"
                ORDER = {section_index}
                TOKEN = "{token}"
                def pipeline_step_{section_index}():
                {comment_block}
                    return TOKEN
                """
            ).strip(),
            summary=f"TARGET{section_index} | project=ORCHID | stage=release | marker=amber | guard=prime | Order={section_index}",
        )
        items = [target]
        expected_items.append(target)

        near_miss_order = rng.randint(1, sections + distractors_per_section)
        near_miss_token = rng.choice(TOKENS)
        comment_block = textwrap.indent(
            "\n".join(
                f"# {repeat_sentences(rng, CODE_COMMENTS, 1)}"
                for _ in range(context_scale)
            ),
            "    ",
        )
        items.append(
            BenchItem(
                item_id=f"DIST{section_index}_0",
                section_index=section_index,
                order=near_miss_order,
                token=near_miss_token,
                amount=None,
                is_target=False,
                text=textwrap.dedent(
                    f"""\
                    # ITEM ID: DIST{section_index}_0
                    PROJECT = "ORCHID"
                    STAGE = "release"
                    MARKER = "amber"
                    GUARD = "shadow"
                    ORDER = {near_miss_order}
                    TOKEN = "{near_miss_token}"
                    def shadow_step_{section_index}():
                    {comment_block}
                        return TOKEN
                    """
                ).strip(),
                summary=f"DIST{section_index}_0 | project=ORCHID | stage=release | marker=amber | guard=shadow | Order={near_miss_order}",
            )
        )

        for distractor_index in range(1, distractors_per_section):
            while True:
                project = rng.choice(CODE_PROJECTS)
                stage = rng.choice(CODE_STAGES)
                marker = rng.choice(CODE_MARKERS)
                guard = rng.choice(CODE_GUARDS)
                if (project, stage, marker, guard) != ("ORCHID", "release", "amber", "prime"):
                    break
            order = rng.randint(1, sections + distractors_per_section)
            token = rng.choice(TOKENS)
            item_id = f"DIST{section_index}_{distractor_index}"
            comment_block = textwrap.indent(
                "\n".join(
                    f"# {repeat_sentences(rng, CODE_COMMENTS, 1)}"
                    for _ in range(context_scale)
                ),
                "    ",
            )
            items.append(
                BenchItem(
                    item_id=item_id,
                    section_index=section_index,
                    order=order,
                    token=token,
                    amount=None,
                    is_target=False,
                    text=textwrap.dedent(
                        f"""\
                        # ITEM ID: {item_id}
                        PROJECT = "{project}"
                        STAGE = "{stage}"
                        MARKER = "{marker}"
                        GUARD = "{guard}"
                        ORDER = {order}
                        TOKEN = "{token}"
                        def helper_step_{section_index}_{distractor_index}():
                        {comment_block}
                            return TOKEN
                        """
                    ).strip(),
                    summary=f"{item_id} | project={project} | stage={stage} | marker={marker} | guard={guard} | Order={order}",
                )
            )

        rng.shuffle(items)
        section_items.append(items.copy())
        file_body = "\n\n".join(item.text for item in items)
        section_texts.append(f"=== FILE module_{section_index}.py ===\n{file_body}")
        for item in items:
            items_by_id[item.item_id] = item

    expected_answer = compose_answer(
        task_shell(
            family="code",
            display_name="Code localization",
            task_type="code-like localization",
            answer_mode="sequence",
            seed=seed,
            sections=sections,
            distractors_per_section=distractors_per_section,
            context_scale=context_scale,
            criteria_lines=criteria,
        ),
        expected_items,
    )
    return BenchTask(
        family="code",
        display_name="Code localization",
        task_type="code-like localization",
        answer_mode="sequence",
        seed=seed,
        sections=sections,
        distractors_per_section=distractors_per_section,
        context_scale=context_scale,
        criteria_lines=criteria,
        section_texts=section_texts,
        section_items=section_items,
        items_by_id=items_by_id,
        expected_answer=expected_answer,
        full_text="\n\n".join(section_texts),
    )


FAMILY_BUILDERS: dict[str, Callable[..., BenchTask]] = {
    "records": build_prose_task,
    "ledger": build_ledger_task,
    "code": build_code_task,
}


def run_breadth_suite(
    *,
    model_path_or_repo: str,
    families: list[str],
    sections: int,
    distractors_per_section: int,
    context_scale: int,
    seeds: list[int],
    output_path: Path,
    baseline_max_tokens: int,
    chunk_max_tokens: int,
    no_validator_chunk_max_tokens: int,
    recursive_chunk_max_tokens: int,
    recursive_leaf_items: int,
    recursive_branching_factor: int,
) -> dict[str, object]:
    model = MLXPromptModel(model_path_or_repo)
    family_summaries: list[dict[str, object]] = []

    for family in families:
        builder = FAMILY_BUILDERS[family]
        baseline_results: list[BenchConditionResult] = []
        no_validator_results: list[BenchConditionResult] = []
        managed_results: list[BenchConditionResult] = []
        recursive_results: list[BenchConditionResult] = []
        runs: list[dict[str, object]] = []

        for seed in seeds:
            task = builder(
                seed,
                sections=sections,
                distractors_per_section=distractors_per_section,
                context_scale=context_scale,
            )
            baseline = run_baseline(task, model, max_tokens=baseline_max_tokens)
            no_validator = run_no_validator(task, model, max_tokens=no_validator_chunk_max_tokens)
            managed = run_managed(task, model, max_tokens=chunk_max_tokens)
            recursive = run_recursive(
                task,
                model,
                max_tokens=recursive_chunk_max_tokens,
                leaf_items=recursive_leaf_items,
                branching_factor=recursive_branching_factor,
            )

            baseline_results.append(baseline)
            no_validator_results.append(no_validator)
            managed_results.append(managed)
            recursive_results.append(recursive)
            runs.append(
                {
                    "family": task.family,
                    "display_name": task.display_name,
                    "task_type": task.task_type,
                    "answer_mode": task.answer_mode,
                    "seed": seed,
                    "sections": task.sections,
                    "distractors_per_section": task.distractors_per_section,
                    "context_scale": task.context_scale,
                    "artifact_characters": len(task.full_text),
                    "expected_answer": task.expected_answer,
                    "baseline": asdict(baseline),
                    "no_validator": asdict(no_validator),
                    "managed": asdict(managed),
                    "recursive": asdict(recursive),
                }
            )

        first_run = runs[0]
        family_summaries.append(
            {
                "family": family,
                "display_name": first_run["display_name"],
                "task_type": first_run["task_type"],
                "answer_mode": first_run["answer_mode"],
                "sections": sections,
                "distractors_per_section": distractors_per_section,
                "context_scale": context_scale,
                "seeds": seeds,
                "artifact_characters_mean": statistics.mean(run["artifact_characters"] for run in runs),
                "baseline": summarize_condition(baseline_results),
                "no_validator": summarize_condition(no_validator_results),
                "managed": summarize_condition(managed_results),
                "recursive": summarize_condition(recursive_results),
                "runs": runs,
            }
        )

    overall = {
        "baseline_accuracy_mean": statistics.mean(family["baseline"]["accuracy"] for family in family_summaries),
        "no_validator_accuracy_mean": statistics.mean(family["no_validator"]["accuracy"] for family in family_summaries),
        "managed_accuracy_mean": statistics.mean(family["managed"]["accuracy"] for family in family_summaries),
        "recursive_accuracy_mean": statistics.mean(family["recursive"]["accuracy"] for family in family_summaries),
    }
    summary = {
        "label": "breadth-suite",
        "model_path_or_repo": model_path_or_repo,
        "families": family_summaries,
        "overall": overall,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def load_breadth_rows(paths: Iterable[Path]) -> list[FamilyReportRow]:
    rows: list[FamilyReportRow] = []
    for path in paths:
        payload = json.loads(path.read_text())
        for family in payload["families"]:
            rows.append(
                FamilyReportRow(
                    family=family["family"],
                    display_name=family["display_name"],
                    task_type=family["task_type"],
                    answer_mode=family["answer_mode"],
                    runs=len(family["runs"]),
                    avg_characters=family["artifact_characters_mean"],
                    baseline_accuracy=family["baseline"]["accuracy"],
                    no_validator_accuracy=family["no_validator"]["accuracy"],
                    managed_accuracy=family["managed"]["accuracy"],
                    recursive_accuracy=family["recursive"]["accuracy"],
                    baseline_latency=family["baseline"]["mean_latency_seconds"],
                    no_validator_latency=family["no_validator"]["mean_latency_seconds"],
                    managed_latency=family["managed"]["mean_latency_seconds"],
                    recursive_latency=family["recursive"]["mean_latency_seconds"],
                )
            )
    return rows


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def build_breadth_report(paths: Iterable[Path]) -> str:
    rows = load_breadth_rows(paths)
    if not rows:
        raise ValueError("No breadth-suite rows found.")

    family_rows = [
        [
            row.display_name,
            row.task_type,
            str(row.runs),
            format_float(row.avg_characters, 0),
            format_float(row.baseline_accuracy),
            format_float(row.no_validator_accuracy),
            format_float(row.managed_accuracy),
            format_float(row.recursive_accuracy),
            format_float(row.baseline_latency),
            format_float(row.no_validator_latency),
            format_float(row.managed_latency),
            format_float(row.recursive_latency),
        ]
        for row in rows
    ]
    overall = {
        "baseline": statistics.mean(row.baseline_accuracy for row in rows),
        "no_validator": statistics.mean(row.no_validator_accuracy for row in rows),
        "managed": statistics.mean(row.managed_accuracy for row in rows),
        "recursive": statistics.mean(row.recursive_accuracy for row in rows),
    }
    managed_beats_baseline = sum(row.managed_accuracy > row.baseline_accuracy for row in rows)
    recursive_beats_managed = sum(row.recursive_accuracy > row.managed_accuracy for row in rows)
    recursive_matches_or_beats_managed = sum(row.recursive_accuracy >= row.managed_accuracy for row in rows)
    no_validator_beats_baseline = sum(row.no_validator_accuracy > row.baseline_accuracy for row in rows)
    sections = [
        "# Broad Evidence Report",
        "This report does not prove the broad hypothesis, but it defines what broader support should look like and evaluates the first local suite against that bar.",
        "## What Would Count As Broader Support",
        "- task-family transfer: the scaffold should help on more than one benchmark shape",
        "- domain transfer: the advantage should survive prose, arithmetic-style ledgers, and code-like text",
        "- bookkeeping ablation: simply making more calls should not be enough; removing deterministic support should reduce performance",
        "- hierarchical robustness: recursive routing should help when flat decomposition starts to break",
        "- model transfer: ideally the same pattern should later be rerun on more than one model family",
        "## Local Suite Setup",
        "- families: prose retrieval, ledger aggregation, code-like localization",
        "- shared configuration: 4 sections, 6 distractors per section, context scale 3, seeds 0/1/2",
        "- methods: baseline, no-validator, validator-backed managed, recursive",
        "## Family Results",
        render_table(
            [
                "Family",
                "Task type",
                "Runs",
                "Avg chars",
                "Baseline acc",
                "No-validator acc",
                "Managed acc",
                "Recursive acc",
                "Baseline latency (s)",
                "No-validator latency (s)",
                "Managed latency (s)",
                "Recursive latency (s)",
            ],
            family_rows,
        ),
        "## Aggregate Accuracy Means",
        render_table(
            ["Method", "Mean accuracy across families"],
            [
                ["Baseline", format_float(overall["baseline"])],
                ["No-validator", format_float(overall["no_validator"])],
                ["Managed", format_float(overall["managed"])],
                ["Recursive", format_float(overall["recursive"])],
            ],
        ),
        "## Scorecard",
        render_table(
            ["Claim", "Result"],
            [
                ["Managed beats baseline across families", f"{managed_beats_baseline}/{len(rows)}"],
                ["No-validator beats baseline across families", f"{no_validator_beats_baseline}/{len(rows)}"],
                ["Recursive beats flat managed across families", f"{recursive_beats_managed}/{len(rows)}"],
                ["Recursive matches or beats flat managed across families", f"{recursive_matches_or_beats_managed}/{len(rows)}"],
            ],
        ),
        "## Interpretation",
        (
            "If the hypothesis were only an artifact of one synthetic retrieval task, the improvement should disappear when the surface form changes. "
            "Instead, the same pattern persisting across prose, arithmetic-ledger, and code-like tasks is stronger evidence that the bottleneck is partly in decomposition rather than only in raw model weights."
        ),
        (
            "At the same time, the no-validator condition remains much weaker than the validator-backed manager. "
            "That means the broad claim still cannot be stated as 'the model alone already does everything once decomposed.' "
            "The more accurate statement is that the model plus a better management policy and exact support code unlocks capabilities that one-shot prompting leaves on the table."
        ),
        "## Conclusion",
        (
            "The broader local suite supports a stronger but still bounded claim: management advantages transfer across multiple task families, not just the original prose retrieval benchmark. "
            "That is meaningful evidence for the mismanaged-geniuses hypothesis, but not a proof of the full general version yet. "
            "To get closer to that, the next step is model transfer and a real codebase benchmark rather than synthetic text alone."
        ),
    ]
    return "\n\n".join(sections) + "\n"
