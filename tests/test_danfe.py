from decimal import Decimal

import numpy as np
import pytest

from papelada import br
from papelada.cli import validator
from papelada.degrade import degrade
from papelada.doctypes import danfe

SEEDS = range(15)


@pytest.fixture(scope="module")
def samples():
    return [danfe.generate(seed) for seed in SEEDS]


def test_gold_matches_schema(samples):
    check = validator(danfe.DOC_TYPE)
    for sample in samples:
        assert list(check.iter_errors(sample.gold)) == [], sample.meta["seed"]


def test_documents_are_valid(samples):
    for sample in samples:
        gold = sample.gold
        assert br.is_valid_nfe_access_key(gold["access_key"])
        assert br.is_valid_cnpj(gold["issuer"]["cnpj"])
        doc = gold["recipient"]["document"]
        assert br.is_valid_cnpj(doc) if len(doc) == 14 else br.is_valid_cpf(doc)
        # The key embeds the issuer CNPJ, the series and the number.
        key = gold["access_key"]
        assert key[6:20] == gold["issuer"]["cnpj"]
        assert int(key[22:25]) == int(gold["series"]) and int(key[25:34]) == int(gold["number"])


def test_totals_add_up(samples):
    for sample in samples:
        items, totals = sample.gold["items"], sample.gold["totals"]
        for item in items:
            expected = (Decimal(item["quantity"]) * Decimal(item["unit_price"])).quantize(Decimal("0.01"))
            assert abs(expected - Decimal(item["total"])) <= Decimal("0.01")
        assert sum(Decimal(i["total"]) for i in items) == Decimal(totals["products"])
        assert Decimal(totals["invoice_total"]) == (
            Decimal(totals["products"]) + Decimal(totals["freight"]) - Decimal(totals["discount"])
        )


def test_gold_values_are_printed(samples):
    """Every non-null gold string must appear on the page in some form."""
    for sample in samples:
        page = " ".join(sample.meta["printed_text"]).replace(".", "").replace("-", "").replace(" ", "")
        gold = sample.gold
        assert gold["access_key"] in page
        assert gold["issuer"]["cnpj"] in page
        for item in gold["items"]:
            assert item["ncm"] in page and item["description"].replace(" ", "").replace(".", "").replace("-", "") in page


def test_deterministic_and_degradable():
    a, b = danfe.generate(5), danfe.generate(5)
    assert a.gold == b.gold and a.image.tobytes() == b.image.tobytes()
    assert degrade(a.image, "L2", np.random.default_rng(0)).mode == "RGB"
