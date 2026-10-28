"""Field-level scoring.

Each gold leaf falls into one bucket:

    gold value, same value                      -> correct
    gold value, null/missing                    -> omission
    gold value, other text printed on the page  -> misattribution
    gold value, anything else                   -> wrong
    gold null,  null/missing                    -> correct
    gold null,  text printed on the page        -> misattribution
    gold null,  anything else                   -> hallucination

"Misattribution" separates reading the wrong part of the page (a footer put in the
description, the payer's CPF in the payee's field) from inventing a value. It needs
the document's printed text, which the generator records in meta.json.

Lists (table rows) are aligned by position. Predicted rows beyond the gold rows are
reported once each as "extra_row".

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


def _decimal(value) -> Decimal | None:
    """Parse Brazilian or international number formatting: '1.234,56', '1,234.56', '1234.56'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
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
        return Decimal(text)
    except InvalidOperation:
        return None


def _money(value) -> str:
    number = _decimal(value)
    return str(number.quantize(Decimal("0.01"))) if number is not None else _text(value)


def _number(value) -> str:
    """Quantities and document numbers: '000.012.345' == '12345', '2,0000' == '2'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = Decimal(str(value))
    else:
        text = re.sub(r"[^\d.,\-]", "", str(value))
        if "," in text:  # Brazilian formatting: 1.234,5678
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") > 1:  # dotted document number: 000.012.345
            text = text.replace(".", "")
        # A single dot is a decimal point, as the schemas ask: 12.345 kg is not 12345.
        try:
            number = Decimal(text)
        except InvalidOperation:
            return _text(value)
    return format(number.normalize(), "f")


def _datetime(value) -> str:
    digits = re.findall(r"\d+", str(value))
    if len(digits) >= 3 and len(digits[0]) == 4:  # 2026-10-28[T14:03[:12]]
        parts = digits[:6]
        date = "-".join(p.zfill(2) for p in parts[:3])
        return date + ("T" + ":".join(p.zfill(2) for p in parts[3:]) if len(parts) > 3 else "")
    return _text(value)


NORMALIZERS = {
    "text": _text, "key": _key, "code": _code, "money": _money, "number": _number, "datetime": _datetime,
}


def kind_for(path: str, kinds: dict[str, str]) -> str:
    if path in kinds:
        return kinds[path]
    last = re.sub(r"\[\d+\]", "", path).rsplit(".", 1)[-1]
    return kinds.get(f"*.{last}", "text")


def _same(gold, pred, kind: str) -> tuple[bool, bool]:
    """(strict match, lenient match). Lenient also ignores accents."""
    g, p = NORMALIZERS[kind](gold), NORMALIZERS[kind](pred)
    if kind == "datetime":
        # Precision follows the document: if gold has no seconds, predicted seconds are ignored.
        p = p[: len(g)]
    strict = g == p
    return strict, strict or _strip_accents(g) == _strip_accents(p)


class _Printed:
    """Everything printed on the page, normalized lazily per field kind."""

    def __init__(self, texts: list[str]):
        self.texts = texts
        self.cache: dict[str, set[str]] = {}

    def contains(self, value, kind: str) -> bool:
        if not self.texts or isinstance(value, (dict, list)):
            return False
        for k in {kind, "text"}:
            if k not in self.cache:
                self.cache[k] = {_strip_accents(NORMALIZERS[k](t)) for t in self.texts}
            if _strip_accents(NORMALIZERS[k](value)) in self.cache[k]:
                return True
        return False


# --- Scoring -----------------------------------------------------------------


def leaves(obj, prefix: str = "") -> dict[str, object]:
    """Flatten nested dicts and lists into paths like 'items[2].total'."""
    out: dict[str, object] = {}
    items = obj.items() if isinstance(obj, dict) else ((f"[{i}]", v) for i, v in enumerate(obj))
    for key, value in items:
        path = f"{prefix}{key}" if key.startswith("[") else f"{prefix}.{key}" if prefix else key
        if isinstance(value, (dict, list)):
            out.update(leaves(value, path))
        else:
            out[path] = value
    return out


def lookup(obj, path: str):
    for key, index in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path):
        if index:
            if not isinstance(obj, list) or int(index) >= len(obj):
                return None
            obj = obj[int(index)]
        else:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
    return obj


def _lists(obj, prefix: str = ""):
    """Yield (path, list) for every list inside obj."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, list):
                yield path, value
            yield from _lists(value, path)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _lists(value, f"{prefix}[{i}]")


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in {"", "null", "N/A", "-"})


def score_fields(gold: dict, pred: dict | None, kinds: dict[str, str], printed: list[str] | None = None) -> list[dict]:
    """Score every gold leaf. An unparseable prediction is scored as an empty one."""
    pred = pred or {}
    on_page = _Printed(printed or [])
    results = []
    for path, gold_value in leaves(gold).items():
        pred_value = lookup(pred, path)
        kind = kind_for(path, kinds)
        lenient = None
        if gold_value is None:
            if _is_empty(pred_value):
                bucket = "correct"
            else:
                bucket = "misattribution" if on_page.contains(pred_value, kind) else "hallucination"
        elif _is_empty(pred_value):
            bucket = "omission"
        else:
            strict, lenient = _same(gold_value, pred_value, kind)
            if strict:
                bucket = "correct"
            else:
                bucket = "misattribution" if on_page.contains(pred_value, kind) else "wrong"
        results.append({
            "path": path,
            "bucket": bucket,
            "lenient_correct": bucket == "correct" or bool(lenient),
            "gold": gold_value,
            "pred": pred_value,
        })

    for path, gold_rows in _lists(gold):
        pred_rows = lookup(pred, path)
        if isinstance(pred_rows, list):
            for i in range(len(gold_rows), len(pred_rows)):
                results.append({
                    "path": f"{path}[{i}]", "bucket": "extra_row", "lenient_correct": False,
                    "gold": None, "pred": pred_rows[i],
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
