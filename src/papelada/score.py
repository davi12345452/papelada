"""Field-level scoring.

Each gold leaf falls into one bucket:

    gold value, same value       -> correct
    gold value, different value  -> wrong
    gold value, null/missing     -> omission
    gold null,  null/missing     -> correct
    gold null,  any value        -> hallucination

Values are normalized by field kind before comparison (see NORMALIZERS).
"""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

# --- Normalization -----------------------------------------------------------


def _text(value) -> str:
    text = unicodedata.normalize("NFC", str(value))
    return " ".join(text.split()).casefold()


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _key(value) -> str:
    """Identifiers, documents, accounts, PIX keys: ignore punctuation and spacing."""
    return re.sub(r"[\s.\-/()]", "", str(value)).casefold()


def _code(value) -> str:
    """Case-sensitive codes such as the E2E ID."""
    return re.sub(r"\s", "", str(value))


def _money(value) -> str:
    text = re.sub(r"[^\d.,\-]", "", str(value))
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):  # 1.234,56
            text = text.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1 or re.search(r"\.\d{3}$", text):  # 1.234 or 1.234.567
        text = text.replace(".", "")
    try:
        return str(Decimal(text).quantize(Decimal("0.01")))
    except InvalidOperation:
        return _text(value)


def _datetime(value) -> str:
    digits = re.findall(r"\d+", str(value))
    if len(digits) >= 5 and len(digits[0]) == 4:  # 2026-10-28T14:03[:12]
        parts = digits[:6]
        return "-".join(parts[:3]) + "T" + ":".join(p.zfill(2) for p in parts[3:])
    return _text(value)


NORMALIZERS = {"text": _text, "key": _key, "code": _code, "money": _money, "datetime": _datetime}


def kind_for(path: str, kinds: dict[str, str]) -> str:
    if path in kinds:
        return kinds[path]
    last = path.rsplit(".", 1)[-1]
    return kinds.get(f"*.{last}", "text")


def _same(gold, pred, kind: str) -> tuple[bool, bool]:
    """(strict match, lenient match). Lenient also ignores accents."""
    g, p = NORMALIZERS[kind](gold), NORMALIZERS[kind](pred)
    if kind == "datetime":
        # Precision follows the document: if gold has no seconds, predicted seconds are ignored.
        p = p[: len(g)]
    strict = g == p
    return strict, strict or _strip_accents(g) == _strip_accents(p)


# --- Scoring -----------------------------------------------------------------


def leaves(obj, prefix: str = "") -> dict[str, object]:
    """Flatten nested dicts into dotted paths. Lists are not used by the v0 PIX schema yet."""
    out: dict[str, object] = {}
    for key, value in obj.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(leaves(value, f"{path}."))
        else:
            out[path] = value
    return out


def lookup(obj, path: str):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in {"", "null", "N/A", "-"})


def score_fields(gold: dict, pred: dict | None, kinds: dict[str, str]) -> list[dict]:
    """Score every gold leaf. An unparseable prediction is scored as an empty one."""
    pred = pred or {}
    results = []
    for path, gold_value in leaves(gold).items():
        pred_value = lookup(pred, path)
        lenient = None
        if gold_value is None:
            bucket = "correct" if _is_empty(pred_value) else "hallucination"
        elif _is_empty(pred_value):
            bucket = "omission"
        else:
            strict, lenient = _same(gold_value, pred_value, kind_for(path, kinds))
            bucket = "correct" if strict else "wrong"
        results.append({
            "path": path,
            "bucket": bucket,
            "lenient_correct": bucket == "correct" or bool(lenient),
            "gold": gold_value,
            "pred": pred_value,
        })
    return results


def parse_json(text: str | None) -> dict | None:
    """Extract the JSON object from a model reply, tolerating code fences and chatter."""
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
