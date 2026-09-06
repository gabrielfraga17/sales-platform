"""Testes para os repositórios do Carrinho de Compras."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.cart import Carrinho, ItemCarrinho
from app.models.product import TipoCliente
from app.repositories.cart_firestore_repository import FirestoreCartRepository, InMemoryCartRepository


def test_in_memory_cart_repository_save_and_get():
    repo = InMemoryCartRepository()
    now = datetime.now(timezone.utc)
    carrinho = Carrinho(
        carrinho_id="cart_repo_1",
        tipo_cliente=TipoCliente.B2C,
        itens=[],
        criado_em=now,
        atualizado_em=now,
    )

    repo.save(carrinho)
    res = repo.get_by_id("cart_repo_1")
    assert res is not None
    assert res.carrinho_id == "cart_repo_1"

    assert repo.get_by_id("cart_inexistente") is None


@patch("google.cloud.firestore.Client")
def test_firestore_cart_repository(mock_firestore_client):
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc_snap = MagicMock()

    mock_firestore_client.return_value = mock_db
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc_ref

    repo = FirestoreCartRepository()

    now = datetime.now(timezone.utc)
    carrinho = Carrinho(
        carrinho_id="cart_fs_1",
        tipo_cliente=TipoCliente.B2B,
        itens=[
            ItemCarrinho(
                produto_id="p1",
                sku_variacao="s1",
                nome_produto="P1",
                quantidade=1,
                preco_unitario=100.0,
            )
        ],
        criado_em=now,
        atualizado_em=now,
    )

    # Save test
    repo.save(carrinho)
    mock_doc_ref.set.assert_called_once()

    # Get_by_id test (encontrado)
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_snap.exists = True
    mock_doc_snap.to_dict.return_value = carrinho.model_dump(mode="json")

    res = repo.get_by_id("cart_fs_1")
    assert res is not None
    assert res.carrinho_id == "cart_fs_1"

    # Get_by_id test (não encontrado)
    mock_doc_snap.exists = False
    assert repo.get_by_id("cart_fs_99") is None
