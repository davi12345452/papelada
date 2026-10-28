"""Synthetic DANFE (printed NF-e) in the standard portrait layout.

Besides the extraction targets, the page carries the boxes a real DANFE has
(authorization protocol, installments, carrier, per-item ICMS) as distractors:
reading a number from the wrong box shows up as misattribution.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from faker import Faker
from PIL import Image, ImageDraw

from papelada import br
from papelada.render import font, wrap

DOC_TYPE = "danfe"

FIELD_KINDS = {
    "access_key": "key",
    "number": "number",
    "series": "number",
    "issue_date": "datetime",
    "*.cnpj": "key",
    "*.document": "key",
    "*.state_registration": "key",
    "*.zip_code": "key",
    "*.ncm": "key",
    "*.cfop": "key",
    "*.code": "key",
    "*.quantity": "number",
    "*.unit_price": "money",
    "*.total": "money",
    "*.products": "money",
    "*.icms_base": "money",
    "*.icms": "money",
    "*.freight": "money",
    "*.discount": "money",
    "*.invoice_total": "money",
}

# (description, NCM, unit, unit price range in cents, sold by weight)
PRODUCTS = [
    ("ARROZ TIPO 1 5KG", "10063021", "UN", (1800, 3500), False),
    ("FEIJAO CARIOCA 1KG", "07133319", "UN", (600, 1200), False),
    ("OLEO DE SOJA 900ML", "15079011", "UN", (500, 1000), False),
    ("CAFE TORRADO E MOIDO 500G", "09012100", "UN", (1200, 2500), False),
    ("ACUCAR CRISTAL 5KG", "17011400", "UN", (1500, 3000), False),
    ("PARAFUSO SEXTAVADO 1/4 X 2", "73181500", "CX", (2000, 6000), False),
    ("CIMENTO CP II 50KG", "25232910", "SC", (3000, 4500), False),
    ("CABO FLEXIVEL 2,5MM 100M", "85444900", "RL", (15000, 30000), False),
    ("TINTA ACRILICA FOSCA 18L", "32091010", "GL", (20000, 45000), False),
    ("PAPEL A4 75G 500 FOLHAS", "48025610", "PCT", (2500, 4000), False),
    ("CANETA ESFEROGRAFICA AZUL CX 50", "96081000", "CX", (1500, 4000), False),
    ("DETERGENTE LIQUIDO NEUTRO 500ML", "34022000", "UN", (200, 500), False),
    ("AGUA MINERAL S/ GAS 500ML FD 12", "22011000", "FD", (1000, 2500), False),
    ("FILE DE PEITO DE FRANGO CONG", "02071400", "KG", (1500, 2800), True),
    ("QUEIJO MUSSARELA FATIADO", "04069010", "KG", (3500, 5500), True),
    ("CARNE BOVINA PATINHO", "02013000", "KG", (3800, 5200), True),
    ("PNEU 175/70 R14 88T", "40111000", "UN", (25000, 45000), False),
    ("OLEO MOTOR 5W30 SINTETICO 1L", "27101932", "UN", (3000, 6000), False),
    ("CAMISETA ALGODAO GOLA C TAM M", "61091000", "UN", (2000, 6000), False),
    ("TENIS ESPORTIVO MASC N 42", "64041100", "PAR", (15000, 40000), False),
]

NATURES = ["VENDA DE MERCADORIA", "VENDA DE PRODUCAO DO ESTABELECIMENTO", "VENDA MERC. ADQ. DE TERCEIROS"]

ICMS_RATES = {True: Decimal("0.18"), False: Decimal("0.12")}  # intrastate, interstate

CENT = Decimal("0.01")


@dataclass
class Sample:
    gold: dict
    meta: dict
    image: Image.Image


def _money(value: Decimal) -> str:
    return br.format_number(value, 2)


def _address(fake: Faker, rng: random.Random, uf: str) -> dict:
    return {
        "street": fake.street_name(),
        "number": str(rng.randint(1, 4999)),
        "district": fake.bairro(),
        "city": fake.city(),
        "state": uf,
        "zip_code": f"{rng.randint(1_000_000, 99_999_999):08d}",
    }


def generate(seed: int) -> Sample:
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    fake.seed_instance(seed)

    issue = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 660))
    issuer_uf = rng.choice(list(br.UF_CODES))
    intrastate = rng.random() < 0.7
    recipient_uf = issuer_uf if intrastate else rng.choice([u for u in br.UF_CODES if u != issuer_uf])
    simples = rng.random() < 0.2  # Simples Nacional: no ICMS highlighted on the invoice

    issuer_cnpj = br.cnpj(rng)
    number, series = rng.randint(1, 999_999), rng.choice([1, 1, 1, 2, 3])
    outbound = rng.random() < 0.9
    issuer = {
        "name": fake.company().upper(),
        "cnpj": issuer_cnpj,
        "state_registration": f"{rng.randint(10**8, 10**9 - 1)}{rng.randint(100, 999)}",
        "address": _address(fake, rng, issuer_uf),
    }
    if rng.random() < 0.6:
        recipient = {"name": fake.company().upper(), "document": br.cnpj(rng)}
    else:
        recipient = {"name": fake.name().upper(), "document": br.cpf(rng)}
    recipient["address"] = _address(fake, rng, recipient_uf)

    # Blank boxes: the field exists on the form but is empty, so gold is null.
    absent = set()
    for field, p in (("district", 0.12), ("zip_code", 0.12)):
        if rng.random() < p:
            recipient["address"][field] = None
            absent.add(f"recipient.address.{field}")

    cfop = ("5" if intrastate else "6") + rng.choice(["102", "405"])
    rate = Decimal(0) if simples else ICMS_RATES[intrastate]
    items = []
    for product in rng.sample(PRODUCTS, rng.randint(1, 12)):
        description, ncm, unit, (low, high), by_weight = product
        quantity = (Decimal(rng.randint(250, 25000)) / 1000) if by_weight else Decimal(rng.choice([1, 1, 2, 3, 5, 6, 10, 12, 24]))
        unit_price = Decimal(rng.randint(low, high)) / 100
        total = (quantity * unit_price).quantize(CENT, ROUND_HALF_UP)
        items.append({
            "code": rng.choice([f"{rng.randint(1, 99999):05d}", f"PRD-{rng.randint(100, 9999)}", str(rng.randint(7890000000000, 7899999999999))]),
            "description": description,
            "ncm": ncm,
            "cfop": cfop,
            "unit": "KG" if by_weight else unit,
            "quantity": quantity,
            "unit_price": unit_price,
            "total": total,
        })

    products = sum((i["total"] for i in items), Decimal(0))
    freight = (Decimal(rng.randint(1500, 25000)) / 100) if rng.random() < 0.35 else Decimal(0)
    discount = (products * Decimal(rng.choice([1, 2, 3, 5])) / 100).quantize(CENT) if rng.random() < 0.25 else Decimal(0)
    icms_base = Decimal(0) if simples else products - discount
    icms = (icms_base * rate).quantize(CENT, ROUND_HALF_UP)
    invoice_total = products + freight - discount
    access_key = br.nfe_access_key(issuer_uf, issue.year, issue.month, issuer_cnpj, series, number, rng)

    gold = {
        "access_key": access_key,
        "number": str(number),
        "series": str(series),
        "issue_date": issue.isoformat(),
        "operation_type": "outbound" if outbound else "inbound",
        "issuer": issuer,
        "recipient": recipient,
        "items": [
            {
                **{k: item[k] for k in ("code", "description", "ncm", "cfop", "unit")},
                "quantity": format(item["quantity"].normalize(), "f"),
                "unit_price": str(item["unit_price"].quantize(CENT)),
                "total": str(item["total"]),
            }
            for item in items
        ],
        "totals": {
            "products": str(products),
            "icms_base": str(icms_base.quantize(CENT)),
            "icms": str(icms),
            "freight": str(freight.quantize(CENT)),
            "discount": str(discount.quantize(CENT)),
            "invoice_total": str(invoice_total.quantize(CENT)),
        },
    }

    page = _Page()
    _draw(page, rng, fake, gold, items, issue, rate, simples, outbound)
    return Sample(
        gold=gold,
        meta={
            "doc_type": DOC_TYPE,
            "seed": seed,
            "layout": "portrait",
            "items": len(items),
            "absent_fields": sorted(absent),
            "traps": [],
            "printed_text": page.printed,
        },
        image=page.finish(),
    )


# --- Drawing -------------------------------------------------------------------

WIDTH, MARGIN = 1654, 50  # A4 at 200 DPI
LABEL, VALUE, SMALL = 13, 19, 15


class _Page:
    def __init__(self):
        self.img = Image.new("RGB", (WIDTH, 2339), "white")
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN
        self.printed: list[str] = []

    def text(self, xy, text: str, size: int, bold: bool = False, fill: str = "#111111") -> None:
        if text:
            self.draw.text(xy, text, font=font("sans_bold" if bold else "sans", size), fill=fill)
            self.printed.append(text)

    def box(self, x: int, y: int, w: int, h: int, label: str, value: str = "", align: str = "left", bold: bool = False) -> None:
        self.draw.rectangle([x, y, x + w, y + h], outline="#222222", width=2)
        self.text((x + 6, y + 4), label, LABEL, fill="#333333")
        if value:
            fnt = font("sans_bold" if bold else "sans", VALUE)
            lines = wrap(self.draw, value, fnt, w - 12)
            for i, line in enumerate(lines[:2]):
                width = self.draw.textlength(line, font=fnt)
                x_text = x + w - 6 - width if align == "right" else x + 6
                self.text((x_text, y + 22 + i * (VALUE + 3)), line, VALUE, bold)

    def row(self, cells: list[tuple], height: int = 54) -> None:
        """cells: (fraction of width, label, value[, align])."""
        x, inner = MARGIN, WIDTH - 2 * MARGIN
        for i, cell in enumerate(cells):
            fraction, label, value, *rest = cell
            w = inner - (x - MARGIN) if i == len(cells) - 1 else int(inner * fraction)
            self.box(x, self.y, w, height, label, value, *(rest or ["left"]))
            x += w
        self.y += height

    def section(self, title: str) -> None:
        self.y += 8
        self.text((MARGIN, self.y), title, SMALL, bold=True)
        self.y += SMALL + 6

    def finish(self) -> Image.Image:
        return self.img.crop((0, 0, WIDTH, min(self.y + MARGIN, self.img.height)))


def _draw(p: _Page, rng: random.Random, fake: Faker, gold: dict, items: list[dict], issue: date,
          rate: Decimal, simples: bool, outbound: bool) -> None:
    issuer, recipient, totals = gold["issuer"], gold["recipient"], gold["totals"]
    inner = WIDTH - 2 * MARGIN
    padded = f"{int(gold['number']):09d}"
    number_display = f"{padded[:3]}.{padded[3:6]}.{padded[6:]}"
    series_display = f"{int(gold['series']):03d}"

    # Receipt stub.
    p.row([
        (0.82, f"RECEBEMOS DE {issuer['name']} OS PRODUTOS CONSTANTES DA NOTA FISCAL INDICADA AO LADO", ""),
        (0.18, "NF-e", f"Nº {number_display}  SÉRIE {series_display}"),
    ], 64)
    p.y += 14

    # Header: issuer, DANFE block, access key.
    top, height = p.y, 250
    a = issuer["address"]
    w1, w2 = int(inner * 0.40), int(inner * 0.20)
    w3 = inner - w1 - w2
    p.draw.rectangle([MARGIN, top, MARGIN + inner, top + height], outline="#222222", width=2)
    p.draw.line([MARGIN + w1, top, MARGIN + w1, top + height], fill="#222222", width=2)
    p.draw.line([MARGIN + w1 + w2, top, MARGIN + w1 + w2, top + height], fill="#222222", width=2)

    x = MARGIN + 12
    p.text((x, top + 12), "IDENTIFICAÇÃO DO EMITENTE", LABEL, fill="#333333")
    name_lines = wrap(p.draw, issuer["name"], font("sans_bold", 24), w1 - 24)
    y = top + 40
    for line in name_lines[:2]:
        p.text((x, y), line, 24, bold=True)
        y += 30
    for line in (f"{a['street']}, {a['number']}", f"{a['district']} - CEP {a['zip_code'][:5]}-{a['zip_code'][5:]}",
                 f"{a['city']} - {a['state']}", f"Fone: ({rng.randint(11, 99)}) {rng.randint(2000, 3999)}-{rng.randint(1000, 9999)}"):
        p.text((x, y + 6), line, SMALL + 1)
        y += 26

    x = MARGIN + w1 + 12
    p.text((x + 40, top + 14), "DANFE", 34, bold=True)
    p.text((x, top + 58), "Documento Auxiliar da", SMALL)
    p.text((x, top + 76), "Nota Fiscal Eletrônica", SMALL)
    p.text((x, top + 104), "0 - ENTRADA", SMALL)
    p.text((x, top + 124), "1 - SAÍDA", SMALL)
    p.draw.rectangle([x + 150, top + 104, x + 190, top + 142], outline="#222222", width=2)
    p.text((x + 162, top + 108), "1" if outbound else "0", 26, bold=True)
    p.text((x, top + 160), f"Nº {number_display}", VALUE, bold=True)
    p.text((x, top + 186), f"SÉRIE {series_display}", VALUE, bold=True)
    p.text((x, top + 212), "FOLHA 1/1", SMALL)

    x = MARGIN + w1 + w2 + 14
    bars_x, bar_y = x, top + 14
    while bars_x < MARGIN + inner - 20:  # decorative barcode
        width = rng.choice([2, 2, 3, 4])
        if rng.random() < 0.55:
            p.draw.rectangle([bars_x, bar_y, bars_x + width - 1, bar_y + 70], fill="#111111")
        bars_x += width
    p.text((x, top + 96), "CHAVE DE ACESSO", LABEL, fill="#333333")
    p.text((x, top + 116), br.format_access_key(gold["access_key"]), VALUE + 1, bold=True)
    p.text((x, top + 160), "Consulta de autenticidade no portal nacional da NF-e", SMALL - 1)
    p.text((x, top + 180), "www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora", SMALL - 1)
    p.y = top + height

    protocol = f"{br.UF_CODES[a['state']]}{rng.randint(10**12, 10**13 - 1)}"
    p.row([
        (0.6, "NATUREZA DA OPERAÇÃO", rng.choice(NATURES)),
        (0.4, "PROTOCOLO DE AUTORIZAÇÃO DE USO", f"{protocol} - {issue:%d/%m/%Y} {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"),
    ])
    p.row([
        (0.33, "INSCRIÇÃO ESTADUAL", issuer["state_registration"]),
        (0.33, "INSCRIÇÃO ESTADUAL DO SUBST. TRIBUT.", ""),
        (0.34, "CNPJ", br.format_cnpj(issuer["cnpj"])),
    ])

    p.section("DESTINATÁRIO / REMETENTE")
    r = recipient["address"]
    doc = recipient["document"]
    exit_date = issue + timedelta(days=rng.choice([0, 0, 1, 2]))
    p.row([
        (0.58, "NOME / RAZÃO SOCIAL", recipient["name"]),
        (0.25, "CNPJ / CPF", br.format_cnpj(doc) if len(doc) == 14 else br.format_cpf(doc)),
        (0.17, "DATA DA EMISSÃO", f"{issue:%d/%m/%Y}"),
    ])
    p.row([
        (0.45, "ENDEREÇO", f"{r['street']}, {r['number']}"),
        (0.25, "BAIRRO / DISTRITO", r["district"] or ""),
        (0.13, "CEP", f"{r['zip_code'][:5]}-{r['zip_code'][5:]}" if r["zip_code"] else ""),
        (0.17, "DATA DA SAÍDA/ENTRADA", f"{exit_date:%d/%m/%Y}"),
    ])
    p.row([
        (0.40, "MUNICÍPIO", r["city"]),
        (0.08, "UF", r["state"]),
        (0.20, "FONE / FAX", f"({rng.randint(11, 99)}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"),
        (0.17, "INSCRIÇÃO ESTADUAL", "" if len(doc) == 11 else f"{rng.randint(10**8, 10**9 - 1)}"),
        (0.15, "HORA DA SAÍDA", f"{rng.randint(7, 19):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"),
    ])

    # Installments: dates and values that are not the invoice total.
    total = Decimal(totals["invoice_total"])
    count = rng.choice([1, 2, 3])
    p.section("FATURA / DUPLICATAS")
    share = (total / count).quantize(CENT)
    cells = []
    for i in range(count):
        value = total - share * (count - 1) if i == count - 1 else share
        due = issue + timedelta(days=30 * (i + 1))
        cells.append((1 / count, f"Nº {i + 1:03d}   VENC. {due:%d/%m/%Y}", f"R$ {_money(value)}"))
    p.row(cells, 50)

    p.section("CÁLCULO DO IMPOSTO")
    m = lambda key: _money(Decimal(totals[key]))  # noqa: E731
    p.row([
        (0.2, "BASE DE CÁLC. DO ICMS", m("icms_base"), "right"),
        (0.2, "VALOR DO ICMS", m("icms"), "right"),
        (0.2, "BASE DE CÁLC. ICMS S.T.", "0,00", "right"),
        (0.2, "VALOR DO ICMS SUBST.", "0,00", "right"),
        (0.2, "VALOR TOTAL DOS PRODUTOS", m("products"), "right"),
    ])
    p.row([
        (1 / 6, "VALOR DO FRETE", m("freight"), "right"),
        (1 / 6, "VALOR DO SEGURO", "0,00", "right"),
        (1 / 6, "DESCONTO", m("discount"), "right"),
        (1 / 6, "OUTRAS DESPESAS", "0,00", "right"),
        (1 / 6, "VALOR DO IPI", "0,00", "right"),
        (1 / 6, "VALOR TOTAL DA NOTA", m("invoice_total"), "right", True),
    ])

    p.section("TRANSPORTADOR / VOLUMES TRANSPORTADOS")
    carrier = rng.random() < 0.6
    p.row([
        (0.40, "RAZÃO SOCIAL", fake.company().upper() if carrier else ""),
        (0.18, "FRETE POR CONTA", "0 - EMITENTE" if Decimal(totals["freight"]) else "9 - SEM FRETE"),
        (0.12, "PLACA DO VEÍCULO", f"{fake.license_plate()}" if carrier else ""),
        (0.06, "UF", rng.choice(list(br.UF_CODES)) if carrier else ""),
        (0.24, "CNPJ / CPF", br.format_cnpj(br.cnpj(rng)) if carrier else ""),
    ])

    p.section("DADOS DOS PRODUTOS / SERVIÇOS")
    columns = [
        ("CÓDIGO", 0.10, "left"), ("DESCRIÇÃO DO PRODUTO / SERVIÇO", 0.28, "left"), ("NCM/SH", 0.07, "left"),
        ("CST", 0.04, "left"), ("CFOP", 0.05, "left"), ("UN", 0.04, "left"), ("QUANT.", 0.08, "right"),
        ("V. UNITÁRIO", 0.09, "right"), ("V. TOTAL", 0.09, "right"), ("BC ICMS", 0.08, "right"), ("V. ICMS", 0.08, "right"),
    ]
    widths = [int(inner * c[1]) for c in columns]
    widths[-1] = inner - sum(widths[:-1])
    row_h = 30
    header_top = p.y
    x = MARGIN
    for (title, _, _), w in zip(columns, widths):
        p.draw.rectangle([x, p.y, x + w, p.y + row_h], outline="#222222", width=2)
        p.text((x + 4, p.y + 8), title, LABEL - 1, bold=True)
        x += w
    p.y += row_h
    cst = "101" if simples else rng.choice(["000", "000", "020"])
    for item in items:
        bc = Decimal(0) if simples else item["total"]
        cells = [
            item["code"], item["description"], item["ncm"], cst, item["cfop"], item["unit"],
            br.format_number(item["quantity"], 4), br.format_number(item["unit_price"], 2),
            _money(item["total"]), _money(bc), _money((bc * rate).quantize(CENT, ROUND_HALF_UP)),
        ]
        x = MARGIN
        for value, (_, _, align), w in zip(cells, columns, widths):
            fnt = font("sans", SMALL)
            width = p.draw.textlength(value, font=fnt)
            p.text((x + w - 5 - width if align == "right" else x + 4, p.y + 7), value, SMALL)
            x += w
        p.y += row_h
    p.draw.rectangle([MARGIN, header_top, MARGIN + inner, p.y], outline="#222222", width=2)

    p.section("DADOS ADICIONAIS")
    notes = [f"Pedido nº {rng.randint(1000, 99999)}. Vendedor: {fake.first_name()}."]
    if simples:
        notes.append("DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL. NÃO GERA DIREITO A CRÉDITO FISCAL DE IPI.")
    notes.append(f"Valor aproximado dos tributos: R$ {_money((Decimal(totals['invoice_total']) * Decimal('0.31')).quantize(CENT))} (Fonte: IBPT).")
    p.row([(1.0, "INFORMAÇÕES COMPLEMENTARES", " ".join(notes))], 80)
