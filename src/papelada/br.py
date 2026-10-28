"""Brazilian identifiers and formats: CPF, CNPJ, money, masks."""

from __future__ import annotations

import random


def _check_digit(digits: list[int], weights: list[int]) -> int:
    remainder = sum(d * w for d, w in zip(digits, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def cpf(rng: random.Random) -> str:
    """Random CPF with valid check digits, digits only."""
    while True:
        digits = [rng.randint(0, 9) for _ in range(9)]
        if len(set(digits)) > 1:  # all-equal CPFs are invalid by rule
            break
    digits.append(_check_digit(digits, list(range(10, 1, -1))))
    digits.append(_check_digit(digits, list(range(11, 1, -1))))
    return "".join(map(str, digits))


def cnpj(rng: random.Random) -> str:
    """Random CNPJ (headquarters branch 0001) with valid check digits, digits only."""
    digits = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digits.append(_check_digit(digits, weights))
    digits.append(_check_digit(digits, [6] + weights))
    return "".join(map(str, digits))


def is_valid_cpf(value: str) -> bool:
    d = [int(c) for c in value if c.isdigit()]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    return (
        d[9] == _check_digit(d[:9], list(range(10, 1, -1)))
        and d[10] == _check_digit(d[:10], list(range(11, 1, -1)))
    )


def is_valid_cnpj(value: str) -> bool:
    d = [int(c) for c in value if c.isdigit()]
    if len(d) != 14:
        return False
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return d[12] == _check_digit(d[:12], weights) and d[13] == _check_digit(d[:13], [6] + weights)


def format_cpf(value: str) -> str:
    return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"


def mask_cpf(value: str) -> str:
    """Central Bank receipt mask: only the middle six digits are visible."""
    return f"***.{value[3:6]}.{value[6:9]}-**"


def format_cnpj(value: str) -> str:
    return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"


def brl(cents: int) -> str:
    """1234567 -> 'R$ 12.345,67'"""
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def decimal_str(cents: int) -> str:
    """1234567 -> '12345.67' (gold format for money)"""
    reais, centavos = divmod(cents, 100)
    return f"{reais}.{centavos:02d}"


MONTHS_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# IBGE state codes used in NF-e access keys.
UF_CODES = {
    "SP": "35", "RJ": "33", "MG": "31", "RS": "43", "PR": "41", "SC": "42",
    "BA": "29", "PE": "26", "CE": "23", "GO": "52", "DF": "53", "ES": "32",
}


def nfe_check_digit(first_43: str) -> int:
    """Mod 11 with weights 2..9 cycling from the right, as in the NF-e manual."""
    total = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(first_43)))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def nfe_access_key(uf: str, year: int, month: int, cnpj: str, series: int, number: int, rng: random.Random) -> str:
    """44-digit access key: cUF AAMM CNPJ mod serie nNF tpEmis cNF cDV."""
    random_code = f"{rng.randint(0, 99_999_999):08d}"
    first_43 = f"{UF_CODES[uf]}{year % 100:02d}{month:02d}{cnpj}55{series:03d}{number:09d}1{random_code}"
    return first_43 + str(nfe_check_digit(first_43))


def is_valid_nfe_access_key(key: str) -> bool:
    digits = "".join(c for c in key if c.isdigit())
    return len(digits) == 44 and int(digits[-1]) == nfe_check_digit(digits[:43])


def format_access_key(key: str) -> str:
    return " ".join(key[i : i + 4] for i in range(0, 44, 4))


def format_number(value, decimals: int) -> str:
    """Brazilian number formatting: 1234.5 -> '1.234,50'."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")
