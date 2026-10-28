from papelada.doctypes.pix_receipt import FIELD_KINDS
from papelada.score import parse_json, score_fields

GOLD = {
    "amount": "1331.56",
    "datetime": "2025-11-23T16:01",
    "end_to_end_id": "E31872495202511231601uNO6n9JEC3H",
    "description": None,
    "payer": {"name": "Mariah Aparecida", "document": "***.475.938-**", "institution": "Banco Aurora S.A.",
              "agency": "5410", "account": "63370922-8"},
    "payee": {"name": "Thomas Mendonça", "document": None, "institution": "Cooperativa de Crédito Sertão",
              "agency": None, "account": None},
    "payee_key": "+55 11 91234-5678",
}


def buckets(pred):
    return {f["path"]: f["bucket"] for f in score_fields(GOLD, pred, FIELD_KINDS)}


def test_formatting_differences_are_forgiven():
    pred = {
        "amount": "R$ 1.331,56",
        "datetime": "2025-11-23T16:01:00",
        "end_to_end_id": "E31872495202511231601uNO6n9JEC3H",
        "payer": {"name": "MARIAH APARECIDA", "document": "***475938**", "institution": "Banco Aurora S.A.",
                  "agency": "5410", "account": "633709228"},
        "payee": {"name": "Thomas  Mendonça", "institution": "Cooperativa de Crédito Sertão"},
        "payee_key": "+5511912345678",
    }
    assert set(buckets(pred).values()) == {"correct"}


def test_buckets():
    pred = {
        "amount": 1331.65,
        "end_to_end_id": "e31872495202511231601uno6n9jec3h",  # case matters for the E2E ID
        "description": "conta de luz",
        "payee": {"document": "***.123.456-**", "name": "Thomas Mendonca"},
    }
    result = buckets(pred)
    assert result["amount"] == "wrong"
    assert result["end_to_end_id"] == "wrong"
    assert result["datetime"] == "omission"
    assert result["description"] == "hallucination"
    assert result["payee.document"] == "hallucination"
    assert result["payee.agency"] == "correct"
    assert result["payee.name"] == "wrong"


def test_lenient_ignores_accents():
    fields = score_fields(GOLD, {"payee": {"name": "Thomas Mendonca"}}, FIELD_KINDS)
    name = next(f for f in fields if f["path"] == "payee.name")
    assert name["bucket"] == "wrong" and name["lenient_correct"]


def test_parse_json():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here it is: {"a": {"b": null}} done') == {"a": {"b": None}}
    assert parse_json("no json") is None
    assert parse_json(None) is None
