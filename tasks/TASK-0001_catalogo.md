# TASK-0001 — Módulo de Catálogo (Sales Platform)

## Status
`READY_FOR_IMPLEMENTATION`

## Contexto de Negócio
Plataforma de vendas B2C + B2B (Atacado) para moda branca e semijoias/acessórios rituais do nicho de Umbanda e Espiritualidade de Matriz Africana. Regras de negócio já travadas (ver `docs/01_visao_negocio_e_personas.md`):

- **B2C (Varejo)**: venda direta ao consumidor final, preço cheio.
- **B2B (Atacado)**: revendedoras e casas de artigos religiosos. Pedido mínimo (MOQ) de **R$ 350,00** e margem superior a **100%** para o lojista sobre o preço de custo.
- Um mesmo produto pode ter **preços diferentes** conforme o tipo de cliente (B2C vs B2B), mas é a mesma entidade de catálogo — não duplicar produto por canal.

Este módulo é a fundação da Sales Platform. **Não inclui** carrinho, checkout, pagamento ou autenticação de cliente — isso é escopo de tickets futuros (TASK-0002+).

## Objetivo
Implementar um serviço de Catálogo que permita:
1. Cadastrar produtos com variações (ex: tamanho, cor).
2. Definir preço por tipo de cliente (B2C / B2B) por produto.
3. Consultar produtos e preços via API, já preparado para ser consumido pelo módulo de Carrinho (TASK-0002) e, futuramente, por uma camada de leitura do Hub Operacional (BigQuery/Sheets) para destacar produtos com Fit Score alto — **essa integração está fora do escopo desta ticket**, mas o schema não deve impedi-la (manter `sku` como chave estável e previsível).

## Stack e Decisões de Arquitetura (não negociáveis nesta ticket)
- **Linguagem:** Python 3.11+, com type hints em 100% das funções públicas.
- **Framework API:** FastAPI.
- **Validação de dados:** Pydantic v2 (todos os contratos de entrada/saída como modelos Pydantic, não dicts soltos).
- **Banco de dados:** Firestore (modo nativo), via `google-cloud-firestore`. Justificativa: custo zero em repouso, alinhado ao princípio de Free Tier/serverless já adotado no Hub Operacional. Não usar Cloud SQL nesta fase.
- **Deploy alvo:** Cloud Run (2ª geração), região `southamerica-east1`. Incluir `Dockerfile` funcional.
- **Autenticação do serviço:** Service Account com permissão mínima (`roles/datastore.user` apenas) — não usar credenciais de usuário (ADC pessoal).
- **Sem dependências externas não justificadas.** Qualquer biblioteca além de `fastapi`, `pydantic`, `google-cloud-firestore`, `uvicorn` e bibliotecas de teste (`pytest`, `pytest-cov`) precisa de justificativa por escrito no PR.

## Contrato de Dados (Pydantic — implementar exatamente estes campos, tipos podem ser refinados com justificativa)

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TipoCliente(str, Enum):
    B2C = "b2c"
    B2B = "b2b"

class PrecoPorTipoCliente(BaseModel):
    tipo_cliente: TipoCliente
    preco_unitario: float = Field(gt=0, description="Preço em BRL, sempre positivo")
    margem_minima_revenda_pct: Optional[float] = Field(
        default=None,
        description="Apenas para tipo_cliente=B2B. Deve ser >= 100.0 conforme regra de negócio (margem >100% para o lojista)."
    )

class VariacaoProduto(BaseModel):
    sku_variacao: str = Field(description="SKU único da variação, ex: COLAR-BRANCO-P")
    atributos: dict[str, str] = Field(description="Ex: {'tamanho': 'P', 'cor': 'branco'}")
    estoque_disponivel: int = Field(ge=0)

class Produto(BaseModel):
    produto_id: str = Field(description="ID único, gerado pelo sistema")
    sku_base: str = Field(description="SKU base do produto, estável — usado por integrações futuras")
    nome: str
    descricao: str
    pilar_conteudo: Optional[str] = Field(
        default=None,
        description="Vínculo opcional com pilar de conteúdo do Hub (ex: 'Estilo & Modaxé'). Campo livre, sem validação de enum nesta ticket."
    )
    categoria: str
    variacoes: list[VariacaoProduto] = Field(min_length=1, description="Todo produto tem ao menos 1 variação")
    precos: list[PrecoPorTipoCliente] = Field(
        min_length=1,
        description="Todo produto deve ter preço B2C definido. Preço B2B é opcional (nem todo produto é vendido no atacado)."
    )
    ativo: bool = Field(default=True)
    criado_em: datetime
    atualizado_em: datetime
