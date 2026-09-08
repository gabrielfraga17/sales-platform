"""Testes unitários para o OrderService e regras de negócio de checkout."""

import pytest
from datetime import datetime, timezone

from app.models.cart import Carrinho, ItemCarrinho
from app.models.order import (
    DadosComprador,
    EnderecoEntrega,
    FinalizarCheckoutRequest,
    StatusPedido,
)
from app.models.product import PrecoPorTipoCliente, Produto, TipoCliente, VariacaoProduto
from app.repositories.cart_firestore_repository import InMemoryCartRepository
from app.repositories.firestore_repository import InMemoryProductRepository
from app.repositories.order_firestore_repository import InMemoryOrderRepository
from app.services.cart_service import CartAlreadyFinalizedError as CartServiceAlreadyFinalizedError, CartService
from app.services.order_service import (
    CartAlreadyFinalizedError,
    CartNotEligibleError,
    InvalidBuyerDataError,
    OrderNotFoundError,
    OrderService,
    StockCommitError,
)
from app.services.product_service import ProductService


@pytest.fixture
def repos_and_services():
    cart_repo = InMemoryCartRepository()
    product_repo = InMemoryProductRepository()
    order_repo = InMemoryOrderRepository()

    product_service = ProductService(repository=product_repo)
    cart_service = CartService(cart_repository=cart_repo, product_service=product_service)
    order_service = OrderService(order_repository=order_repo, cart_service=cart_service)

    return {
        "cart_repo": cart_repo,
        "product_repo": product_repo,
        "order_repo": order_repo,
        "product_service": product_service,
        "cart_service": cart_service,
        "order_service": order_service,
    }


def _criar_produto_teste(product_service: ProductService, produto_id="prod_1", sku_var="SKU-VAR-1", estoque=10) -> Produto:
    now = datetime.now(timezone.utc)
    produto = Produto(
        produto_id=produto_id,
        sku_base="SKU-BASE-1",
        nome="Brinco Dourado",
        descricao="Brinco lindo",
        categoria="Acessórios",
        variacoes=[VariacaoProduto(sku_variacao=sku_var, atributos={"cor": "dourado"}, estoque_disponivel=estoque)],
        precos=[
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2C, preco_unitario=50.0),
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2B, preco_unitario=40.0, margem_minima_revenda_pct=100.0),
        ],
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )
    return product_service.create_product(produto)


