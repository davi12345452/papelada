"""Synthetic PIX transfer receipts (comprovantes).

Institutions are fictional and layouts are generic: the goal is realistic structure,
not imitation of any real bank's branding.
"""

from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from faker import Faker
from PIL import Image

from papelada import br, traps
from papelada.render import Style, printed_text, render

DOC_TYPE = "pix_receipt"

# (name, ISPB). ISPBs are made up; 8 digits like the real ones.
INSTITUTIONS = [
    ("Banco Aurora S.A.", "31872495"),
    ("Caju Pagamentos S.A.", "40217736"),
    ("Cooperativa de Crédito Sertão", "52904118"),
    ("Banco Pampa S.A.", "17345602"),
    ("Ipê Instituição de Pagamento", "29481153"),
    ("Jatobá Banco Digital S.A.", "63018827"),
    ("Banco Tucano S.A.", "08562314"),
]

DESCRIPTIONS = [
    "aluguel outubro", "pizza de sexta", "racha do churrasco", "mensalidade academia",
    "parcela 3/10", "material escolar", "presente de aniversário",
    "conta de luz", "frete", "uber de ontem", "ingresso show",
]

ACCENTS = ["#5b2a86", "#0b6e4f", "#c2410c", "#1d4ed8", "#0f172a", "#be123c", "#7c5e10"]

PARTY_FIELDS = ("name", "document", "institution", "agency", "account")

# How each field is normalized before scoring (see papelada.score). Default: "text".
FIELD_KINDS = {
    "amount": "money",
    "datetime": "datetime",
    "end_to_end_id": "code",
    "payee_key": "key",
    "*.document": "key",
    "*.agency": "key",
    "*.account": "key",
}

# Field -> probability the layout hides it, to measure hallucination on absent fields.
OPTIONAL = {
    "payer.document": 0.3,
    "payee.document": 0.2,
    "payer.institution": 0.1,
    "end_to_end_id": 0.15,
}
# Agency and account are hidden together, per party.
OPTIONAL_ACCOUNT = 0.4

TRAP_NAME = 0.4  # chance each person gets an uncommon first-name spelling
TRAP_DESCRIPTION = 0.5  # chance a present description is a trap


@dataclass
class Sample:
    gold: dict
    meta: dict
    image: Image.Image


class _Builder:
    """Collects blocks and records the gold value of every field actually rendered."""

    def __init__(self, values: dict[str, tuple[object, str]], hidden: set[str]):
        self.values = values
        self.hidden = hidden
        self.blocks: list[tuple] = []
        self.shown: dict[str, object] = {}

    def add(self, *block) -> None:
        self.blocks.append(block)

    def available(self, path: str) -> bool:
        return path in self.values and path not in self.hidden

    def show(self, path: str, block: tuple, gold: object | None = None) -> None:
        if not self.available(path):
            return
        self.blocks.append(block)
        self.shown[path] = self.values[path][0] if gold is None else gold

    def field(self, path: str, label: str, upper: bool = False) -> None:
        if self.available(path):
            display = self.values[path][1]
            self.show(path, ("field", label, display.upper() if upper else display))


def generate(seed: int) -> Sample:
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    fake.seed_instance(seed)

    values, key_type, dt, trap_paths = _fake_values(rng, fake)
    hidden = {path for path, p in OPTIONAL.items() if rng.random() < p}
    for party in ("payer", "payee"):
        if rng.random() < OPTIONAL_ACCOUNT:
            hidden |= {f"{party}.agency", f"{party}.account"}

    layout_name = rng.choice(list(LAYOUTS))
    builder = _Builder(values, hidden)
    style = LAYOUTS[layout_name](builder, dt, rng)

    return Sample(
        gold=_gold(builder.shown),
        meta={
            "doc_type": DOC_TYPE,
            "seed": seed,
            "layout": layout_name,
            "payee_key_type": key_type,
            "absent_fields": sorted(_all_paths() - builder.shown.keys()),
            "traps": sorted(p for p in trap_paths if p in builder.shown),
            "printed_text": printed_text(builder.blocks),
        },
        image=render(builder.blocks, style),
    )