```

## Regras de Negócio a Validar no Código (não apenas documentar — implementar checagem)

1. Todo `Produto` deve ter **exatamente um** `PrecoPorTipoCliente` com `tipo_cliente=B2C`. Rejeitar criação/atualização se ausente.
2. Se existir `PrecoPorTipoCliente` com `tipo_cliente=B2B`, o campo `margem_minima_revenda_pct` é obrigatório e deve ser `>= 100.0`. Rejeitar caso contrário (`ValueError` explícito, não silencioso).
3. `sku_base` e `sku_variacao` devem ser únicos em toda a coleção — validar antes de escrever no Firestore (checagem de unicidade, não apenas confiar no índice).
4. `estoque_disponivel` nunca pode ser negativo — a validação do Pydantic (`ge=0`) já cobre entrada, mas garantir que nenhuma operação de decremento (mesmo que não implementada nesta ticket) deixe brecha para valor negativo no futuro (comentário no código é suficiente, não implementar decremento agora).

## Endpoints Requeridos (FastAPI)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/produtos` | Cria produto (valida regras acima) |
| `GET` | `/produtos/{produto_id}` | Retorna produto por ID |
| `GET` | `/produtos` | Lista produtos ativos, com paginação (`limit`, `offset`) e filtro opcional por `categoria` |
| `PUT` | `/produtos/{produto_id}` | Atualiza produto (mesmas validações da criação) |
| `DELETE` | `/produtos/{produto_id}` | Soft delete — seta `ativo=false`, nunca remove documento do Firestore |
| `GET` | `/produtos/{produto_id}/preco` | Retorna preço aplicável, recebendo `tipo_cliente` como query param |

Todos os endpoints devem retornar erros HTTP semânticos (400 para validação, 404 para não encontrado, 409 para conflito de SKU) com corpo JSON descritivo — não usar `500` genérico para erros de validação previsíveis.

## Requisitos Não-Funcionais

- **Testes:** `pytest`, cobertura mínima de **90%** nas regras de negócio (item "Regras de Negócio" acima) e nos endpoints. Usar Firestore emulator ou mock — não depender de projeto GCP real para rodar os testes.
- **Documentação:** Docstrings em todas as funções públicas (padrão Google ou NumPy, escolher um e manter consistente).
- **Sem placeholders:** nenhum `# TODO`, `pass  # implementar depois` ou trecho comentado substituindo lógica real. Código entregue deve rodar de ponta a ponta.
- **Logging:** usar `logging` padrão do Python (não `print`), nível `INFO` para operações de escrita, `WARNING` para tentativas de violação de regra de negócio.

## Critérios de Aceite (checklist para o Code Review)

- [ ] Todos os campos do contrato Pydantic implementados com os tipos especificados.
- [ ] As 4 regras de negócio da seção acima têm teste unitário dedicado, incluindo caso de falha esperada (ex: teste que tenta criar produto B2B com margem de 80% e espera `ValueError`).
- [ ] Os 6 endpoints implementados e testados (sucesso + pelo menos 1 caso de erro cada).
- [ ] Cobertura de teste ≥ 90% (relatório `pytest-cov` anexado no PR).
- [ ] `Dockerfile` construído com sucesso localmente (`docker build`).
- [ ] Nenhuma dependência fora da lista autorizada sem justificativa.
- [ ] Nenhuma credencial ou chave de Service Account commitada no repositório.

## Fora de Escopo (explicitamente, para evitar scope creep)
- Carrinho de compras, cálculo de MOQ (R$350), checkout, pagamento.
- Autenticação de usuário/cliente final.
- Upload de imagens de produto (assumir campo `url_imagem: Optional[str]` simples nesta ticket, sem lógica de upload).
- Integração real com o Hub Operacional (BigQuery/Sheets) — apenas manter `sku_base` estável para viabilizar isso depois.

## Impacto Estimado em Custo/Cota (GCP)
- Firestore: gratuito até 50k leituras/20k escritas por dia (Free Tier) — catálogo de um negócio de nicho fica bem abaixo disso mesmo com tráfego de vitrine.
- Cloud Run: escala a zero quando ocioso, sem custo fixo.
- **Custo esperado nesta fase: R$ 0,00/mês** enquanto o volume não ultrapassar o Free Tier.
