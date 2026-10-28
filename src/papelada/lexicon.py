"""Lexicon of real Portuguese words and Brazilian place names.

Used to tell a misread ("PATINHO" -> "PATRINHO") from a plausible substitution, where a
model that cannot read the print writes a different real word or place instead
("Pereira" -> "Pirenópolis"). The lists are downloaded on demand into data/lexicon/
and never committed:

- 50k most frequent Brazilian Portuguese words, FrequencyWords by Hermit Dave (CC BY-SA 4.0)
- Brazilian municipalities, IBGE localities API (public data)
"""

from __future__ import annotations

import gzip
import json
import unicodedata
import urllib.request
from functools import lru_cache
from pathlib import Path

LEXICON_DIR = Path(__file__).resolve().parents[2] / "data" / "lexicon"
WORDS_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/pt_br/pt_br_50k.txt"
MUNICIPALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"


def loose(text: str) -> str:
    """Casefolded, accents removed: the form tokens are compared in."""
    return unicodedata.normalize("NFD", text.casefold()).encode("ascii", "ignore").decode()


def tokens(text: str) -> list[str]:
    cleaned = "".join(c if c.isalnum() else " " for c in loose(text))
    return cleaned.split()


def fetch(directory: Path = LEXICON_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(WORDS_URL, timeout=60) as response:
        words = {loose(line.split()[0]) for line in response.read().decode("utf-8").splitlines() if line.strip()}
    with urllib.request.urlopen(MUNICIPALITIES_URL, timeout=60) as response:
        body = response.read()
    if body[:2] == b"\x1f\x8b":  # IBGE sends gzip even when not asked to
        body = gzip.decompress(body)
    places = {t for m in json.loads(body) for t in tokens(m["municipio-nome"])}
    out = directory / "lexicon.txt"
    out.write_text("\n".join(sorted(w for w in words | places if w.isalpha() and len(w) >= 3)) + "\n")
    load.cache_clear()
    return out


@lru_cache(maxsize=1)
def load(directory: Path = LEXICON_DIR) -> frozenset[str]:
    """The lexicon, or an empty set when it has not been fetched (substitution is then not detected)."""
    path = directory / "lexicon.txt"
    return frozenset(path.read_text().split()) if path.exists() else frozenset()


def is_substitution(gold: str, pred: str, lexicon: frozenset[str] | None = None) -> bool:
    """True when the prediction swaps at least one printed word for a different real word.

    Only words of four or more letters count, so "de" -> "da" stays a misread.
    """
    lexicon = load() if lexicon is None else lexicon
    if not lexicon:
        return False
    printed = set(tokens(gold))
    return any(
        token not in printed and len(token) >= 4 and token.isalpha() and token in lexicon
        for token in tokens(pred)
    )
