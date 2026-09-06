# TASK-0002 — Módulo de Carrinho (Sales Platform)

## Status
`READY_FOR_IMPLEMENTATION`

## Contexto de Negócio
Este módulo implementa o carrinho de compras da Sales Platform, com a regra
central de **pedido mínimo (MOQ) de R$ 350,00 para clientes B2B** (ver
`docs/01_visao_negocio_e_personas.md`). Não há autenticação de cliente final
implementada ainda (fora de escopo, ver TASK-0001) — o carrinho é identificado
por um `carrinho_id` opaco, gerado na criação e devolvido ao chamador, que fica
responsável por guardá-lo (ex: frontend em `localStorage`/`sessionStorage`).
Não assuma usuário logado em nenhum momento desta ticket.

Este módulo **depende do módulo de Catálogo (TASK-0001)**, já implementado,
testado (91% de cobertura) e mergeado neste mesmo repositório.

## Objetivo
Implementar um serviço de Carrinho que permita:
1. Criar um carrinho vazio, associado a um tipo de cliente (B2C ou B2B).
2. Adicionar, atualizar e remover itens do carrinho, com preço sempre obtido
   dinamicamente do Catálogo — nunca aceito do chamador da API.
3. Validar se um carrinho está elegível para prosseguir ao checkout, incluindo
   a regra de MOQ B2B (≥ R$ 350,00). **Checkout e pagamento em si são
   TASK-0003+, fora de escopo aqui** — esta ticket só valida a elegibilidade.

## Stack e Decisões de Arquitetura (não negociáveis nesta ticket)

- **Mesmo app FastAPI da Sales Platform, não um serviço novo.** O Carrinho
  vive em `app/models/cart.py`, `app/services/cart_service.py`,
  `app/repositories/cart_firestore_repository.py`, `app/routers/cart_router.py`
  — seguindo exatamente o mesmo padrão de camadas do Catálogo.
- **Consulta de preço e estoque via chamada de função Python direta** ao
  `product_service.py` já existente (ex: uma função `obter_preco_produto(...)`
  e `obter_estoque_variacao(...)`, adicionando-as ao `product_service.py` se
  ainda não existirem com essa assinatura). **Não implemente chamada HTTP
  entre serviços** — é o mesmo processo, mesmo deploy, sem necessidade disso
  nesta fase.
- **Banco de dados:** Firestore (mesmo banco do Catálogo), coleção `carrinhos`.
- **Linguagem:** Python 3.11+, type hints em 100% das funções públicas.
- **Validação de dados:** Pydantic v2.
- Nenhuma dependência nova além do que já está em `requirements.txt` desta
  ticket em diante — se precisar de algo novo, justifique por escrito no PR,
  como já exigido na TASK-0001.

## Contrato de Dados (Pydantic)

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# TipoCliente já existe em app/models/product.py — reutilize, não redefina.

class ItemCarrinho(BaseModel):
    produto_id: str
    sku_variacao: str
    nome_produto: str = Field(description="Snapshot do nome no momento da adição, para exibição")
    quantidade: int = Field(gt=0)
    preco_unitario: float = Field(gt=0, description="Snapshot do preço no momento da adição/atualização")

    @property
    def subtotal(self) -> float:
        return round(self.quantidade * self.preco_unitario, 2)

class Carrinho(BaseModel):
    carrinho_id: str
    tipo_cliente: "TipoCliente"  # reutilizado de app.models.product
    itens: list[ItemCarrinho] = Field(default_factory=list)
    criado_em: datetime
    atualizado_em: datetime

    @property
    def total(self) -> float:
        return round(sum(item.subtotal for item in self.itens), 2)

class ElegibilidadeCheckout(BaseModel):
    elegivel: bool
    total: float
    motivo: Optional[str] = Field(
        default=None,
        description="Preenchido quando elegivel=False, ex: 'Pedido mínimo B2B de R$350,00 não atingido'",
    )
    valor_faltante_moq: Optional[float] = Field(
        default=None,
        description="Apenas quando aplicável a B2B e não atingido — quanto falta para R$350,00",
    )
