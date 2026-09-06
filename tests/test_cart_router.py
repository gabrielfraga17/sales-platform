"""Testes de integração das rotas HTTP da API de Carrinho de Compras."""

from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.product import PrecoPorTipoCliente, Produto, TipoCliente, VariacaoProduto
from app.routers.cart_router import get_cart_service
from app.services.cart_service import CartService
from app.repositories.cart_firestore_repository import InMemoryCartRepository
from app.repositories.firestore_repository import InMemoryProductRepository
from app.services.product_service import ProductService


@pytest.fixture
def client_and_service():
    cart_repo = InMemoryCartRepository()
    prod_repo = InMemoryProductRepository()
    prod_svc = ProductService(repository=prod_repo)
    cart_svc = CartService(cart_repository=cart_repo, product_service=prod_svc)

    def override_get_cart_service():
        return cart_svc

    app.dependency_overrides[get_cart_service] = override_get_cart_service
    client = TestClient(app)

    yield client, cart_svc, prod_svc

    app.dependency_overrides.clear()


def _cadastrar_produto_aux(prod_svc: ProductService, prod_id: str = "p_api", estoque: int = 10, preco_b2c: float = 100.0, preco_b2b: float = 80.0):
    now = datetime.now(timezone.utc)
    produto = Produto(
        produto_id=prod_id,
        sku_base=f"BASE-{prod_id}",
        nome=f"Produto API {prod_id}",
        descricao="Desc",
        categoria="Categorias",
        variacoes=[
            VariacaoProduto(
                sku_variacao=f"SKU-{prod_id}-VAR",
                atributos={"tamanho": "M"},
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


def test_endpoint_criar_carrinho(client_and_service):
    client, _, _ = client_and_service

    res = client.post("/carrinhos", json={"tipo_cliente": "b2c"})
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert "carrinho_id" in data
    assert data["tipo_cliente"] == "b2c"
    assert data["itens"] == []


def test_endpoint_obter_carrinho_sucesso_e_nao_encontrado(client_and_service):
    client, _, _ = client_and_service

    # POST
    create_res = client.post("/carrinhos", json={"tipo_cliente": "b2b"})
    carrinho_id = create_res.json()["carrinho_id"]

    # GET sucesso
    get_res = client.get(f"/carrinhos/{carrinho_id}")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["carrinho_id"] == carrinho_id

    # GET erro 404
    err_res = client.get("/carrinhos/cart_id_inexistente")
    assert err_res.status_code == status.HTTP_404_NOT_FOUND


def test_endpoint_adicionar_item_sucesso_e_erros(client_and_service):
    client, _, prod_svc = client_and_service
    prod = _cadastrar_produto_aux(prod_svc, "p_item", estoque=5, preco_b2c=50.0)

    carrinho_id = client.post("/carrinhos", json={"tipo_cliente": "b2c"}).json()["carrinho_id"]

    # Sucesso
    res_add = client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_item-VAR", "quantidade": 2},
    )
    assert res_add.status_code == status.HTTP_200_OK
    data = res_add.json()
    assert len(data["itens"]) == 1
    assert data["itens"][0]["preco_unitario"] == 50.0

    # Erro 400 - Estoque insuficiente (tentando colocar mais 4, total 6 > 5)
    res_err_stock = client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_item-VAR", "quantidade": 4},
    )
    assert res_err_stock.status_code == status.HTTP_400_BAD_REQUEST

    # Erro 404 - Produto não encontrado
    res_err_prod = client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": "prod_fantasma", "sku_variacao": "SKU-p_item-VAR", "quantidade": 1},
    )
    assert res_err_prod.status_code == status.HTTP_404_NOT_FOUND

    # Erro 404 - Carrinho não encontrado
    res_err_cart = client.post(
        "/carrinhos/cart_fantasma/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_item-VAR", "quantidade": 1},
    )
    assert res_err_cart.status_code == status.HTTP_404_NOT_FOUND


