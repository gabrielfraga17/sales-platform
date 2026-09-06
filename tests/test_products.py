"""Suíte completa de testes unitários e de integração para a TASK-0001 (Catálogo)."""

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.models.product import PrecoPorTipoCliente, ProdutoCreate, TipoCliente, VariacaoProduto
from app.routers.product_router import get_repository
from app.services.product_service import PriceNotAvailableError, ProductNotFoundError, ProductService, SKUConflictError


def payload_produto_valido(sku_base: str = "GUIA-MIÇANGA-01") -> dict:
    """Retorna um payload dicionário válido para cadastro de produto."""
    return {
        "sku_base": sku_base,
        "nome": "Guia de Miçangas de Iemanjá",
        "descricao": "Guia ritualística confeccionada com miçangas de vidro azuis e brancas.",
        "pilar_conteudo": "Estilo & Modaxé",
        "categoria": "Guias & Chicotés",
        "variacoes": [
            {
                "sku_variacao": f"{sku_base}-AZUL-UN",
                "atributos": {"tamanho": "único", "cor": "azul/branco"},
                "estoque_disponivel": 25,
            }
        ],
        "precos": [
            {
                "tipo_cliente": "b2c",
                "preco_unitario": 89.90,
            },
            {
                "tipo_cliente": "b2b",
                "preco_unitario": 40.00,
                "margem_minima_revenda_pct": 124.75,
            },
        ],
    }


# ============================================================================
# 1. TESTES DAS REGRAS DE NEGÓCIO (UNITÁRIOS NOS MODELOS E VALIDAÇÕES)
# ============================================================================

def test_regra_1_produto_deve_ter_preco_b2c() -> None:
    """Regra 1: Todo produto deve ter exatamente um preço com tipo_cliente=B2C."""
    data = payload_produto_valido("TEST-B2C-MISSING")
    data["precos"] = [
        {
            "tipo_cliente": "b2b",
            "preco_unitario": 40.0,
            "margem_minima_revenda_pct": 120.0,
        }
    ]
    with pytest.raises(ValidationError) as exc_info:
        ProdutoCreate(**data)
    assert "exatamente um preço para tipo_cliente=B2C" in str(exc_info.value)


def test_regra_1_produto_nao_pode_ter_multiplos_precos_b2c() -> None:
    """Regra 1: Produto com múltiplos preços B2C deve ser rejeitado."""
    data = payload_produto_valido("TEST-B2C-DUP")
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 80.0},
        {"tipo_cliente": "b2c", "preco_unitario": 90.0},
    ]
    with pytest.raises(ValidationError) as exc_info:
        ProdutoCreate(**data)
    assert "exatamente um preço para tipo_cliente=B2C" in str(exc_info.value)


def test_regra_2_b2b_sem_margem_revenda_deve_falhar() -> None:
    """Regra 2: Se existir tipo_cliente=B2B, o campo margem_minima_revenda_pct é obrigatório."""
    data = payload_produto_valido("TEST-B2B-NOMARGIN")
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 100.0},
        {"tipo_cliente": "b2b", "preco_unitario": 45.0, "margem_minima_revenda_pct": None},
    ]
    with pytest.raises(ValidationError) as exc_info:
        ProdutoCreate(**data)
    assert "margem_minima_revenda_pct é obrigatório" in str(exc_info.value)


def test_regra_2_b2b_com_margem_inferior_a_100_pct_deve_falhar() -> None:
    """Regra 2: Margem B2B < 100.0% deve lançar ValueError explícito."""
    data = payload_produto_valido("TEST-B2B-LOWMARGIN")
    data["precos"] = [
        {"tipo_cliente": "b2c", "preco_unitario": 100.0},
        {"tipo_cliente": "b2b", "preco_unitario": 60.0, "margem_minima_revenda_pct": 66.66},
    ]
    with pytest.raises(ValidationError) as exc_info:
        ProdutoCreate(**data)
    assert "Margem mínima de revenda B2B deve ser >= 100.0" in str(exc_info.value)