```

## Regras de Negócio a Validar no Código

1. **Tipo de cliente é definido na criação e é imutável.** Um carrinho criado
   como B2C não pode virar B2B (e vice-versa) — isso invalidaria os preços já
   salvos nos itens. Não implemente endpoint de troca de tipo; se necessário,
   o cliente da API deve criar um novo carrinho.

2. **Preço é sempre obtido do Catálogo no momento da adição/atualização do
   item, nunca aceito como input do chamador da API.** Se o corpo da
   requisição de `POST /carrinhos/{id}/itens` incluir um campo de preço,
   ignore-o silenciosamente e busque o preço real via `product_service`.

3. **Adicionar quantidade a um item já existente no carrinho deve somar à
   quantidade existente, não criar uma linha duplicada.** Identificação de
   "mesmo item" é por `sku_variacao` dentro do mesmo carrinho.

4. **Validação de estoque na adição (leitura, sem decremento).** Ao
   adicionar ou atualizar quantidade de um item, verifique que a quantidade
   total solicitada não excede `estoque_disponivel` da variação no Catálogo.
   Rejeite com erro claro se exceder. **Não decremente o estoque** — reserva/
   decremento de estoque é escopo de TASK futura (checkout).

5. **Regra de MOQ B2B no endpoint de validação de checkout.** Um carrinho
   `tipo_cliente=B2B` só é elegível (`elegivel=True`) se `total >= 350.00`.
   Carrinhos `tipo_cliente=B2C` não têm MOQ — são sempre elegíveis por essa
   regra (desde que tenham ao menos 1 item). Um carrinho vazio nunca é
   elegível, independente do tipo.

## Endpoints Requeridos (FastAPI)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/carrinhos` | Cria carrinho vazio. Body: `{"tipo_cliente": "b2c"\|"b2b"}`. Retorna `carrinho_id`. |
| `GET` | `/carrinhos/{carrinho_id}` | Retorna o carrinho completo, com itens, subtotais e total. |
| `POST` | `/carrinhos/{carrinho_id}/itens` | Adiciona item. Body: `{"produto_id", "sku_variacao", "quantidade"}`. Preço buscado internamente. |
| `PUT` | `/carrinhos/{carrinho_id}/itens/{sku_variacao}` | Atualiza quantidade de um item específico. `quantidade=0` remove o item. |
| `DELETE` | `/carrinhos/{carrinho_id}/itens/{sku_variacao}` | Remove um item do carrinho. |
| `GET` | `/carrinhos/{carrinho_id}/elegibilidade-checkout` | Retorna `ElegibilidadeCheckout` — se pode prosseguir, total, motivo se não puder. |

Erros HTTP semânticos: 404 se `carrinho_id` ou `sku_variacao` não existir, 400
para violação de regra de negócio (ex: estoque insuficiente), com corpo JSON
descritivo — mesmo padrão da TASK-0001.

## Requisitos Não-Funcionais

- **Testes:** `pytest`, cobertura mínima de **90%** do pacote `app/` completo
  (incluindo o que já existe do Catálogo — não deixe a média geral cair).
  Testes de regra de negócio devem incluir o caso de falha esperada para cada
  uma das 5 regras acima (ex: teste que tenta adicionar item além do estoque
  disponível e espera erro 400).
- **Sem placeholders:** mesma exigência da TASK-0001 — nenhum `TODO` ou
  lógica incompleta.
- **Logging:** `INFO` para criação de carrinho e adição de item, `WARNING`
  para tentativas de violação de regra de negócio (estoque insuficiente,
  MOQ não atingido).
- **Docstrings** em todas as funções públicas, mesmo padrão já usado no
  projeto.

## Critérios de Aceite

- [ ] Contrato Pydantic implementado exatamente como especificado.
- [ ] As 5 regras de negócio têm teste unitário dedicado, incluindo caso de
      falha esperada para cada uma.
- [ ] Os 6 endpoints implementados e testados (sucesso + ao menos 1 erro cada).
- [ ] Cobertura de teste ≥ 90% do pacote `app/` inteiro (rode
      `pytest --cov=app --cov-report=term-missing`, sem restringir a
      subpastas — isso já causou retrabalho na ticket anterior).
- [ ] Nenhuma chamada HTTP entre módulos internos — uso de função Python
      direta para consultar preço/estoque do Catálogo.
- [ ] Nenhuma dependência nova não justificada por escrito no PR.
- [ ] Nenhuma credencial commitada.

## Fora de Escopo (explicitamente)

- Checkout, pagamento, emissão de pedido — TASK-0003+.
- Decremento/reserva real de estoque — apenas leitura/validação nesta ticket.
- Autenticação de cliente final — carrinho é identificado só por `carrinho_id`.
- Expiração/limpeza automática de carrinhos abandonados — considerar em
  ticket futura se o volume justificar.
- Cupons de desconto, frete, ou qualquer cálculo além de `quantidade × preço`.

## Impacto Estimado em Custo/Cota (GCP)

- Mesmo Cloud Run e mesmo Firestore já provisionados para o Catálogo — sem
  serviço novo, sem custo de infraestrutura adicional.
- Firestore: coleção nova (`carrinhos`), mesmo Free Tier de 50k leituras/20k
  escritas por dia — volume de carrinho é tipicamente maior que catálogo,
  mas ainda bem abaixo do teto para o estágio atual do negócio.
- **Custo esperado: R$ 0,00/mês adicional** enquanto dentro do Free Tier do
  Firestore.
