"""Testes unitários para o repositório Firestore (app.repositories.firestore_repository)."""

from unittest.mock import MagicMock, patch
import pytest

from app.models.product import PrecoPorTipoCliente, Produto, TipoCliente, VariacaoProduto
from app.repositories.firestore_repository import FirestoreProductRepository


def produto_exemplo(produto_id: str = "prod_123", sku_base: str = "SKU-FIRE-01") -> Produto:
    return Produto(
        produto_id=produto_id,
        sku_base=sku_base,
        nome="Produto Firestore",
        descricao="Descricao Firestore",
        categoria="Categoria F",
        variacoes=[
            VariacaoProduto(
                sku_variacao=f"{sku_base}-V1",
                atributos={"cor": "azul"},
                estoque_disponivel=10,
            )
        ],
        precos=[
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2C, preco_unitario=100.0)
        ],
    )


@patch("google.cloud.firestore.Client")
def test_firestore_save(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_doc = MagicMock()
    mock_db.collection.return_value.document.return_value = mock_doc

    repo = FirestoreProductRepository()
    prod = produto_exemplo()
    salvo = repo.save(prod)

    assert salvo.produto_id == prod.produto_id
    mock_doc.set.assert_called_once()


@patch("google.cloud.firestore.Client")
def test_firestore_get_by_id_found(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc_snapshot = MagicMock()
    mock_doc_snapshot.exists = True
    prod = produto_exemplo()
    mock_doc_snapshot.to_dict.return_value = prod.model_dump(mode="json")
    mock_doc.get.return_value = mock_doc_snapshot
    mock_db.collection.return_value.document.return_value = mock_doc

    repo = FirestoreProductRepository()
    resultado = repo.get_by_id("prod_123")

    assert resultado is not None
    assert resultado.produto_id == "prod_123"
    assert resultado.sku_base == "SKU-FIRE-01"


@patch("google.cloud.firestore.Client")
def test_firestore_get_by_id_not_found(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_doc = MagicMock()
    mock_doc_snapshot = MagicMock()
    mock_doc_snapshot.exists = False
    mock_doc.get.return_value = mock_doc_snapshot
    mock_db.collection.return_value.document.return_value = mock_doc

    repo = FirestoreProductRepository()
    resultado = repo.get_by_id("prod_404")

    assert resultado is None


@patch("google.cloud.firestore.Client")
def test_firestore_list_active(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_query = MagicMock()
    mock_db.collection.return_value.where.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query

    prod = produto_exemplo()
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = prod.model_dump(mode="json")
    mock_query.stream.return_value = [mock_doc1]

    repo = FirestoreProductRepository()
    resultado = repo.list_active(limit=10, offset=0, categoria="Categoria F")

    assert len(resultado) == 1
    assert resultado[0].produto_id == "prod_123"


@patch("google.cloud.firestore.Client")
def test_firestore_check_sku_exists_base(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_query = MagicMock()
    mock_db.collection.return_value.where.return_value = mock_query
    mock_query.limit.return_value = mock_query

    mock_doc = MagicMock()
    mock_doc.id = "prod_999"
    mock_query.stream.return_value = [mock_doc]

    repo = FirestoreProductRepository()
    found = repo.check_sku_exists("SKU-BASE-EXISTE", ["VAR-1"])

    assert found == "SKU-BASE-EXISTE"


@patch("google.cloud.firestore.Client")
def test_firestore_check_sku_exists_variacao(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_query_base = MagicMock()
    mock_db.collection.return_value.where.return_value = mock_query_base
    mock_query_base.limit.return_value = mock_query_base
    mock_query_base.stream.return_value = []  # Nao achou por sku_base query

    prod_doc_dict = {
        "sku_base": "SKU-OUTRO",
        "variacoes": [{"sku_variacao": "SKU-VAR-EXISTE", "atributos": {}, "estoque_disponivel": 5}],
    }
    mock_doc = MagicMock()
    mock_doc.id = "prod_888"
    mock_doc.to_dict.return_value = prod_doc_dict
    mock_db.collection.return_value.stream.return_value = [mock_doc]

    repo = FirestoreProductRepository()
    found = repo.check_sku_exists("SKU-NOVO", ["SKU-VAR-EXISTE"])

    assert found == "SKU-VAR-EXISTE"


@patch("google.cloud.firestore.Client")
def test_firestore_check_sku_exists_none(mock_client_cls: MagicMock) -> None:
    mock_db = MagicMock()
    mock_client_cls.return_value = mock_db
    mock_query_base = MagicMock()
    mock_db.collection.return_value.where.return_value = mock_query_base
    mock_query_base.limit.return_value = mock_query_base
    mock_query_base.stream.return_value = []

    mock_db.collection.return_value.stream.return_value = []

    repo = FirestoreProductRepository()
    found = repo.check_sku_exists("SKU-INEXISTENTE", ["SKU-VAR-INEXISTENTE"])

    assert found is None
