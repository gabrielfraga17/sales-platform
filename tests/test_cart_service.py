"""Testes unitários para o CartService e regras de negócio do Carrinho."""

from datetime import datetime, timezone
import pytest

from app.models.product import PrecoPorTipoCliente, Produto, TipoCliente, VariacaoProduto
from app.repositories.cart_firestore_repository import InMemoryCartRepository
from app.repositories.firestore_repository import InMemoryProductRepository
from app.services.cart_service import (
    CartItemNotFoundError,
    CartNotFoundError,
    CartService,
    InsufficientStockError,
)
from app.services.product_service import ProductService


@pytest.fixture
def product_service():
    repo = InMemoryProductRepository()
    service = ProductService(repository=repo)
    return service, repo


@pytest.fixture
def cart_service(product_service):
    prod_svc, _ = product_service
    cart_repo = InMemoryCartRepository()
    return CartService(cart_repository=cart_repo, product_service=prod_svc), cart_repo, prod_svc


def _criar_produto_exemplo(prod_svc: ProductService, prod_id: str = "prod_1", estoque: int = 10, preco_b2c: float = 100.0, preco_b2b: float = 80.0):
    now = datetime.now(timezone.utc)
    produto = Produto(
        produto_id=prod_id,
        sku_base=f"BASE-{prod_id}",
        nome=f"Produto {prod_id}",
        descricao="Descrição do produto",
        categoria="Acessórios",
        variacoes=[
            VariacaoProduto(
                sku_variacao=f"SKU-{prod_id}-VAR1",
                atributos={"cor": "azul"},
                estoque_disponivel=estoque,
            )
        ],
        precos=[
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2C, preco_unitario=preco_b2c),
            PrecoPorTipoCliente(
                tipo_cliente=TipoCliente.B2B,
                preco_unitario=preco_b2b,
                margem_minima_revenda_pct=100.0,
            ),
        ],
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )
    prod_svc.repository.save(produto)
    return produto


def test_criar_carrinho(cart_service):
    svc, _, _ = cart_service
    carrinho_b2c = svc.create_cart(TipoCliente.B2C)
    assert carrinho_b2c.carrinho_id.startswith("cart_")
    assert carrinho_b2c.tipo_cliente == TipoCliente.B2C
    assert len(carrinho_b2c.itens) == 0

    carrinho_b2b = svc.create_cart(TipoCliente.B2B)
    assert carrinho_b2b.tipo_cliente == TipoCliente.B2B


def test_obter_carrinho_inexistente_lança_erro(cart_service):
    svc, _, _ = cart_service
    with pytest.raises(CartNotFoundError):
        svc.get_cart("cart_inexistente")


def test_regra_1_e_2_preco_vem_do_catalogo_e_por_tipo_cliente(cart_service):
    """
    Regra 1: Tipo de cliente é definido na criação (b2c/b2b).
    Regra 2: Preço é obtido do Catálogo dinamicamente para o tipo_cliente do carrinho.
    """
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_p", estoque=20, preco_b2c=150.0, preco_b2b=100.0)

    cart_b2c = svc.create_cart(TipoCliente.B2C)
    cart_b2c = svc.add_item(cart_b2c.carrinho_id, prod.produto_id, "SKU-prod_p-VAR1", quantidade=2)
    assert cart_b2c.itens[0].preco_unitario == 150.0
    assert cart_b2c.total == 300.0

    cart_b2b = svc.create_cart(TipoCliente.B2B)
    cart_b2b = svc.add_item(cart_b2b.carrinho_id, prod.produto_id, "SKU-prod_p-VAR1", quantidade=2)
    assert cart_b2b.itens[0].preco_unitario == 100.0
    assert cart_b2b.total == 200.0


def test_regra_3_adicionar_item_existente_soma_quantidade(cart_service):
    """
    Regra 3: Adicionar quantidade a um item já existente no carrinho deve somar
    à quantidade existente, não criar uma linha duplicada.
    """
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_soma", estoque=50, preco_b2c=50.0)

    cart = svc.create_cart(TipoCliente.B2C)
    svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_soma-VAR1", quantidade=2)
    cart_atualizado = svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_soma-VAR1", quantidade=3)

    assert len(cart_atualizado.itens) == 1
    assert cart_atualizado.itens[0].quantidade == 5
    assert cart_atualizado.total == 250.0


