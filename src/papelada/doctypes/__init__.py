import json
from functools import lru_cache
from pathlib import Path

from papelada.doctypes import danfe, pix_receipt

DOC_TYPES = {module.DOC_TYPE: module for module in (pix_receipt, danfe)}

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas"


@lru_cache(maxsize=None)
def load_schema(doc_type: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{doc_type}.schema.json").read_text())
