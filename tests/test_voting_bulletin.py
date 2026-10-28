import pytest

from papelada.cli import validator
from papelada.doctypes import voting_bulletin

SEEDS = range(20)


@pytest.fixture(scope="module")
def samples():
    return [voting_bulletin.generate(seed) for seed in SEEDS]


def test_gold_matches_schema(samples):
    check = validator(voting_bulletin.DOC_TYPE)
    for sample in samples:
        assert list(check.iter_errors(sample.gold)) == [], sample.meta["seed"]


def test_totals_are_consistent(samples):
    for sample in samples:
        gold = sample.gold
        assert gold["eligible_voters"] == gold["turnout"] + gold["absent"]
        for contest in gold["contests"]:
            votes = sum(c["votes"] for c in contest["candidates"]) + sum(p["votes"] for p in contest["party_votes"])
            assert votes + contest["blank"] + contest["null_votes"] == contest["total"] == gold["turnout"]
            assert all(c["votes"] >= 1 for c in contest["candidates"])


def test_rounds_and_offices(samples):
    rounds = {s.gold["round"] for s in samples}
    assert rounds == {1, 2}
    for sample in samples:
        offices = [c["office"] for c in sample.gold["contests"]]
        if sample.gold["round"] == 2:
            assert offices[-1] == "Presidente" and all(len(c["candidates"]) == 2 for c in sample.gold["contests"])
        else:
            assert len(offices) == 5
        for contest in sample.gold["contests"]:
            numbers = [c["number"] for c in contest["candidates"]]
            assert len(numbers) == len(set(numbers))
            # Party-only votes exist only in proportional contests.
            assert bool(contest["party_votes"]) == contest["office"].startswith("Deputado")


def test_gold_is_printed_and_traps_exist(samples):
    for sample in samples:
        page = "\n".join(sample.meta["printed_text"])
        assert sample.gold["state"] in sample.meta["printed_text"]  # the UF is printed, not only the state name
        for contest in sample.gold["contests"]:
            for c in contest["candidates"]:
                assert f"{c['number']} {c['name']}" in page
    assert sum(len(s.meta["traps"]) for s in samples) > len(samples)


def test_deterministic():
    a, b = voting_bulletin.generate(3), voting_bulletin.generate(3)
    assert a.gold == b.gold and a.image.tobytes() == b.image.tobytes()
