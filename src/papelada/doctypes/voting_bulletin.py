"""Synthetic voting bulletins (boletim de urna), printed on thermal paper.

Parties and candidates are fictional. Totals are consistent the way a real bulletin's
are: per office, nominal + party-only + blank + null votes = turnout, and
eligible voters = turnout + absent. The print also carries numbers that look like
targets (voting location, machine id, per-party totals, verification code).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from faker import Faker
from PIL import Image

from papelada import places
from papelada.render import Style, printed_text, render

DOC_TYPE = "voting_bulletin"

FIELD_KINDS = {
    "municipality_code": "key",
    "date": "datetime",
    "*.number": "key",
    "*.votes": "number",
    "*.blank": "number",
    "*.null_votes": "number",
    "*.total": "number",
    "eligible_voters": "number",
    "turnout": "number",
    "absent": "number",
    "zone": "number",
    "section": "number",
    "round": "number",
}

STATES = {
    "AC": "ACRE", "AL": "ALAGOAS", "AP": "AMAPÁ", "AM": "AMAZONAS", "BA": "BAHIA", "CE": "CEARÁ",
    "DF": "DISTRITO FEDERAL", "ES": "ESPÍRITO SANTO", "GO": "GOIÁS", "MA": "MARANHÃO",
    "MT": "MATO GROSSO", "MS": "MATO GROSSO DO SUL", "MG": "MINAS GERAIS", "PA": "PARÁ",
    "PB": "PARAÍBA", "PR": "PARANÁ", "PE": "PERNAMBUCO", "PI": "PIAUÍ", "RJ": "RIO DE JANEIRO",
    "RN": "RIO GRANDE DO NORTE", "RS": "RIO GRANDE DO SUL", "RO": "RONDÔNIA", "RR": "RORAIMA",
    "SC": "SANTA CATARINA", "SP": "SÃO PAULO", "SE": "SERGIPE", "TO": "TOCANTINS",
}

# Fictional parties: (acronym, number).
PARTIES = [
    ("PAV", 71), ("MCB", 72), ("PRS", 73), ("PIA", 74), ("ALB", 76),
    ("PSU", 78), ("NVB", 79), ("PDE", 81), ("RCB", 82), ("PLT", 84),
]

# Election year -> (first round, second round).
ELECTIONS = {2022: (date(2022, 10, 2), date(2022, 10, 30)), 2026: (date(2026, 10, 4), date(2026, 10, 25))}

# Ballot names as candidates register them.
NICKNAMES = ["ZÉ", "TONHO", "CHICO", "ZEZINHO", "BIL", "DUDA", "TETÊ", "NENÊ", "JUNINHO", "BETO", "CIDA", "DONA NICE"]
NICK_SUFFIXES = ["DO GÁS", "DA FARMÁCIA", "DO POVO", "DA SAÚDE", "DO SINDICATO", "DA FEIRA", "DO TÁXI", "DO BAIRRO"]
TITLES = ["PROFESSORA", "PROFESSOR", "DOUTOR", "PASTOR", "IRMÃ", "SARGENTO", "DELEGADA", "ENFERMEIRA"]


@dataclass
class Sample:
    gold: dict
    meta: dict
    image: Image.Image


def _split(total: int, parts: int, rng: random.Random) -> list[int]:
    """Split total into parts integers, each at least 1 when possible, with uneven random weights."""
    if parts == 0:
        return []
    base = [1] * parts if total >= parts else [0] * parts
    rest = total - sum(base)
    weights = [rng.random() ** 2 + 0.02 for _ in range(parts)]
    shares = [rest * w / sum(weights) for w in weights]
    result = [b + int(s) for b, s in zip(base, shares)]
    for i in sorted(range(parts), key=lambda i: shares[i] - int(shares[i]), reverse=True)[: total - sum(result)]:
        result[i] += 1
    return result


def _ballot_name(rng: random.Random, fake: Faker) -> tuple[str, bool]:
    """(name, is_trap). Nicknames and titles are the uncommon strings."""
    roll = rng.random()
    if roll < 0.25:
        return f"{rng.choice(NICKNAMES)} {rng.choice(NICK_SUFFIXES)}", True
    if roll < 0.45:
        return f"{rng.choice(TITLES)} {fake.first_name().upper()}", True
    return f"{fake.first_name()} {fake.last_name()}".upper(), False


def generate(seed: int) -> Sample:
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    fake.seed_instance(seed)

    year = rng.choice(list(ELECTIONS))
    second_round = rng.random() < 0.3
    election_date = ELECTIONS[year][1 if second_round else 0]
    uf = rng.choice(list(STATES))
    municipality = places.city(rng, uf)
    eligible = rng.randint(150, 450)
    absent = round(eligible * rng.uniform(0.1, 0.3))
    turnout = eligible - absent

    if second_round:
        offices = [("Governador", "major", 2)] if rng.random() < 0.6 else []
        offices.append(("Presidente", "major", 2))
    else:
        offices = [
            ("Deputado Federal", "prop", 4),
            ("Deputado Distrital" if uf == "DF" else "Deputado Estadual", "prop", 5),
            ("Senador", "major", 3),
            ("Governador", "major", 2),
            ("Presidente", "major", 2),
        ]

    traps: list[str] = []
    contests = []
    for c, (office, system, digits) in enumerate(offices):
        blank = round(turnout * rng.uniform(0.01, 0.08))
        null = round(turnout * rng.uniform(0.02, 0.10))
        valid = turnout - blank - null
        candidates, party_votes = [], []
        if system == "major":
            count = 2 if second_round else rng.randint(3, 6)
            parties = rng.sample(PARTIES, count)
            for votes, (acronym, number) in zip(_split(valid, count, rng), parties):
                name, trap = _ballot_name(rng, fake)
                if trap:
                    traps.append(f"contests[{c}].candidates[{len(candidates)}].name")
                suffix = str(rng.randint(1, 9)) if digits == 3 else ""
                candidates.append({"number": f"{number}{suffix}", "name": name, "party": acronym, "votes": votes})
        else:
            parties = rng.sample(PARTIES, rng.randint(2, 3))
            for party_total, (acronym, number) in zip(_split(valid, len(parties), rng), parties):
                legend = min(party_total - 1, round(party_total * rng.uniform(0.03, 0.12)))
                n_candidates = min(rng.randint(2, 4), party_total - legend)
                used = set()
                for votes in _split(party_total - legend, n_candidates, rng):
                    while (tail := rng.randint(1, 10 ** (digits - 2) - 1)) in used:
                        pass
                    used.add(tail)
                    name, trap = _ballot_name(rng, fake)
                    if trap:
                        traps.append(f"contests[{c}].candidates[{len(candidates)}].name")
                    candidates.append({
                        "number": f"{number}{tail:0{digits - 2}d}", "name": name, "party": acronym, "votes": votes,
                    })
                party_votes.append({"party": acronym, "votes": legend})
        contests.append({
            "office": office,
            "candidates": candidates,
            "party_votes": party_votes,
            "blank": blank,
            "null_votes": null,
            "total": turnout,
        })

    gold = {
        "election": f"Eleições Gerais {year}",
        "round": 2 if second_round else 1,
        "date": election_date.isoformat(),
        "state": uf,
        "municipality_code": f"{rng.randint(1000, 99999):05d}",
        "municipality": municipality,
        "zone": rng.randint(1, 400),
        "section": rng.randint(1, 900),
        "eligible_voters": eligible,
        "turnout": turnout,
        "absent": absent,
        "contests": contests,
    }

    blocks = _blocks(gold, rng, election_date)
    style = Style(
        width=560, family="mono", margin=28, fg="#1a1a1a", muted="#3a3a3a", accent="#1a1a1a",
        body_size=19, label_size=19, title_size=22, amount_size=22, field_mode="inline",
        align_title="center", dashed_rules=True, line_gap=5,
    )
    return Sample(
        gold=gold,
        meta={
            "doc_type": DOC_TYPE,
            "seed": seed,
            "layout": "thermal",
            "round": gold["round"],
            "contests": len(contests),
            "candidates": sum(len(c["candidates"]) for c in contests),
            "absent_fields": [],
            "traps": traps,
            "printed_text": printed_text(blocks),
        },
        image=render(blocks, style),
    )


def _blocks(gold: dict, rng: random.Random, election_date: date) -> list[tuple]:
    uf = gold["state"]
    opened = datetime.combine(election_date, datetime.min.time()) + timedelta(hours=7, minutes=rng.randint(0, 59))
    closed = datetime.combine(election_date, datetime.min.time()) + timedelta(hours=17, seconds=rng.randint(0, 900))
    machine = f"{rng.randint(1_000_000, 9_999_999):08d}"
    blocks: list[tuple] = [
        ("title", "JUSTIÇA ELEITORAL"),
        ("subtitle", "TRIBUNAL REGIONAL ELEITORAL"),
        ("subtitle", f"{'DO' if uf in {'AC', 'AP', 'AM', 'CE', 'DF', 'ES', 'MA', 'MT', 'MS', 'PA', 'PI', 'PR', 'RN', 'RS', 'TO'} else 'DE'} {STATES[uf]}"),
        ("gap", 6),
        ("title", "BOLETIM DE URNA"),
        ("subtitle", gold["election"]),
        ("subtitle", f"{gold['round']}º Turno ({election_date:%d/%m/%Y})"),
        ("rule",),
        ("field", "UF", uf),
        ("field", "Município", f"{gold['municipality_code']} {gold['municipality'].upper()}"),
        ("field", "Zona Eleitoral", f"{gold['zone']:04d}"),
        ("field", "Seção Eleitoral", f"{gold['section']:04d}"),
        ("field", "Local de Votação", f"{rng.randint(1000, 1999)}"),
        ("field", "Eleitores aptos", str(gold["eligible_voters"])),
        ("rule",),
        ("field", "Código identificação UE", f"{machine[:2]}.{machine[2:5]}.{machine[5:]}"),
        ("field", "Data de abertura", f"{opened:%d/%m/%Y %H:%M:%S}"),
        ("field", "Data de fechamento", f"{closed:%d/%m/%Y %H:%M:%S}"),
        ("field", "Data de emissão", f"{closed + timedelta(seconds=rng.randint(20, 90)):%d/%m/%Y %H:%M:%S}"),
    ]

    for contest in gold["contests"]:
        blocks += [("rule",), ("title", contest["office"].upper())]
        if contest["party_votes"]:
            party_votes = {p["party"]: p["votes"] for p in contest["party_votes"]}
            for party, legend in party_votes.items():
                rows = [c for c in contest["candidates"] if c["party"] == party]
                number = rows[0]["number"][:2]
                blocks.append(("section", f"{party} - {number}"))
                blocks += [("field", f"{c['number']} {c['name']}", str(c["votes"])) for c in rows]
                blocks.append(("field", "Votos de legenda", str(legend)))
                blocks.append(("field", "Total do partido", str(legend + sum(c["votes"] for c in rows))))
            nominal = sum(c["votes"] for c in contest["candidates"])
            blocks += [
                ("gap", 8),
                ("field", "Votos nominais", str(nominal)),
                ("field", "Votos de legenda", str(sum(party_votes.values()))),
            ]
        else:
            blocks += [("field", f"{c['number']} {c['name']} ({c['party']})", str(c["votes"])) for c in contest["candidates"]]
        blocks += [
            ("field", "Brancos", str(contest["blank"])),
            ("field", "Nulos", str(contest["null_votes"])),
            ("field", "Total apurado", str(contest["total"])),
        ]

    code = "".join(rng.choice("0123456789") for _ in range(16))
    digest = "".join(rng.choice("0123456789ABCDEF") for _ in range(64))
    blocks += [
        ("rule",),
        ("field", "Eleitores aptos", str(gold["eligible_voters"])),
        ("field", "Comparecimento", str(gold["turnout"])),
        ("field", "Eleitores faltosos", str(gold["absent"])),
        ("field", "Habilitados por ano de nascimento", "0"),
        ("rule",),
        ("field", "Código verificador", " ".join(code[i : i + 4] for i in range(0, 16, 4))),
        ("note", "Assinatura digital"),
        ("note", " ".join(digest[i : i + 8] for i in range(0, 64, 8))),
    ]
    return blocks