def test_regra_4_validacao_de_estoque_na_adicao_e_atualizacao(cart_service):
    """
    Regra 4: Validação de estoque na adição/atualização. Rejeita se exceder.
    Não decremente estoque real.
    """
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_est", estoque=5, preco_b2c=10.0)

    cart = svc.create_cart(TipoCliente.B2C)

    # Sucesso até o limite do estoque (5)
    cart = svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_est-VAR1", quantidade=3)
    assert cart.itens[0].quantidade == 3

    # Tenta somar mais 3 (total daria 6 > 5) -> Erro esperado
    with pytest.raises(InsufficientStockError) as exc_info:
        svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_est-VAR1", quantidade=3)
    assert "Estoque insuficiente" in str(exc_info.value)

    # Tenta atualizar via update_item_quantity para 6 > 5 -> Erro esperado
    with pytest.raises(InsufficientStockError):
        svc.update_item_quantity(cart.carrinho_id, "SKU-prod_est-VAR1", quantidade=6)

    # Verifica que o estoque do produto no catálogo permanece inalterado (5)
    prod_catalogo = prod_svc.get_product(prod.produto_id)
    assert prod_catalogo.variacoes[0].estoque_disponivel == 5


def test_regra_5_elegibilidade_checkout_moq_b2b_e_b2c(cart_service):
    """
    Regra 5: MOQ B2B >= R$ 350,00. B2C não tem MOQ. Carrinho vazio nunca é elegível.
    """
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_moq", estoque=100, preco_b2c=50.0, preco_b2b=100.0)

    # Carrinho B2C e B2B vazios -> não elegíveis
    cart_b2c = svc.create_cart(TipoCliente.B2C)
    cart_b2b = svc.create_cart(TipoCliente.B2B)

    eleg_b2c_vazio = svc.check_checkout_eligibility(cart_b2c.carrinho_id)
    assert eleg_b2c_vazio.elegivel is False
    assert eleg_b2c_vazio.motivo == "O carrinho está vazio."

    eleg_b2b_vazio = svc.check_checkout_eligibility(cart_b2b.carrinho_id)
    assert eleg_b2b_vazio.elegivel is False
    assert eleg_b2b_vazio.motivo == "O carrinho está vazio."

    # B2C com 1 item de R$ 50 -> Elegível (sem MOQ)
    svc.add_item(cart_b2c.carrinho_id, prod.produto_id, "SKU-prod_moq-VAR1", quantidade=1)
    eleg_b2c = svc.check_checkout_eligibility(cart_b2c.carrinho_id)
    assert eleg_b2c.elegivel is True
    assert eleg_b2c.total == 50.0

    # B2B com 3 itens de R$ 100 = R$ 300 (< 350) -> Não elegível
    svc.add_item(cart_b2b.carrinho_id, prod.produto_id, "SKU-prod_moq-VAR1", quantidade=3)
    eleg_b2b_abaixo = svc.check_checkout_eligibility(cart_b2b.carrinho_id)
    assert eleg_b2b_abaixo.elegivel is False
    assert eleg_b2b_abaixo.total == 300.0
    assert eleg_b2b_abaixo.valor_faltante_moq == 50.0
    assert "Pedido mínimo B2B de R$350,00 não atingido" in eleg_b2b_abaixo.motivo

    # B2B adiciona mais 1 item (total R$ 400 >= 350) -> Elegível
    svc.add_item(cart_b2b.carrinho_id, prod.produto_id, "SKU-prod_moq-VAR1", quantidade=1)
    eleg_b2b_ok = svc.check_checkout_eligibility(cart_b2b.carrinho_id)
    assert eleg_b2b_ok.elegivel is True
    assert eleg_b2b_ok.total == 400.0
    assert eleg_b2b_ok.valor_faltante_moq is None


def test_update_item_quantity_com_zero_remove_item(cart_service):
    """Testa se atualizar quantidade para 0 remove o item do carrinho."""
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_rem", estoque=10, preco_b2c=20.0)

    cart = svc.create_cart(TipoCliente.B2C)
    svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_rem-VAR1", quantidade=2)

    cart_rem = svc.update_item_quantity(cart.carrinho_id, "SKU-prod_rem-VAR1", quantidade=0)
    assert len(cart_rem.itens) == 0
    assert cart_rem.total == 0.0


def test_remove_item_carrinho(cart_service):
    """Testa remoção direta de item."""
    svc, _, prod_svc = cart_service
    prod = _criar_produto_exemplo(prod_svc, "prod_del", estoque=10, preco_b2c=20.0)

    cart = svc.create_cart(TipoCliente.B2C)
    svc.add_item(cart.carrinho_id, prod.produto_id, "SKU-prod_del-VAR1", quantidade=2)

    cart_after = svc.remove_item(cart.carrinho_id, "SKU-prod_del-VAR1")
    assert len(cart_after.itens) == 0


def test_remover_item_inexistente_lança_erro(cart_service):
    """Testa se remover item que não está no carrinho lança erro."""
    svc, _, prod_svc = cart_service
    cart = svc.create_cart(TipoCliente.B2C)

    with pytest.raises(CartItemNotFoundError):
        svc.remove_item(cart.carrinho_id, "SKU-INEXISTENTE")

    with pytest.raises(CartItemNotFoundError):
        svc.update_item_quantity(cart.carrinho_id, "SKU-INEXISTENTE", quantidade=1)
