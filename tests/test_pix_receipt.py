import numpy as np
import pytest

from papelada.cli import validator
from papelada.degrade import LEVELS, degrade
from papelada.doctypes import pix_receipt

SEEDS = range(40)


@pytest.fixture(scope="module")
def samples():
    return [pix_receipt.generate(seed) for seed in SEEDS]


def test_gold_matches_schema(samples):
    check = validator(pix_receipt.DOC_TYPE)
    for sample in samples:
        assert list(check.iter_errors(sample.gold)) == [], sample.meta


def test_absent_fields_are_null(samples):
    for sample in samples:
        for path in sample.meta["absent_fields"]:
            node = sample.gold
            for key in path.split("."):
                node = node[key]
            assert node is None, (sample.meta["seed"], path)


def test_every_layout_and_absence_is_exercised(samples):
    assert {s.meta["layout"] for s in samples} == set(pix_receipt.LAYOUTS)
    # The hallucination metric needs absent optional fields in the set.
    assert sum(len(s.meta["absent_fields"]) for s in samples) > len(samples)


def test_end_to_end_id_embeds_datetime(samples):
    for sample in samples:
        e2e, dt = sample.gold["end_to_end_id"], sample.gold["datetime"]
        if e2e and dt:
            assert e2e[9:21] == dt[:16].replace("-", "").replace("T", "").replace(":", "")


def test_deterministic():
    a, b = pix_receipt.generate(7), pix_receipt.generate(7)
    assert a.gold == b.gold
    assert a.image.tobytes() == b.image.tobytes()


def test_degradation_levels_run():
    sample = pix_receipt.generate(3)
    for index, level in enumerate(LEVELS):
        image = degrade(sample.image, level, np.random.default_rng([3, index]))
        assert image.mode == "RGB" and min(image.size) > 200
