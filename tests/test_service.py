"""Testes unitários para o serviço de produtos (app.services.product_service)."""

from datetime import datetime, timezone
import pytest

from app.models.product import PrecoPorTipoCliente, Produto, ProdutoCreate, ProdutoUpdate, TipoCliente, VariacaoProduto
from app.repositories.firestore_repository import InMemoryProductRepository
from app.services.product_service import PriceNotAvailableError, ProductNotFoundError, ProductService, SKUConflictError


def payload_produto_valido(sku_base: str = "SKU-SVC-01") -> ProdutoCreate:
    return ProdutoCreate(
        sku_base=sku_base,
        nome="Produto Servico",
        descricao="Descricao produto servico",
        categoria="Categoria Teste",
        variacoes=[
            VariacaoProduto(
                sku_variacao=f"{sku_base}-VAR1",
                atributos={"tamanho": "M"},
                estoque_disponivel=15,
            )
        ],
        precos=[
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2C, preco_unitario=100.0),
            PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2B, preco_unitario=40.0, margem_minima_revenda_pct=150.0),
        ],
    )


def test_service_create_product_success() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    payload = payload_produto_valido("SKU-SVC-01")

    produto = service.create_product(payload)
    assert produto.produto_id.startswith("prod_")
    assert produto.sku_base == "SKU-SVC-01"
    assert produto.ativo is True


def test_service_create_product_sku_conflict() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    payload = payload_produto_valido("SKU-DUP-SVC")

    service.create_product(payload)
    with pytest.raises(SKUConflictError) as exc:
        service.create_product(payload)
    assert "já está cadastrado" in str(exc.value)


def test_service_get_product_not_found() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    with pytest.raises(ProductNotFoundError):
        service.get_product("prod_inexistente")


def test_service_update_product_success() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    created = service.create_product(payload_produto_valido("SKU-UPD-01"))

    update_payload = ProdutoUpdate(nome="Nome Atualizado")
    updated = service.update_product(created.produto_id, update_payload)
    assert updated.nome == "Nome Atualizado"


def test_service_update_product_sku_conflict() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    p1 = service.create_product(payload_produto_valido("SKU-A"))
    p2 = service.create_product(payload_produto_valido("SKU-B"))

    update_payload = ProdutoUpdate(sku_base="SKU-A")
    with pytest.raises(SKUConflictError):
        service.update_product(p2.produto_id, update_payload)


def test_service_delete_product_soft_delete() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    created = service.create_product(payload_produto_valido("SKU-DEL-SVC"))

    deleted = service.delete_product(created.produto_id)
    assert deleted.ativo is False

    # Soft delete idempotente
    deleted_again = service.delete_product(created.produto_id)
    assert deleted_again.ativo is False


def test_service_get_product_price() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    created = service.create_product(payload_produto_valido("SKU-PRICE-SVC"))

    preco_b2c = service.get_product_price(created.produto_id, TipoCliente.B2C)
    assert preco_b2c.preco_unitario == 100.0

    preco_b2b = service.get_product_price(created.produto_id, TipoCliente.B2B)
    assert preco_b2b.preco_unitario == 40.0
    assert preco_b2b.margem_minima_revenda_pct == 150.0


def test_service_get_product_price_not_configured() -> None:
    repo = InMemoryProductRepository()
    service = ProductService(repo)
    payload = ProdutoCreate(
        sku_base="SKU-B2C-ONLY-SVC",
        nome="Apenas B2C",
        descricao="Descricao",
        categoria="Cat",
        variacoes=[VariacaoProduto(sku_variacao="SKU-B2C-ONLY-SVC-V", atributos={}, estoque_disponivel=1)],
        precos=[PrecoPorTipoCliente(tipo_cliente=TipoCliente.B2C, preco_unitario=50.0)],
    )
    created = service.create_product(payload)

    with pytest.raises(PriceNotAvailableError):
        service.get_product_price(created.produto_id, TipoCliente.B2B)