def _fake_values(rng: random.Random, fake: Faker):
    """Every possible field as path -> (gold value, display string)."""
    cents = int(10 ** rng.uniform(2, 5.7))  # R$ 1,00 to ~R$ 5.000,00, log-uniform
    if rng.random() < 0.3:
        cents -= cents % 1000  # round amounts are common
    cents = max(cents, 100)
    dt = datetime(2025, 1, 1) + timedelta(seconds=rng.randrange(0, 640 * 24 * 3600))

    trap_paths: set[str] = set()

    def person(path: str) -> str:
        if rng.random() < TRAP_NAME:
            trap_paths.add(path)
            return f"{rng.choice(traps.NAMES)} {fake.last_name()}"
        return fake.name()

    payer_inst, payee_inst = rng.choice(INSTITUTIONS), rng.choice(INSTITUTIONS)
    payer_cpf = br.cpf(rng)
    values: dict[str, tuple[object, str]] = {
        "amount": (br.decimal_str(cents), br.brl(cents)),
        "payer.name": (person("payer.name"), ""),
        "payer.document": (br.mask_cpf(payer_cpf), ""),
        "payer.institution": (payer_inst[0], ""),
    }

    if rng.random() < 0.75:
        payee_cpf = br.cpf(rng)
        values["payee.name"] = (person("payee.name"), "")
        values["payee.document"] = (br.mask_cpf(payee_cpf), "")
        key_type = rng.choice(["email", "phone", "cpf", "random"])
    else:
        payee_cnpj = br.cnpj(rng)
        values["payee.name"] = (fake.company(), "")
        values["payee.document"] = (br.format_cnpj(payee_cnpj), "")
        key_type = rng.choice(["email", "phone", "cnpj", "random"])
    values["payee.institution"] = (payee_inst[0], "")

    for party in ("payer", "payee"):
        agency = f"{rng.randint(1, 9999):04d}"
        account = f"{rng.randint(1000, 99999999)}-{rng.randint(0, 9)}"
        values[f"{party}.agency"] = (agency, "")
        values[f"{party}.account"] = (account, "")

    if key_type == "email" and "payee.name" in trap_paths:
        key = traps.email_from_name(values["payee.name"][0], rng)
        trap_paths.add("payee_key")
    elif key_type == "email":
        key = fake.free_email()
    elif key_type == "phone":
        key = f"+55 {rng.randint(11, 99)} 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    elif key_type == "cpf":
        key = values["payee.document"][0]
    elif key_type == "cnpj":
        key = values["payee.document"][0]
    else:
        key = str(uuid.UUID(int=rng.getrandbits(128), version=4))
    values["payee_key"] = (key, "")

    # "I" and "l" render identically in common sans fonts, which would make the gold unreadable.
    alphabet = [c for c in string.ascii_letters + string.digits if c not in "Il"]
    suffix = "".join(rng.choice(alphabet) for _ in range(11))
    values["end_to_end_id"] = (f"E{payer_inst[1]}{dt:%Y%m%d%H%M}{suffix}", "")

    if rng.random() < 0.45:
        if rng.random() < TRAP_DESCRIPTION:
            values["description"] = (rng.choice(traps.DESCRIPTIONS), "")
            trap_paths.add("description")
        else:
            values["description"] = (rng.choice(DESCRIPTIONS), "")

    # Unless set above, what is displayed is the gold value itself.
    values = {k: (g, d or str(g)) for k, (g, d) in values.items()}
    return values, key_type, dt, trap_paths


def _all_paths() -> set[str]:
    top = {"amount", "datetime", "end_to_end_id", "description", "payee_key"}
    return top | {f"{p}.{f}" for p in ("payer", "payee") for f in PARTY_FIELDS}


def _gold(shown: dict[str, object]) -> dict:
    def party(prefix: str) -> dict:
        return {f: shown.get(f"{prefix}.{f}") for f in PARTY_FIELDS}

    return {
        "amount": shown.get("amount"),
        "datetime": shown.get("datetime"),
        "end_to_end_id": shown.get("end_to_end_id"),
        "description": shown.get("description"),
        "payer": party("payer"),
        "payee": party("payee"),
        "payee_key": shown.get("payee_key"),
    }


# --- Layouts -----------------------------------------------------------------
# Each layout fills the builder and returns its Style. The datetime is rendered
# per layout because the displayed precision decides the gold value.


