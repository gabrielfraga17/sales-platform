"""Testes unitários e de integração para os endpoints do router de checkout e pedidos."""

from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.product import PrecoPorTipoCliente, Produto, TipoCliente, VariacaoProduto
from app.repositories.firestore_repository import InMemoryProductRepository
from app.routers.cart_router import get_cart_service, get_order_service


import uuid
from app.routers.product_router import get_repository

@pytest.fixture(autouse=True)
def force_in_memory():
    original = settings.USE_IN_MEMORY_DB
    settings.USE_IN_MEMORY_DB = True
    # Reset singleton state
    import app.routers.product_router as pr
    pr._repo_instance = InMemoryProductRepository()

    if hasattr(get_cart_service, "_cart_repo"):
        delattr(get_cart_service, "_cart_repo")
    if hasattr(get_order_service, "_order_repo"):
        delattr(get_order_service, "_order_repo")
    yield
    settings.USE_IN_MEMORY_DB = original


@pytest.fixture
def client():
    return TestClient(app)


def _criar_produto(client: TestClient) -> dict:
    unique_sku = f"SKU-ROUTER-{uuid.uuid4().hex[:6]}"
    unique_var_sku = f"SKU-VAR-{uuid.uuid4().hex[:6]}"
    payload = {
        "sku_base": unique_sku,
        "nome": "Colar Sol",
        "descricao": "Colar folheado a ouro",
        "categoria": "Jóias",
        "variacoes": [
            {
                "sku_variacao": unique_var_sku,
                "atributos": {"tamanho": "M"},
                "estoque_disponivel": 10,
            }
        ],
        "precos": [
            {"tipo_cliente": "b2c", "preco_unitario": 100.0},
            {"tipo_cliente": "b2b", "preco_unitario": 80.0, "margem_minima_revenda_pct": 100.0},
        ],
    }
    response = client.post("/produtos", json=payload)
    assert response.status_code == 201
    res = response.json()
    res["sku_variacao"] = unique_var_sku
    return res


def test_finalizar_checkout_endpoint_sucesso(client: TestClient):
    prod = _criar_produto(client)
    prod_id = prod["produto_id"]
    sku_var = prod["sku_variacao"]

    # Cria carrinho
    resp_cart = client.post("/carrinhos", json={"tipo_cliente": "b2c"})
    cart_id = resp_cart.json()["carrinho_id"]

    # Adiciona item
    client.post(
        f"/carrinhos/{cart_id}/itens",
        json={"produto_id": prod_id, "sku_variacao": sku_var, "quantidade": 2},
    )

    # Finaliza checkout
    payload_checkout = {
        "comprador": {
            "nome": "Ana Maria",
            "email": "ana@example.com",
            "telefone": "11988887777",
        },
        "endereco_entrega": {
            "destinatario": "Ana Maria",
            "logradouro": "Av Paulista",
            "numero": "1000",
            "bairro": "Bela Vista",
            "cidade": "São Paulo",
            "estado": "SP",
            "cep": "01310-100",
        },
    }

    resp_checkout = client.post(f"/carrinhos/{cart_id}/finalizar-checkout", json=payload_checkout)
    assert resp_checkout.status_code == status.HTTP_201_CREATED
    pedido_data = resp_checkout.json()

    assert pedido_data["carrinho_id"] == cart_id
    assert pedido_data["status"] == "aguardando_pagamento"
    assert pedido_data["total"] == 200.0
    pedido_id = pedido_data["pedido_id"]

    # Consulta pedido criado
    resp_pedido = client.get(f"/pedidos/{pedido_id}")
    assert resp_pedido.status_code == status.HTTP_200_OK
    assert resp_pedido.json()["pedido_id"] == pedido_id


def test_finalizar_checkout_carrinho_nao_encontrado(client: TestClient):
    payload = {
        "comprador": {"nome": "A", "email": "a@ex.com", "telefone": "119"},
        "endereco_entrega": {
            "destinatario": "A",
            "logradouro": "L",
            "numero": "1",
            "bairro": "B",
            "cidade": "C",
            "estado": "SP",
            "cep": "00000-000",
        },
    }
    resp = client.post("/carrinhos/cart_inexistente/finalizar-checkout", json=payload)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_finalizar_checkout_b2b_sem_cnpj_status_400(client: TestClient):
    prod = _criar_produto(client)
    prod_id = prod["produto_id"]
    sku_var = prod["sku_variacao"]

    resp_cart = client.post("/carrinhos", json={"tipo_cliente": "b2b"})
    cart_id = resp_cart.json()["carrinho_id"]

    # Adiciona 5 * 80 = 400 >= 350
    client.post(
        f"/carrinhos/{cart_id}/itens",
        json={"produto_id": prod_id, "sku_variacao": sku_var, "quantidade": 5},
    )

    payload_incompleto = {
        "comprador": {
            "nome": "Empresa Teste",
            "email": "emp@example.com",
            "telefone": "11988887777",
            "razao_social": "Empresa Teste Ltda",
            "cnpj": None,
        },
        "endereco_entrega": {
            "destinatario": "Empresa Teste",
            "logradouro": "Rua X",
            "numero": "12",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "estado": "SP",
            "cep": "01310-100",
        },
    }

    resp = client.post(f"/carrinhos/{cart_id}/finalizar-checkout", json=payload_incompleto)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_obter_pedido_nao_encontrado(client: TestClient):
    resp = client.get("/pedidos/ped_inexistente")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
