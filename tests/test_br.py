import random

from papelada import br


def test_known_valid_documents():
    assert br.is_valid_cpf("529.982.247-25")
    assert br.is_valid_cnpj("11.222.333/0001-81")
    assert not br.is_valid_cpf("529.982.247-24")
    assert not br.is_valid_cpf("111.111.111-11")


def test_generated_documents_are_valid():
    rng = random.Random(0)
    for _ in range(500):
        assert br.is_valid_cpf(br.cpf(rng))
        assert br.is_valid_cnpj(br.cnpj(rng))


def test_formats():
    assert br.format_cpf("52998224725") == "529.982.247-25"
    assert br.mask_cpf("52998224725") == "***.982.247-**"
    assert br.format_cnpj("11222333000181") == "11.222.333/0001-81"
    assert br.brl(123456789) == "R$ 1.234.567,89"
    assert br.brl(5) == "R$ 0,05"
    assert br.decimal_str(123456789) == "1234567.89"
