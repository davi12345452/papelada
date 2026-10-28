"""Real Brazilian places for generated addresses.

Municipalities come from IBGE (data/municipalities.csv, public data). Street and
district names are common real ones, so a model that writes a different real word
is unambiguously wrong rather than "fixing" an invented name.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

STREET_TYPES = ["Rua", "Rua", "Rua", "Avenida", "Avenida", "Travessa", "Alameda", "Praça", "Rodovia"]

STREET_NAMES = [
    "Sete de Setembro", "Quinze de Novembro", "Tiradentes", "Dom Pedro II", "Marechal Deodoro",
    "Getúlio Vargas", "Santos Dumont", "Rui Barbosa", "Duque de Caxias", "Floriano Peixoto",
    "Barão do Rio Branco", "José Bonifácio", "Castro Alves", "Machado de Assis", "Princesa Isabel",
    "Visconde de Mauá", "Benjamin Constant", "Joaquim Nabuco", "São Paulo", "Paraná", "Bahia",
    "das Flores", "das Palmeiras", "dos Andradas", "Coronel Fernandes", "Padre Anchieta",
    "Presidente Vargas", "Treze de Maio", "Independência", "Brasil", "Amazonas", "Goiás",
    "Monteiro Lobato", "Carlos Gomes", "Senador Feijó", "General Osório", "Almirante Barroso",
    "Frei Caneca", "Voluntários da Pátria", "Conselheiro Lafaiete",
]

DISTRICTS = [
    "Centro", "Centro", "Jardim América", "Vila Nova", "Boa Vista", "Santa Cruz", "São José",
    "Industrial", "Planalto", "Bela Vista", "Santo Antônio", "Jardim Europa", "Vila Operária",
    "Cidade Nova", "Alto da Boa Vista", "Parque das Nações", "Jardim Primavera", "São Cristóvão",
    "Nossa Senhora Aparecida", "Distrito Industrial", "Jardim Paulista", "Vila Mariana",
    "Santa Mônica", "Morada do Sol", "Liberdade", "Aeroporto", "Conjunto Habitacional",
    "Recanto dos Pássaros", "Vila São Jorge", "Jardim das Acácias",
]


@lru_cache(maxsize=1)
def municipalities() -> dict[str, list[tuple[str, int]]]:
    """UF -> [(name, IBGE code)]."""
    by_uf: dict[str, list[tuple[str, int]]] = defaultdict(list)
    with (DATA / "municipalities.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_uf[row["uf"]].append((row["name"], int(row["ibge_code"])))
    return dict(by_uf)


def city(rng: random.Random, uf: str) -> str:
    return rng.choice(municipalities()[uf])[0]


def street(rng: random.Random) -> str:
    return f"{rng.choice(STREET_TYPES)} {rng.choice(STREET_NAMES)}"


def district(rng: random.Random) -> str:
    return rng.choice(DISTRICTS)


def address(rng: random.Random, uf: str) -> dict:
    return {
        "street": street(rng),
        "number": str(rng.randint(1, 4999)),
        "district": district(rng),
        "city": city(rng, uf),
        "state": uf,
        "zip_code": f"{rng.randint(1_000_000, 99_999_999):08d}",
    }