def test_checkout_sucesso_decrementa_estoque(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=10)

    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2C)
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 3)

    req = FinalizarCheckoutRequest(
        comprador=DadosComprador(nome="Cliente Teste", email="teste@example.com", telefone="11999999999"),
        endereco_entrega=EnderecoEntrega(
            destinatario="Cliente Teste",
            logradouro="Rua A",
            numero="10",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    pedido = services["order_service"].finalizar_checkout(cart.carrinho_id, req)

    assert pedido.pedido_id.startswith("ped_")
    assert pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO
    assert pedido.total == 150.0

    # Verifica se o estoque foi decrementado de 10 para 7
    prod_atualizado = services["product_service"].get_product(prod.produto_id)
    assert prod_atualizado.variacoes[0].estoque_disponivel == 7

    # Verifica se carrinho foi marcado como finalizado
    cart_atualizado = services["cart_service"].get_cart(cart.carrinho_id)
    assert cart_atualizado.finalizado is True


def test_checkout_rejeitado_moq_b2b(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=10)

    # B2B exige R$ 350. Preço unitário B2B = 40.0. Qtd 2 = 80.0 < 350.0
    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2B)
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 2)

    req = FinalizarCheckoutRequest(
        comprador=DadosComprador(
            nome="Empresa X",
            email="empresa@example.com",
            telefone="11999999999",
            razao_social="Empresa X Ltda",
            cnpj="12.345.678/0001-90",
        ),
        endereco_entrega=EnderecoEntrega(
            destinatario="Empresa X",
            logradouro="Rua B",
            numero="20",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    with pytest.raises(CartNotEligibleError) as exc_info:
        services["order_service"].finalizar_checkout(cart.carrinho_id, req)

    assert "350,00" in str(exc_info.value)


def test_checkout_rejeitado_estoque_insuficiente_no_commit(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=5)

    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2C)
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 3)

    # Simula alteração do estoque por outro processo/checkout concorrente antes do commit
    prod_db = services["product_service"].get_product(prod.produto_id)
    prod_db.variacoes[0].estoque_disponivel = 1  # Agora só resta 1 no estoque
    services["product_repo"].save(prod_db)

    req = FinalizarCheckoutRequest(
        comprador=DadosComprador(nome="Cliente Concorrente", email="conc@example.com", telefone="11999999999"),
        endereco_entrega=EnderecoEntrega(
            destinatario="Cliente Concorrente",
            logradouro="Rua C",
            numero="30",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    with pytest.raises(StockCommitError) as exc_info:
        services["order_service"].finalizar_checkout(cart.carrinho_id, req)

    assert "SKU-VAR-1" in exc_info.value.skus


def test_checkout_rejeitado_carrinho_ja_finalizado(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=10)

    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2C)
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 1)

    req = FinalizarCheckoutRequest(
        comprador=DadosComprador(nome="Cliente", email="cliente@example.com", telefone="11999999999"),
        endereco_entrega=EnderecoEntrega(
            destinatario="Cliente",
            logradouro="Rua D",
            numero="40",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    services["order_service"].finalizar_checkout(cart.carrinho_id, req)

    # Segunda tentativa no mesmo carrinho
    with pytest.raises(CartAlreadyFinalizedError):
        services["order_service"].finalizar_checkout(cart.carrinho_id, req)


def test_alteracao_item_carrinho_ja_finalizado(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=10)

    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2C)
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 1)

    req = FinalizarCheckoutRequest(
        comprador=DadosComprador(nome="Cliente", email="cliente@example.com", telefone="11999999999"),
        endereco_entrega=EnderecoEntrega(
            destinatario="Cliente",
            logradouro="Rua E",
            numero="50",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    services["order_service"].finalizar_checkout(cart.carrinho_id, req)

    # Tentativa de add_item em carrinho finalizado
    with pytest.raises(CartServiceAlreadyFinalizedError):
        services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 1)

    # Tentativa de update_item_quantity em carrinho finalizado
    with pytest.raises(CartServiceAlreadyFinalizedError):
        services["cart_service"].update_item_quantity(cart.carrinho_id, "SKU-VAR-1", 2)

    # Tentativa de remove_item em carrinho finalizado
    with pytest.raises(CartServiceAlreadyFinalizedError):
        services["cart_service"].remove_item(cart.carrinho_id, "SKU-VAR-1")


def test_b2b_sem_razao_social_ou_cnpj(repos_and_services):
    services = repos_and_services
    prod = _criar_produto_teste(services["product_service"], estoque=20)

    cart = services["cart_service"].create_cart(tipo_cliente=TipoCliente.B2B)
    # 10 * 40 = 400 >= 350
    services["cart_service"].add_item(cart.carrinho_id, prod.produto_id, "SKU-VAR-1", 10)

    req_sem_cnpj = FinalizarCheckoutRequest(
        comprador=DadosComprador(
            nome="Empresa Y",
            email="empresa@example.com",
            telefone="11999999999",
            razao_social="Empresa Y Ltda",
            cnpj=None,  # Faltando CNPJ
        ),
        endereco_entrega=EnderecoEntrega(
            destinatario="Empresa Y",
            logradouro="Rua F",
            numero="60",
            bairro="Bairro",
            cidade="Cidade",
            estado="SP",
            cep="12345-678",
        ),
    )

    with pytest.raises(InvalidBuyerDataError):
        services["order_service"].finalizar_checkout(cart.carrinho_id, req_sem_cnpj)


def test_get_order_nao_encontrado(repos_and_services):
    services = repos_and_services
    with pytest.raises(OrderNotFoundError):
        services["order_service"].get_order("ped_inexistente")