def test_regra_4_estoque_nao_pode_ser_negativo() -> None:
    """Regra 4: Estoque disponível nunca pode ser negativo."""
    data = payload_produto_valido("TEST-ESTOQUE-NEGATIVO")
    data["variacoes"][0]["estoque_disponivel"] = -5
    with pytest.raises(ValidationError):
        ProdutoCreate(**data)


# ============================================================================
# 2. TESTES DOS ENDPOINTS DA API (INTEGRAÇÃO FASTAPI + COBERTURA COMPLETA)
# ============================================================================

def test_criar_produto_sucesso(client: TestClient) -> None:
    """POST /produtos - Criação com sucesso (HTTP 201)."""
    payload = payload_produto_valido("SKU-PROD-01")
    response = client.post("/produtos", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["sku_base"] == "SKU-PROD-01"
    assert "produto_id" in res_data
    assert res_data["ativo"] is True


def test_criar_produto_sku_duplicado_conflito(client: TestClient) -> None:
    """Regra 3: SKU duplicado deve retornar HTTP 409 Conflict."""
    payload = payload_produto_valido("SKU-DUP-01")
    res1 = client.post("/produtos", json=payload)
    assert res1.status_code == 201

    # Tenta criar com o mesmo SKU base
    res2 = client.post("/produtos", json=payload)
    assert res2.status_code == 409
    assert "já está cadastrado" in res2.json()["detail"]


def test_obter_produto_por_id(client: TestClient) -> None:
    """GET /produtos/{id} - Busca por ID existente e inexistente."""
    payload = payload_produto_valido("SKU-GET-01")
    created = client.post("/produtos", json=payload).json()
    produto_id = created["produto_id"]

    # Sucesso
    res = client.get(f"/produtos/{produto_id}")
    assert res.status_code == 200
    assert res.json()["nome"] == payload["nome"]

    # Não Encontrado
    res_404 = client.get("/produtos/prod_inexistente_999")
    assert res_404.status_code == 404


def test_listar_produtos_com_paginacao_e_filtro(client: TestClient) -> None:
    """GET /produtos - Teste de listagem, paginação e filtro por categoria."""
    p1 = payload_produto_valido("SKU-LIST-01")
    p1["categoria"] = "Vestuário"
    client.post("/produtos", json=p1)

    p2 = payload_produto_valido("SKU-LIST-02")
    p2["categoria"] = "Vestuário"
    client.post("/produtos", json=p2)

    p3 = payload_produto_valido("SKU-LIST-03")
    p3["categoria"] = "Acessórios"
    client.post("/produtos", json=p3)

    # Listar todos com limite 10
    res = client.get("/produtos?limit=10")
    assert res.status_code == 200
    assert len(res.json()) == 3

    # Filtrar por categoria Vestuário
    res_cat = client.get("/produtos?categoria=Vestuário")
    assert res_cat.status_code == 200
    assert len(res_cat.json()) == 2

    # Teste de paginação limit=1, offset=1
    res_page = client.get("/produtos?limit=1&offset=1")
    assert res_page.status_code == 200
    assert len(res_page.json()) == 1


def test_atualizar_produto_sucesso(client: TestClient) -> None:
    """PUT /produtos/{id} - Atualização de informações do produto."""
    payload = payload_produto_valido("SKU-PUT-01")
    created = client.post("/produtos", json=payload).json()
    produto_id = created["produto_id"]

    update_payload = {
        "nome": "Guia de Miçangas Especial de Iemanjá",
        "categoria": "Guias Luxo",
    }
    res = client.put(f"/produtos/{produto_id}", json=update_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["nome"] == "Guia de Miçangas Especial de Iemanjá"
    assert res_data["categoria"] == "Guias Luxo"


def test_atualizar_produto_inexistente_404(client: TestClient) -> None:
    """PUT /produtos/{id} - Produto inexistente retorna 404."""
    res = client.put("/produtos/prod_nao_existe", json={"nome": "Novo Nome"})
    assert res.status_code == 404


def test_atualizar_produto_sku_conflito_409(client: TestClient) -> None:
    """PUT /produtos/{id} - Conflito de SKU na atualização retorna 409."""
    p1 = client.post("/produtos", json=payload_produto_valido("SKU-ORIGINAL-1")).json()
    p2 = client.post("/produtos", json=payload_produto_valido("SKU-ORIGINAL-2")).json()

    # Tenta atualizar p2 para o sku_base de p1
    res = client.put(f"/produtos/{p2['produto_id']}", json={"sku_base": "SKU-ORIGINAL-1"})
    assert res.status_code == 409


def test_atualizar_produto_sem_mudancas(client: TestClient) -> None:
    """PUT /produtos/{id} - Payload vazio não altera produto."""
    created = client.post("/produtos", json=payload_produto_valido("SKU-NOOP")).json()
    res = client.put(f"/produtos/{created['produto_id']}", json={})
    assert res.status_code == 200


def test_remover_produto_soft_delete(client: TestClient) -> None:
    """DELETE /produtos/{id} - Soft delete altera ativo=False."""
    payload = payload_produto_valido("SKU-DEL-01")
    created = client.post("/produtos", json=payload).json()
    produto_id = created["produto_id"]

    res_del = client.delete(f"/produtos/{produto_id}")
    assert res_del.status_code == 200
    assert res_del.json()["ativo"] is False

    # Idempotência: remover novamente produto já inativo
    res_del_2 = client.delete(f"/produtos/{produto_id}")
    assert res_del_2.status_code == 200

    # Confirmar que não aparece mais na listagem de ativos
    res_list = client.get("/produtos")
    ids_ativos = [p["produto_id"] for p in res_list.json()]
    assert produto_id not in ids_ativos


def test_remover_produto_inexistente_404(client: TestClient) -> None:
    """DELETE /produtos/{id} - Produto inexistente retorna 404."""
    res = client.delete("/produtos/prod_nao_existe")
    assert res.status_code == 404


def test_consultar_preco_produto_b2c_e_b2b(client: TestClient) -> None:
    """GET /produtos/{id}/preco?tipo_cliente=b2c|b2b."""
    payload = payload_produto_valido("SKU-PRECO-01")
    created = client.post("/produtos", json=payload).json()
    produto_id = created["produto_id"]

    # Preço B2C
    res_b2c = client.get(f"/produtos/{produto_id}/preco?tipo_cliente=b2c")
    assert res_b2c.status_code == 200
    assert res_b2c.json()["preco_unitario"] == 89.90

    # Preço B2B
    res_b2b = client.get(f"/produtos/{produto_id}/preco?tipo_cliente=b2b")
    assert res_b2b.status_code == 200
    assert res_b2b.json()["preco_unitario"] == 40.00
    assert res_b2b.json()["margem_minima_revenda_pct"] == 124.75


def test_consultar_preco_produto_nao_configurado_404(client: TestClient) -> None:
    """GET /produtos/{id}/preco - Tipo de cliente sem preço cadastrado retorna 404."""
    data = payload_produto_valido("SKU-B2C-ONLY")
    data["precos"] = [{"tipo_cliente": "b2c", "preco_unitario": 99.90}]
    created = client.post("/produtos", json=data).json()

    res = client.get(f"/produtos/{created['produto_id']}/preco?tipo_cliente=b2b")
    assert res.status_code == 404
    assert "não está configurado" in res.json()["detail"]


def test_health_check_endpoint(client: TestClient) -> None:
    """GET /health - Verificação de integridade da API."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_get_repository_singleton() -> None:
    """Testa a injeção do repositório singleton get_repository()."""
    repo = get_repository()
    assert repo is not None
