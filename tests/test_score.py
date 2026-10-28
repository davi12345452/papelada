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


def test_misattribution_needs_the_text_on_the_page():
    printed = ["Descrição", "OBRIGADO PELA PREFERENCIA", "***.475.938-**"]
    fields = score_fields(GOLD, {"description": "Obrigado pela preferência", "payee": {"document": "***475938**"}},
                          FIELD_KINDS, printed)
    result = {f["path"]: f["bucket"] for f in fields}
    assert result["description"] == "misattribution"  # the footer, even with an added accent
    assert result["payee.document"] == "misattribution"  # payer's CPF in the payee's field
    fields = score_fields(GOLD, {"description": "pix enviado com sucesso"}, FIELD_KINDS, printed)
    assert next(f for f in fields if f["path"] == "description")["bucket"] == "hallucination"


def test_tables_and_numbers():
    from papelada.doctypes.danfe import FIELD_KINDS as DANFE_KINDS

    gold = {"number": "12345", "items": [{"quantity": "12.345", "total": "10.00"}, {"quantity": "2", "total": "5.50"}]}
    pred = {"number": "000.012.345", "items": [{"quantity": "12,3450", "total": "10"}, {"quantity": 2.0, "total": "R$ 5,50"},
                                              {"quantity": "1", "total": "1.00"}]}
    fields = score_fields(gold, pred, DANFE_KINDS)
    buckets = [f["bucket"] for f in fields]
    assert buckets == ["correct"] * 5 + ["extra_row"]
    pred["items"][0]["quantity"] = "12345"
    assert score_fields(gold, pred, DANFE_KINDS)[1]["bucket"] == "wrong"


def test_long_digit_strings_on_the_page_do_not_break_scoring():
    from papelada.doctypes.danfe import FIELD_KINDS as DANFE_KINDS

    key = "3526" * 11
    printed = [key, "3526 1011 2223 3300 0181 5500 1000 0123 4511 8034 0633", "1" * 60]
    gold = {"totals": {"freight": None, "discount": "0.00"}}
    fields = score_fields(gold, {"totals": {"freight": "12.50", "discount": "0,00"}}, DANFE_KINDS, printed)
    assert [f["bucket"] for f in fields] == ["hallucination", "correct"]
