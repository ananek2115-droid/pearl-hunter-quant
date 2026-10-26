"""Local Trail-code A/B measurement: no network, agent hooks or model execution.

Records must come from matched *real* agent runs. Synthetic test fixtures do
not establish performance. The benchmark never chooses a production agent.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from statistics import median

COMMIT = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
VARIANTS = {"baseline", "trail"}


def _record(item):
    if not isinstance(item, dict) or not isinstance(item.get("task_id"), str) or not ID.fullmatch(item["task_id"]):
        raise ValueError("Invalid task ID")
    if item.get("variant") not in VARIANTS:
        raise ValueError("variant must be baseline or trail")
    if not isinstance(item.get("starting_commit"), str) or not COMMIT.fullmatch(item["starting_commit"]):
        raise ValueError("Full SHA-1 starting commit required")
    if not isinstance(item.get("prompt_sha256"), str) or not HASH.fullmatch(item["prompt_sha256"]):
        raise ValueError("Exact prompt checksum required")
    if item.get("measurement_source") not in {"agent_usage_log", "manual_clock_and_log"}:
        raise ValueError("Measurement source required")
    if type(item.get("tests_passed")) is not bool:
        raise ValueError("Explicit regression result required")
    for key in ("elapsed_seconds", "tool_calls", "uncached_input_tokens"):
        value = item.get(key)
        if key != "elapsed_seconds" and type(value) is not int:
            raise ValueError("Nonnegative integer required for " + key)
        if key == "elapsed_seconds" and type(value) not in (float, int):
            raise ValueError("Numeric time required")
        if not math.isfinite(value) or value < (0.001 if key == "elapsed_seconds" else 0):
            raise ValueError("Invalid " + key)
    return item


def evaluate(document):
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported Trail pilot schema")
    if document.get("contains_synthetic_measurements") is True:
        raise ValueError("Never report synthetic measurements as real")
    items = document.get("observations")
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError("Invalid observations")
    grouped = {}
    for item in items:
        item = _record(item)
        key = (item["task_id"], item["variant"])
        if key in grouped:
            raise ValueError("Repeated task/variant")
        grouped[key] = item
    tasks = sorted({task for task, _ in grouped})
    pairs = []
    incomplete = []
    failed = []
    for task in tasks:
        baseline, trail = grouped.get((task, "baseline")), grouped.get((task, "trail"))
        if baseline is None or trail is None:
            incomplete.append(task)
            continue
        if (baseline["starting_commit"] != trail["starting_commit"]
                or baseline["prompt_sha256"] != trail["prompt_sha256"]):
            raise ValueError("A/B pairs must have the same starting commit and exact prompt")
        if not (baseline["tests_passed"] and trail["tests_passed"]):
            failed.append(task)
            continue
        pairs.append((baseline, trail))
    result = {
        "mode": "manual_matched_A_B",
        "observations": len(items),
        "completed_valid_pairs": len(pairs),
        "incomplete_pairs": incomplete,
        "regression_failed_pairs": failed,
        "real_trail_runtime_executed_by_this_script": False,
        "status": "NO_DATA",
        "metrics": None,
        "claim": "No proven speedup. Data are observational and may be confounded by agent variance.",
    }
    if not pairs:
        return result
    fields = ("elapsed_seconds", "tool_calls", "uncached_input_tokens")
    stats = {}
    for field in fields:
        base = [b[field] for b, _ in pairs]
        alt = [t[field] for _, t in pairs]
        # Median paired reduction (vs median of marginal values) guards task-mix effects.
        paired_pct = [(b[field] - t[field]) / b[field] * 100 for b, t in pairs if b[field] > 0]
        stats[field] = {
            "baseline_median": round(median(base), 2),
            "trail_median": round(median(alt), 2),
            "median_paired_reduction_pct": round(median(paired_pct), 2) if len(paired_pct) == len(pairs) else None,
        }
    result["metrics"] = stats
    result["status"] = "DESCRIPTIVE_ONLY" if len(pairs) >= 5 and not incomplete and not failed else "INSUFFICIENT_COMPARABLE_TASKS"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = evaluate(json.loads(Path(args.observations).read_text(encoding="utf-8")))
    report = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(report)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
