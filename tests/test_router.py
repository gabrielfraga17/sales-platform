"""Testes de integração para as rotas FastAPI (app.routers.product_router)."""

from fastapi.testclient import TestClient

from tests.test_products import payload_produto_valido


def test_router_criar_produto_sucesso(client: TestClient) -> None:
    payload = payload_produto_valido("SKU-ROUTER-01")
    res = client.post("/produtos", json=payload)
    assert res.status_code == 201
    assert res.json()["sku_base"] == "SKU-ROUTER-01"


def test_router_criar_produto_sku_duplicado_409(client: TestClient) -> None:
    payload = payload_produto_valido("SKU-ROUTER-DUP")
    client.post("/produtos", json=payload)
    res = client.post("/produtos", json=payload)
    assert res.status_code == 409


def test_router_obter_produto_por_id_sucesso_e_404(client: TestClient) -> None:
    payload = payload_produto_valido("SKU-ROUTER-GET")
    created = client.post("/produtos", json=payload).json()

    res = client.get(f"/produtos/{created['produto_id']}")
    assert res.status_code == 200
    assert res.json()["produto_id"] == created["produto_id"]

    res_404 = client.get("/produtos/prod_nao_existe")
    assert res_404.status_code == 404


def test_router_listar_produtos(client: TestClient) -> None:
    client.post("/produtos", json=payload_produto_valido("SKU-LIST-1"))
    client.post("/produtos", json=payload_produto_valido("SKU-LIST-2"))

    res = client.get("/produtos")
    assert res.status_code == 200
    assert len(res.json()) >= 2


def test_router_atualizar_produto(client: TestClient) -> None:
    created = client.post("/produtos", json=payload_produto_valido("SKU-UPD-R")).json()

    res = client.put(f"/produtos/{created['produto_id']}", json={"nome": "Nome Novo"})
    assert res.status_code == 200
    assert res.json()["nome"] == "Nome Novo"


def test_router_remover_produto_soft_delete(client: TestClient) -> None:
    created = client.post("/produtos", json=payload_produto_valido("SKU-DEL-R")).json()

    res = client.delete(f"/produtos/{created['produto_id']}")
    assert res.status_code == 200
    assert res.json()["ativo"] is False


def test_router_consultar_preco(client: TestClient) -> None:
    created = client.post("/produtos", json=payload_produto_valido("SKU-PRECO-R")).json()

    res = client.get(f"/produtos/{created['produto_id']}/preco?tipo_cliente=b2c")
    assert res.status_code == 200
    assert res.json()["preco_unitario"] == 89.90
