"""Aggregate run files into a markdown table per model and degradation level."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

COLUMNS = [
    "model", "level", "docs", "accuracy", "accuracy (lenient)", "hallucination",
    "omission", "wrong", "schema valid", "errors", "cost/doc (USD)", "p50 latency (s)",
]


def _rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.1%}" if denominator else "-"


def summarize(records: list[dict]) -> dict:
    fields = [f for r in records for f in r["fields"]]
    gold_null = [f for f in fields if f["gold"] is None]
    gold_value = [f for f in fields if f["gold"] is not None]
    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    return {
        "docs": len(records),
        "accuracy": _rate(sum(f["bucket"] == "correct" for f in fields), len(fields)),
        "accuracy (lenient)": _rate(sum(f["lenient_correct"] for f in fields), len(fields)),
        # Rates over the fields where each kind of error is possible.
        "hallucination": _rate(sum(f["bucket"] == "hallucination" for f in gold_null), len(gold_null)),
        "omission": _rate(sum(f["bucket"] == "omission" for f in gold_value), len(gold_value)),
        "wrong": _rate(sum(f["bucket"] == "wrong" for f in gold_value), len(gold_value)),
        "schema valid": _rate(sum(r["schema_valid"] for r in records), len(records)),
        "errors": sum(r["error"] is not None for r in records),
        "cost/doc (USD)": f"{statistics.mean(costs):.5f}" if costs else "-",
        "p50 latency (s)": f"{statistics.median(r['latency_s'] for r in records):.1f}",
    }


def report(paths: list[Path]) -> str:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for path in paths:
        for line in path.read_text().splitlines():
            record = json.loads(line)
            groups[(record["model"], record["level"])].append(record)
            groups[(record["model"], "all")].append(record)

    rows = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for (model, level), records in sorted(groups.items()):
        summary = summarize(records)
        rows.append("| " + " | ".join([model, level] + [str(summary[c]) for c in COLUMNS[2:]]) + " |")
    return "\n".join(rows)


def worst_fields(paths: list[Path], top: int = 10) -> str:
    """Which fields fail most, and how. Useful for reading a single run."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in paths:
        for line in path.read_text().splitlines():
            for field in json.loads(line)["fields"]:
                counts[field["path"]][field["bucket"]] += 1
    ranked = sorted(counts.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if k != "correct"))
    rows = ["| field | correct | wrong | omission | hallucination |", "|---|---|---|---|---|"]
    for path, c in ranked[:top]:
        rows.append(f"| {path} | {c['correct']} | {c['wrong']} | {c['omission']} | {c['hallucination']} |")
    return "\n".join(rows)
