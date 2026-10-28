"""Run a model over generated samples and write one JSONL record per (sample, level)."""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from papelada.doctypes import DOC_TYPES, load_schema
from papelada.models import complete
from papelada.score import parse_json, score_fields

SYSTEM = (
    "You extract structured data from images of Brazilian documents. "
    "Reply with a single JSON object that follows the given JSON Schema, and nothing else. "
    "Transcribe only what is printed in the document. "
    "If a field is not present in the document, use null. Never guess or infer a value that is not printed."
)

PROMPT_VERSION = "v0"


def prompt_for(schema: dict) -> str:
    return "Extract the data from this document.\n\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)


def evaluate(text: str | None, gold: dict, meta: dict) -> dict:
    """Score a raw model reply. Kept separate so saved runs can be rescored without new calls."""
    doc_type = meta["doc_type"]
    schema = load_schema(doc_type)
    pred = parse_json(text)
    schema_errors = [e.message[:200] for e in Draft202012Validator(schema).iter_errors(pred)][:5] if pred else []
    return {
        "valid_json": pred is not None,
        "schema_valid": pred is not None and not schema_errors,
        "schema_errors": schema_errors,
        "traps": meta.get("traps", []),
        "fields": score_fields(gold, pred, DOC_TYPES[doc_type].FIELD_KINDS, meta.get("printed_text")),
    }


def rescore(path: Path, data_dir: Path) -> None:
    """Recompute scores of a run file in place from the stored raw replies."""
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for record in records:
        sample_dir = data_dir / record["doc_type"] / record["sample"]
        gold = json.loads((sample_dir / "gold.json").read_text())
        meta = json.loads((sample_dir / "meta.json").read_text())
        record.update(evaluate(record["raw"], gold, meta))
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    tmp.replace(path)


def run(model: str, data_dir: Path, levels: list[str], out: Path, limit: int | None = None, workers: int = 2,
        doc_types: list[str] | None = None, resume: Path | None = None) -> Path:
    tasks = []
    for gold_path in sorted(data_dir.glob("*/*/gold.json"))[:limit]:
        meta = json.loads((gold_path.parent / "meta.json").read_text())
        if doc_types and meta["doc_type"] not in doc_types:
            continue
        for level in levels:
            if level in meta["images"]:
                tasks.append((gold_path.parent, meta, level))
    if not tasks:
        raise SystemExit(f"No samples found under {data_dir}")

    if resume:
        # Keep the records that got a reply; drop failed calls (e.g. out of credits) and redo only those.
        kept = [r for r in map(json.loads, resume.read_text().splitlines()) if r["error"] is None]
        if any(r["model"] != model for r in kept):
            raise SystemExit(f"{resume} holds another model's run")
        resume.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
        done = {(r["sample"], r["level"]) for r in kept}
        tasks = [t for t in tasks if (t[0].name, t[2]) not in done]
        out_file = resume
        print(f"resuming {resume}: {len(kept)} kept, {len(tasks)} to run", flush=True)
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        out_file = out / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}-{stamp}.jsonl"
    lock = threading.Lock()

    def one(task) -> None:
        sample_dir, meta, level = task
        doc_type = meta["doc_type"]
        schema = load_schema(doc_type)
        gold = json.loads((sample_dir / "gold.json").read_text())

        completion = complete(model, SYSTEM, prompt_for(schema), sample_dir / meta["images"][level])
        record = {
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "doc_type": doc_type,
            "sample": sample_dir.name,
            "layout": meta["layout"],
            "level": level,
            "latency_s": round(completion.latency_s, 3),
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "cost_usd": completion.cost_usd,
            "error": completion.error,
            "raw": completion.text,
            **evaluate(completion.text, gold, meta),
        }
        with lock:
            with out_file.open("a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            buckets = [field["bucket"] for field in record["fields"]]
            status = completion.error or f"correct {buckets.count('correct')}/{len(buckets)}, hallucinated {buckets.count('hallucination')}"
            print(f"{sample_dir.name} {level}: {status}", flush=True)

    failures = []

    def safe(task) -> None:
        # One bad task must not take down a run that has already paid for other calls.
        try:
            one(task)
        except Exception as e:  # noqa: BLE001
            failures.append(task)
            print(f"{task[0].name} {task[2]}: FAILED {type(e).__name__}: {e}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(safe, tasks))
    if failures:
        print(f"{len(failures)} of {len(tasks)} tasks failed and are missing from {out_file}", flush=True)
    return out_file
