"""Testes unitários para os modelos Pydantic do Carrinho."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.cart import Carrinho, ElegibilidadeCheckout, ItemCarrinho
from app.models.product import TipoCliente


def test_item_carrinho_calculo_subtotal():
    """Testa se o subtotal do ItemCarrinho é calculado e arredondado corretamente."""
    item = ItemCarrinho(
        produto_id="prod_123",
        sku_variacao="SKU-TEST-1",
        nome_produto="Produto Teste",
        quantidade=3,
        preco_unitario=19.99,
    )
    assert item.subtotal == 59.97


def test_item_carrinho_quantidade_invalida():
    """Testa se quantidade <= 0 lança erro de validação."""
    with pytest.raises(ValidationError):
        ItemCarrinho(
            produto_id="prod_123",
            sku_variacao="SKU-TEST-1",
            nome_produto="Produto Teste",
            quantidade=0,
            preco_unitario=19.99,
        )


def test_carrinho_calculo_total():
    """Testa se o total do Carrinho soma corretamente todos os subtotais."""
    now = datetime.now(timezone.utc)
    item1 = ItemCarrinho(
        produto_id="p1",
        sku_variacao="sku1",
        nome_produto="P1",
        quantidade=2,
        preco_unitario=10.00,
    )  # subtotal 20.00
    item2 = ItemCarrinho(
        produto_id="p2",
        sku_variacao="sku2",
        nome_produto="P2",
        quantidade=1,
        preco_unitario=35.50,
    )  # subtotal 35.50

    carrinho = Carrinho(
        carrinho_id="cart_1",
        tipo_cliente=TipoCliente.B2C,
        itens=[item1, item2],
        criado_em=now,
        atualizado_em=now,
    )
    assert carrinho.total == 55.50


def test_carrinho_vazio_total_zero():
    """Testa se um carrinho sem itens tem total 0.0."""
    now = datetime.now(timezone.utc)
    carrinho = Carrinho(
        carrinho_id="cart_empty",
        tipo_cliente=TipoCliente.B2B,
        itens=[],
        criado_em=now,
        atualizado_em=now,
    )
    assert carrinho.total == 0.0


def test_elegibilidade_checkout_model():
    """Testa instanciação do modelo ElegibilidadeCheckout."""
    elegivel = ElegibilidadeCheckout(elegivel=True, total=400.00)
    assert elegivel.elegivel is True
    assert elegivel.motivo is None

    nao_elegivel = ElegibilidadeCheckout(
        elegivel=False,
        total=200.00,
        motivo="Pedido mínimo B2B de R$350,00 não atingido",
        valor_faltante_moq=150.00,
    )
    assert nao_elegivel.elegivel is False
    assert nao_elegivel.valor_faltante_moq == 150.00
