"""Testes unitários para os modelos Pydantic de Checkout e Pedido."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.order import (
    DadosComprador,
    EnderecoEntrega,
    FinalizarCheckoutRequest,
    ItemPedido,
    Pedido,
    StatusPedido,
)
from app.models.product import TipoCliente


def test_endereco_entrega_valido():
    endereco = EnderecoEntrega(
        destinatario="Maria Silva",
        logradouro="Rua das Flores",
        numero="123",
        complemento="Apt 101",
        bairro="Centro",
        cidade="Rio de Janeiro",
        estado="RJ",
        cep="20000-000",
    )
    assert endereco.destinatario == "Maria Silva"
    assert endereco.estado == "RJ"


def test_endereco_entrega_estado_invalido():
    with pytest.raises(ValidationError):
        EnderecoEntrega(
            destinatario="Maria Silva",
            logradouro="Rua das Flores",
            numero="123",
            bairro="Centro",
            cidade="Rio de Janeiro",
            estado="RJO",  # > 2 chars
            cep="20000-000",
        )


def test_dados_comprador_email_invalido():
    with pytest.raises(ValidationError):
        DadosComprador(
            nome="João",
            email="email-invalido",
            telefone="11999999999",
        )


def test_item_pedido_subtotal():
    item = ItemPedido(
        produto_id="prod_1",
        sku_variacao="SKU-1",
        nome_produto="Colar",
        quantidade=3,
        preco_unitario=29.90,
    )
    assert item.subtotal == round(3 * 29.90, 2)


def test_pedido_model():
    comprador = DadosComprador(
        nome="Carlos",
        email="carlos@example.com",
        telefone="21988887777",
    )
    endereco = EnderecoEntrega(
        destinatario="Carlos",
        logradouro="Av Brasil",
        numero="500",
        bairro="Caju",
        cidade="Rio de Janeiro",
        estado="RJ",
        cep="20930-000",
    )
    item = ItemPedido(
        produto_id="p1",
        sku_variacao="SKU-1",
        nome_produto="Pulseira",
        quantidade=2,
        preco_unitario=50.0,
    )
    now = datetime.now(timezone.utc)
    pedido = Pedido(
        pedido_id="ped_123",
        carrinho_id="cart_123",
        tipo_cliente=TipoCliente.B2C,
        comprador=comprador,
        endereco_entrega=endereco,
        itens=[item],
        total=100.0,
        status=StatusPedido.AGUARDANDO_PAGAMENTO,
        criado_em=now,
    )
    assert pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO
    assert pedido.total == 100.0
