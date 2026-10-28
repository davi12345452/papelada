"""Language-prior traps.

Text that is printed exactly as written here, but that a model is tempted to "fix"
toward a more common spelling or word: uncommon Brazilian name spellings, homophones,
typos and slang. Fields holding a trap are listed in meta.json so the report can show
accuracy on traps separately.
"""

from __future__ import annotations

import random
import unicodedata

# First names with uncommon spellings; the common form is what models drift to.
NAMES = [
    "Thyago", "Maicon", "Uóxinton", "Kauã", "Mykaelly", "Wellyngton", "Jhennifer", "Rayssa",
    "Ketlyn", "Stheffany", "Kawan", "Brayan", "Kemilly", "Thayná", "Iasmin", "Wesllen",
    "Maykon", "Lohanna", "Dyego", "Raphaella",
]

# Messages as payers actually type them: homophones used correctly, typos, slang.
DESCRIPTIONS = [
    "conserto do celular", "conserto da bike", "sessão de fisio", "cessão da vaga",
    "concerto da orquestra", "pagamento do almoso", "rassa do churras", "vlw pela carona",
    "mensalidade acadmia", "excursão da escola", "cocha de retalhos", "pg parcela 3/10 tênis",
]

EMAIL_DOMAINS = ["gmail.com", "hotmail.com", "yahoo.com.br", "outlook.com", "uol.com.br", "icloud.com"]


def email_from_name(name: str, rng: random.Random) -> str:
    """'Thyago Souza' -> 'thyago.souza@gmail.com' (accents dropped, as email providers require)."""
    ascii_name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode().lower()
    parts = [p for p in ascii_name.split() if p.isalpha()]
    first, last = parts[0], parts[-1]
    local = rng.choice([f"{first}.{last}", f"{first}{last}", f"{first}_{last}{rng.randint(1, 99)}"])
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"