def _app_card(b: _Builder, dt: datetime, rng: random.Random) -> Style:
    """Mobile app screenshot: colored header, big amount, stacked label/value."""
    b.values["datetime"] = (f"{dt:%Y-%m-%dT%H:%M:%S}", f"{dt:%d/%m/%Y} às {dt:%H:%M:%S}")
    b.add("title", "Comprovante de transferência")
    b.add("subtitle", "Pix enviado")
    b.show("amount", ("amount", b.values["amount"][1]))
    b.show("datetime", ("subtitle", b.values["datetime"][1]))
    b.add("rule")
    b.add("section", "Destino")
    b.field("payee.name", "Nome")
    b.field("payee.document", "CPF/CNPJ")
    b.field("payee.institution", "Instituição")
    b.field("payee.agency", "Agência")
    b.field("payee.account", "Conta")
    b.field("payee_key", "Chave Pix")
    b.add("section", "Origem")
    b.field("payer.name", "Nome")
    b.field("payer.document", "CPF")
    b.field("payer.institution", "Instituição")
    b.field("payer.agency", "Agência")
    b.field("payer.account", "Conta")
    if b.available("description"):
        b.add("section", "Mensagem")
        b.field("description", "Descrição")
    b.add("rule")
    b.field("end_to_end_id", "ID da transação")
    b.add("note", "Este comprovante tem validade para todos os fins legais.")
    return Style(width=720, header_band=True, accent=rng.choice(ACCENTS), field_mode="stacked")


def _thermal_slip(b: _Builder, dt: datetime, rng: random.Random) -> Style:
    """Narrow monospace slip, uppercase, no agency/account."""
    b.values["datetime"] = (f"{dt:%Y-%m-%dT%H:%M}", f"{dt:%d/%m/%Y %H:%M}")
    b.add("title", "COMPROVANTE PIX")
    b.show("datetime", ("subtitle", b.values["datetime"][1]))
    b.add("rule")
    b.field("amount", "VALOR")
    b.add("rule")
    b.add("section", "PAGADOR")
    b.field("payer.name", "NOME", upper=True)
    b.field("payer.document", "CPF")
    b.field("payer.institution", "INST.", upper=True)
    b.add("section", "RECEBEDOR")
    b.field("payee.name", "NOME", upper=True)
    b.field("payee.document", "CPF/CNPJ")
    b.field("payee.institution", "INST.", upper=True)
    b.field("payee_key", "CHAVE")
    b.add("rule")
    b.field("description", "MSG", upper=True)
    b.field("end_to_end_id", "ID")
    b.add("rule")
    b.add("note", "OBRIGADO PELA PREFERENCIA")
    return Style(
        width=560, family="mono", margin=28, fg="#1a1a1a", muted="#444444", accent="#1a1a1a",
        body_size=20, label_size=19, title_size=26, field_mode="inline",
        align_title="center", dashed_rules=True, line_gap=6,
    )


def _statement(b: _Builder, dt: datetime, rng: random.Random) -> Style:
    """Wide printable page: label left, value right, sectioned."""
    month = br.MONTHS_PT[dt.month - 1]
    b.values["datetime"] = (f"{dt:%Y-%m-%dT%H:%M:%S}", f"{dt.day:02d} {month} {dt.year} - {dt:%H:%M:%S}")
    b.add("title", "Comprovante de Pagamento Pix")
    b.add("subtitle", "Transação concluída")
    b.add("rule")
    b.field("amount", "Valor do pagamento")
    b.field("datetime", "Data do pagamento")
    b.field("description", "Descrição")
    b.add("section", "Dados do recebedor")
    b.field("payee.name", "Nome")
    b.field("payee.document", "CPF/CNPJ")
    b.field("payee_key", "Chave")
    b.field("payee.institution", "Instituição")
    b.field("payee.agency", "Agência")
    b.field("payee.account", "Conta")
    b.add("section", "Dados do pagador")
    b.field("payer.name", "Nome")
    b.field("payer.document", "CPF")
    b.field("payer.institution", "Instituição")
    b.field("payer.agency", "Agência")
    b.field("payer.account", "Conta")
    b.add("rule")
    b.field("end_to_end_id", "Identificador")
    return Style(width=1100, margin=56, accent=rng.choice(ACCENTS), field_mode="inline", body_size=24)


LAYOUTS = {
    "app_card": _app_card,
    "thermal_slip": _thermal_slip,
    "statement": _statement,
}