def test_endpoint_atualizar_quantidade_sucesso_e_erros(client_and_service):
    client, _, prod_svc = client_and_service
    prod = _cadastrar_produto_aux(prod_svc, "p_upd", estoque=10, preco_b2c=100.0)

    carrinho_id = client.post("/carrinhos", json={"tipo_cliente": "b2c"}).json()["carrinho_id"]

    client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_upd-VAR", "quantidade": 2},
    )

    # PUT Sucesso
    res_put = client.put(
        f"/carrinhos/{carrinho_id}/itens/SKU-p_upd-VAR",
        json={"quantidade": 5},
    )
    assert res_put.status_code == status.HTTP_200_OK
    assert res_put.json()["itens"][0]["quantidade"] == 5

    # PUT Erro 400 Estoque Excedido (15 > 10)
    res_err_stk = client.put(
        f"/carrinhos/{carrinho_id}/itens/SKU-p_upd-VAR",
        json={"quantidade": 15},
    )
    assert res_err_stk.status_code == status.HTTP_400_BAD_REQUEST

    # PUT Erro 404 SKU não existe no carrinho
    res_err_sku = client.put(
        f"/carrinhos/{carrinho_id}/itens/SKU-OUTRO",
        json={"quantidade": 1},
    )
    assert res_err_sku.status_code == status.HTTP_404_NOT_FOUND


def test_endpoint_remover_item_sucesso_e_erro(client_and_service):
    client, _, prod_svc = client_and_service
    prod = _cadastrar_produto_aux(prod_svc, "p_del", estoque=10, preco_b2c=100.0)

    carrinho_id = client.post("/carrinhos", json={"tipo_cliente": "b2c"}).json()["carrinho_id"]

    client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_del-VAR", "quantidade": 2},
    )

    # DELETE Sucesso
    res_del = client.delete(f"/carrinhos/{carrinho_id}/itens/SKU-p_del-VAR")
    assert res_del.status_code == status.HTTP_200_OK
    assert len(res_del.json()["itens"]) == 0

    # DELETE Erro 404
    res_err_del = client.delete(f"/carrinhos/{carrinho_id}/itens/SKU-p_del-VAR")
    assert res_err_del.status_code == status.HTTP_404_NOT_FOUND


def test_endpoint_elegibilidade_checkout(client_and_service):
    client, _, prod_svc = client_and_service
    prod = _cadastrar_produto_aux(prod_svc, "p_elig", estoque=50, preco_b2b=100.0)

    carrinho_id = client.post("/carrinhos", json={"tipo_cliente": "b2b"}).json()["carrinho_id"]

    # Vazio -> Elegivel False
    res_vazio = client.get(f"/carrinhos/{carrinho_id}/elegibilidade-checkout")
    assert res_vazio.status_code == status.HTTP_200_OK
    assert res_vazio.json()["elegivel"] is False

    # 3 itens x R$ 100 = 300 (< 350) -> Elegivel False
    client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_elig-VAR", "quantidade": 3},
    )
    res_b2b_abaixo = client.get(f"/carrinhos/{carrinho_id}/elegibilidade-checkout")
    assert res_b2b_abaixo.json()["elegivel"] is False
    assert res_b2b_abaixo.json()["valor_faltante_moq"] == 50.0

    # 4 itens x R$ 100 = 400 (>= 350) -> Elegivel True
    client.post(
        f"/carrinhos/{carrinho_id}/itens",
        json={"produto_id": prod.produto_id, "sku_variacao": "SKU-p_elig-VAR", "quantidade": 1},
    )
    res_b2b_ok = client.get(f"/carrinhos/{carrinho_id}/elegibilidade-checkout")
    assert res_b2b_ok.json()["elegivel"] is True
    assert res_b2b_ok.json()["valor_faltante_moq"] is None

    # GET Erro 404
    res_err_cart = client.get("/carrinhos/cart_fantasma/elegibilidade-checkout")
    assert res_err_cart.status_code == status.HTTP_404_NOT_FOUND
