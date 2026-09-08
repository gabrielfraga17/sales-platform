"""Testes adicionais para FirestoreOrderRepository e rotas auxiliares."""

import pytest
from unittest.mock import MagicMock, patch
from app.models.cart import Carrinho, ItemCarrinho
from app.models.order import DadosComprador, EnderecoEntrega, ItemPedido, Pedido, StatusPedido
from app.models.product import TipoCliente
from datetime import datetime, timezone
from app.repositories.order_firestore_repository import FirestoreOrderRepository, BaseOrderRepository


def test_base_order_repository_abstract_methods():
    class DummyOrderRepo(BaseOrderRepository):
        pass

    with pytest.raises(TypeError):
        DummyOrderRepo()


@patch("google.cloud.firestore.Client")
def test_firestore_order_repository_save_and_get(mock_firestore_client):
    mock_db = MagicMock()
    mock_firestore_client.return_value = mock_db
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref

    repo = FirestoreOrderRepository()

    comprador = DadosComprador(nome="A", email="a@a.com", telefone="11")
    endereco = EnderecoEntrega(destinatario="A", logradouro="L", numero="1", bairro="B", cidade="C", estado="SP", cep="00")
    now = datetime.now(timezone.utc)
    pedido = Pedido(
        pedido_id="ped_1",
        carrinho_id="cart_1",
        tipo_cliente=TipoCliente.B2C,
        comprador=comprador,
        endereco_entrega=endereco,
        itens=[],
        total=0.0,
        status=StatusPedido.AGUARDANDO_PAGAMENTO,
        criado_em=now,
    )

    # Save
    repo.save_order(pedido)
    mock_doc_ref.set.assert_called_once()

    # Get found
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = pedido.model_dump(mode="json")
    mock_doc_ref.get.return_value = mock_doc

    res = repo.get_order_by_id("ped_1")
    assert res is not None
    assert res.pedido_id == "ped_1"

    # Get not found
    mock_doc_not_found = MagicMock()
    mock_doc_not_found.exists = False
    mock_doc_ref.get.return_value = mock_doc_not_found
    assert repo.get_order_by_id("ped_inexistente") is None


@patch("google.cloud.firestore.Client")
def test_firestore_order_repository_execute_transaction(mock_firestore_client):
    mock_db = MagicMock()
    mock_firestore_client.return_value = mock_db

    repo = FirestoreOrderRepository()

    carrinho = MagicMock()
    carrinho.carrinho_id = "cart_1"
    carrinho.itens = []

    pedido = MagicMock()
    pedido.pedido_id = "ped_1"

    # Mock @firestore.transactional behavior
    with patch("google.cloud.firestore.transactional", lambda fn: fn):
        success, skus = repo.execute_checkout_transaction(
            carrinho=carrinho,
            pedido=pedido,
            cart_repository=MagicMock(),
            product_repository=MagicMock(),
        )
        assert success is True
        assert skus == []
