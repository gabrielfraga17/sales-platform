"""Testes unitários para os modelos Pydantic (app.models.product)."""

import pytest
from pydantic import ValidationError

from app.models.product import PrecoPorTipoCliente, Produto, ProdutoCreate, TipoCliente, VariacaoProduto


def payload_base_valido() -> dict:
    return {
        "sku_base": "GUIA-01",
        "nome": "Guia de Miçangas",
        "descricao": "Guia ritualística",
        "pilar_conteudo": "Estilo & Modaxé",
        "categoria": "Guias",
        "variacoes": [
            {
                "sku_variacao": "GUIA-01-AZUL",
                "atributos": {"cor": "azul"},
                "estoque_disponivel": 10,
            }
        ],
        "precos": [
            {
                "tipo_cliente": "b2c",
                "preco_unitario": 50.0,
            },
            {
                "tipo_cliente": "b2b",
                "preco_unitario": 20.0,
                "margem_minima_revenda_pct": 150.0,
            },
        ],
    }


def test_modelo_produto_valido() -> None:
    data = payload_base_valido()
    produto = ProdutoCreate(**data)
    assert produto.sku_base == "GUIA-01"
    assert len(produto.precos) == 2


def test_modelo_produto_sem_preco_b2c_deve_falhar() -> None:
    data = payload_base_valido()
    data["precos"] = [
        {
            "tipo_cliente": "b2b",
            "preco_unitario": 20.0,
            "margem_minima_revenda_pct": 150.0,
        }
    ]
    with pytest.raises(ValidationError) as exc:
        ProdutoCreate(**data)
    assert "exatamente um preço para tipo_cliente=B2C" in str(exc.value)


def test_modelo_produto_com_multiplos_precos_b2c_deve_falhar() -> None:
    data = payload_base_valido()
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 50.0},
        {"tipo_cliente": "b2c", "preco_unitario": 60.0},
    ]
    with pytest.raises(ValidationError) as exc:
        ProdutoCreate(**data)
    assert "exatamente um preço para tipo_cliente=B2C" in str(exc.value)


def test_modelo_produto_b2b_sem_margem_deve_falhar() -> None:
    data = payload_base_valido()
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 50.0},
        {"tipo_cliente": "b2b", "preco_unitario": 20.0, "margem_minima_revenda_pct": None},
    ]
    with pytest.raises(ValidationError) as exc:
        ProdutoCreate(**data)
    assert "margem_minima_revenda_pct é obrigatório" in str(exc.value)


def test_modelo_produto_b2b_com_margem_menor_que_100_deve_falhar() -> None:
    data = payload_base_valido()
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 50.0},
        {"tipo_cliente": "b2b", "preco_unitario": 20.0, "margem_minima_revenda_pct": 99.9},
    ]
    with pytest.raises(ValidationError) as exc:
        ProdutoCreate(**data)
    assert "Margem mínima de revenda B2B deve ser >= 100.0" in str(exc.value)


def test_variacao_produto_estoque_negativo_deve_falhar() -> None:
    data = payload_base_valido()
    data["variacoes"][0]["estoque_disponivel"] = -1
    with pytest.raises(ValidationError):
        ProdutoCreate(**data)
