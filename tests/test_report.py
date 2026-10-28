import json

from papelada.report import leaderboard


def _record(model, doc_type, level, buckets):
    return {
        "model": model, "doc_type": doc_type, "level": level, "cost_usd": 0.001, "latency_s": 1.0,
        "error": None, "schema_valid": True, "traps": [],
        "fields": [{"path": f"f{i}", "gold": "x", "bucket": b, "lenient_correct": b == "correct"}
                   for i, b in enumerate(buckets)],
    }


def test_leaderboard_ranks_by_mean_over_doc_types(tmp_path):
    good = [_record("p:good", t, lvl, ["correct"] * 4) for t in ("pix_receipt", "danfe") for lvl in ("L0", "L1", "L2")]
    bad = [_record("p:bad", t, lvl, ["correct", "wrong"]) for t in ("pix_receipt", "danfe") for lvl in ("L0", "L1", "L2")]
    for name, records in (("good-20261101-120000.jsonl", good), ("bad-20261028-120000.jsonl", bad)):
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in records))

    rows = leaderboard(sorted(tmp_path.glob("*.jsonl"))).splitlines()[2:]
    assert rows[0].startswith("| `good` | **100.0** | 100.0 / 100.0 / 100.0")
    assert rows[0].endswith("| 2026-11-01 |")
    assert rows[1].startswith("| `bad` | **50.0** |")
    assert "| - / - / - |" in rows[1]
