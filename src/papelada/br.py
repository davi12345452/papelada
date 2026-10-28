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
