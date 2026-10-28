"""Aggregate run files into markdown tables per model, document type and degradation level."""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

COLUMNS = [
    "model", "doc type", "level", "docs", "accuracy", "accuracy (lenient)", "hallucination",
    "misattribution", "substitution", "omission", "wrong", "traps", "table cells", "extra rows", "schema valid",
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
        "substitution": _rate(count(gold_value, "substitution"), len(gold_value)),
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
    buckets = ["correct", "wrong", "substitution", "omission", "hallucination", "misattribution"]
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


def _accuracy(records: list[dict]) -> float | None:
    fields = [f for r in records for f in r["fields"] if f["bucket"] != "extra_row"]
    return sum(f["bucket"] == "correct" for f in fields) / len(fields) if fields else None


def leaderboard(paths: list[Path], samples: set[str] | None = None) -> str:
    """One row per model: mean accuracy over document types, per-level accuracy, hallucination and cost.

    The date is taken from the run file name, so a model added later shows when it was tested.
    `samples` restricts every model to the same documents, e.g. those all models were scored on.
    """
    by_model: dict[str, list[dict]] = defaultdict(list)
    tested: dict[str, str] = {}
    for path in paths:
        records = _load([path])
        stamp = re.search(r"-(\d{4})(\d{2})(\d{2})-\d{6}", path.name)
        for record in records:
            if samples is not None and record["sample"] not in samples:
                continue
            by_model[record["model"]].append(record)
            if stamp:
                tested[record["model"]] = "-".join(stamp.groups())

    def pct(value: float | None) -> str:
        return f"{value:.1%}".rstrip("%") if value is not None else "-"

    rows = []
    for model, records in by_model.items():
        cells, type_scores = [], []
        for doc_type in ("pix_receipt", "danfe", "voting_bulletin"):
            of_type = [r for r in records if r["doc_type"] == doc_type]
            type_scores.append(_accuracy(of_type))
            cells.append(" / ".join(pct(_accuracy([r for r in of_type if r["level"] == lvl])) for lvl in ("L0", "L1", "L2")))
        scores = [s for s in type_scores if s is not None]
        mean = sum(scores) / len(scores) if scores else 0.0
        summary = summarize(records)
        name = model.split(":", 1)[-1]
        rows.append((mean, f"| `{name}` | **{pct(mean)}** | " + " | ".join(cells)
                     + f" | {summary['hallucination']} | {float(summary['cost/doc (USD)']):.4f} | {tested.get(model, '-')} |"))

    header = [
        "| Model | Score | PIX L0 / L1 / L2 | DANFE L0 / L1 / L2 | Bulletin L0 / L1 / L2 | Hallucination | US$/doc | Tested |",
        "|---|---|---|---|---|---|---|---|",
    ]
    return "\n".join(header + [row for _, row in sorted(rows, key=lambda r: -r[0])])
