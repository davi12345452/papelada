"""Aggregate run files into markdown tables per model, document type and degradation level."""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

COLUMNS = [
    "model", "doc type", "level", "docs", "accuracy", "accuracy (lenient)", "hallucination",
    "misattribution", "omission", "wrong", "traps", "table cells", "extra rows", "schema valid",
    "errors", "cost/doc (USD)", "p50 latency (s)",
]


def _rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.1%}" if denominator else "-"


def _is_trap(record: dict, path: str) -> bool:
    return path in record.get("traps", [])


def summarize(records: list[dict]) -> dict:
    scored = [(r, f) for r in records for f in r["fields"] if f["bucket"] != "extra_row"]
    fields = [f for _, f in scored]
    gold_null = [f for f in fields if f["gold"] is None]
    gold_value = [f for f in fields if f["gold"] is not None]
    trap_fields = [f for r, f in scored if _is_trap(r, f["path"])]
    table_cells = [f for f in fields if "[" in f["path"]]
    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    count = lambda items, bucket: sum(f["bucket"] == bucket for f in items)  # noqa: E731
    return {
        "docs": len(records),
        "accuracy": _rate(count(fields, "correct"), len(fields)),
        "accuracy (lenient)": _rate(sum(f["lenient_correct"] for f in fields), len(fields)),
        # Rates over the fields where each kind of error is possible.
        "hallucination": _rate(count(gold_null, "hallucination"), len(gold_null)),
        "misattribution": _rate(count(fields, "misattribution"), len(fields)),
        "omission": _rate(count(gold_value, "omission"), len(gold_value)),
        "wrong": _rate(count(gold_value, "wrong"), len(gold_value)),
        "traps": _rate(count(trap_fields, "correct"), len(trap_fields)),
        "table cells": _rate(count(table_cells, "correct"), len(table_cells)),
        "extra rows": sum(f["bucket"] == "extra_row" for r in records for f in r["fields"]),
        "schema valid": _rate(sum(r["schema_valid"] for r in records), len(records)),
        "errors": sum(r["error"] is not None for r in records),
        "cost/doc (USD)": f"{statistics.mean(costs):.5f}" if costs else "-",
        "p50 latency (s)": f"{statistics.median(r['latency_s'] for r in records):.1f}",
    }


def _load(paths: list[Path]) -> list[dict]:
    return [json.loads(line) for path in paths for line in path.read_text().splitlines()]


def report(paths: list[Path], by_level: bool = True) -> str:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for record in _load(paths):
        model, doc_type = record["model"], record["doc_type"]
        if by_level:
            groups[(model, doc_type, record["level"])].append(record)
        groups[(model, doc_type, "all")].append(record)
        groups[(model, "all", "all")].append(record)

    rows = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for (model, doc_type, level), records in sorted(groups.items()):
        summary = summarize(records)
        rows.append("| " + " | ".join([model, doc_type, level] + [str(summary[c]) for c in COLUMNS[3:]]) + " |")
    return "\n".join(rows)


def worst_fields(paths: list[Path], top: int = 12) -> str:
    """Which fields fail most, and how. Table rows are folded: items[3].total -> items[].total."""
    buckets = ["correct", "wrong", "omission", "hallucination", "misattribution"]
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in _load(paths):
        for field in record["fields"]:
            if field["bucket"] != "extra_row":
                counts[re.sub(r"\[\d+\]", "[]", field["path"])][field["bucket"]] += 1
    ranked = sorted(counts.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if k != "correct"))
    rows = ["| field | " + " | ".join(buckets) + " |", "|---" * (len(buckets) + 1) + "|"]
    for path, c in ranked[:top]:
        rows.append(f"| {path} | " + " | ".join(str(c[b]) for b in buckets) + " |")
    return "\n".join(rows)
