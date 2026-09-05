# Plano de Implementação — Da Fundação de Dados (Fase 0) até a TASK-0001 (Catálogo)

## Visão Geral

Duas trilhas rodam em paralelo, porque têm donos diferentes e não competem pelo mesmo tempo:

```
TRACK A (Sócia + setup pontual do Gabriel)
  Fase 0 do Hub — Fundação de Dados
  └─> roda em background, ~3-4 semanas, baixo esforço técnico

TRACK B (Gabriel, técnico)
  Preparação da Sales Platform
  └─> pode começar HOJE, não depende do Track A

TRACK C (Gabriel + DeepSeek, técnico)
  Execução da TASK-0001 (Catálogo)
  └─> começa assim que Track B estiver pronto (não espera Track A terminar)
```

O único ponto de sincronização real é: **Track A precisa estar rodando antes de você considerar a Fase 2 do Hub (retroalimentação do Fit Score)** — mas isso é depois da TASK-0001, não bloqueia o catálogo.

---

## TRACK A — Fase 0 do Hub: Fundação de Dados

**Responsável principal:** sócia (preenchimento). **Setup:** você, uma vez só.

### Etapa A1 — Criar a aba `Resultados_Publicacao` no Sheets
**Quem:** você. **Tempo:** ~1-2h.

1. Abrir a planilha de produção do Hub.
2. Criar nova aba `Resultados_Publicacao` com colunas:
   `pauta_id | pilar | canal | data_publicacao | views | saves | compartilhamentos | comentarios | cliques_link | leads_b2b_gerados | gasto_ads | receita_atribuida`
3. Em `Backlog_Pautas`, confirmar que existe (ou criar) a coluna `pauta_id` como chave única — se ainda não existir, gerar um ID sequencial simples (`PAUTA-0001`, `PAUTA-0002`...) para as pautas já publicadas.
4. Proteger as colunas de fórmula (se você calcular ROI depois nesta mesma aba) contra edição acidental da sócia — `Dados > Proteger intervalos`.

**Critério de saída da etapa:** aba existe, colunas validadas, pelo menos 1 linha de teste preenchida por você para conferir o formato.

### Etapa A2 — Treinar a sócia no preenchimento
**Quem:** você + sócia. **Tempo:** ~30 min, uma conversa.

1. Mostrar onde pegar cada métrica (Instagram Insights, TikTok Analytics) — idealmente print de tela de cada um mostrando exatamente qual número copiar.
2. Combinar uma rotina: preencher a linha **48h após publicar** (tempo suficiente pra métrica orgânica estabilizar, mas não tanto que ela esqueça).
3. Deixar claro que `leads_b2b_gerados` é uma contagem manual dela mesma (mensagens de lojista interessado, por ex.) — não tem como automatizar isso ainda.

**Critério de saída:** sócia preenche 1 linha sozinha, sem sua ajuda, e você confere se está correta.

### Etapa A3 — Coleta contínua
**Quem:** sócia, ongoing. **Duração:** 3-4 semanas.

- Meta: **15-20 publicações** com dado preenchido antes de qualquer cálculo de conversão por pilar fazer sentido estatisticamente.
- Você não precisa fazer nada tecnicamente nesta etapa — só acompanhar 1x por semana se ela está preenchendo (evitar descobrir com 4 semanas de atraso que parou na segunda publicação).

**✅ Checkpoint de saída do Track A:** 15-20 linhas preenchidas → só então faz sentido abrir a Fase 1 (dashboard) e Fase 2 (retroalimentação) do Hub, discutidas anteriormente. Isso roda independente do Track B/C.

---

## TRACK B — Preparação Técnica da Sales Platform

**Responsável:** você. **Pode começar imediatamente**, em paralelo ao Track A.

### Etapa B1 — Decisão de repositório
**Tempo:** 15 min.

Recomendo **repositório separado** do `Hub_axe_40`, não monorepo — são dois sistemas com ciclos de deploy e times (mesmo que o "time" seja só você + DeepSeek) diferentes.

```bash
# No GitHub, criar novo repo (pode ser via CLI se tiver gh instalado)
gh repo create gabrielfraga17/sales-platform --public --clone
cd sales-platform
mkdir -p app docs tasks tests
```

Estrutura inicial:
```
sales-platform/
├── README.md
├── docs/
│   └── 01_arquitetura_decisoes.md   # registrar Firestore vs Cloud SQL, etc.
├── tasks/
│   └── TASK-0001_catalogo.md         # mover o arquivo que já geramos pra cá
├── app/
├── tests/
└── requirements.txt
```

### Etapa B2 — Setup do projeto GCP
**Tempo:** ~30 min.

1. Decidir: **novo projeto GCP** dedicado à Sales Platform, ou mesmo projeto do Hub com recursos separados? Recomendo **novo projeto** — isolamento de billing e IAM mais limpo, e evita que um bug na Sales Platform consuma cota do Hub.

```bash
gcloud projects create sales-platform-axe --name="Sales Platform Hub Axé"
gcloud config set project sales-platform-axe

# Habilitar APIs necessárias
gcloud services enable firestore.googleapis.com run.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com
```

2. Criar o Firestore (modo nativo, mesma região do Hub para latência):
```bash
gcloud firestore databases create --location=southamerica-east1
```

3. Criar Service Account com privilégio mínimo (conforme exigido na ticket):
```bash
gcloud iam service-accounts create sales-catalog-sa \
  --display-name="Sales Catalog Service Account"

gcloud projects add-iam-policy-binding sales-platform-axe \
  --member="serviceAccount:sales-catalog-sa@sales-platform-axe.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

**Critério de saída:** `gcloud firestore databases list` mostra o banco criado; service account existe com apenas a role acima (nenhuma role de Owner/Editor).

### Etapa B3 — Ambiente local de desenvolvimento
**Tempo:** ~20 min.

```bash
cd sales-platform
python3.11 -m venv venv
source venv/bin/activate
pip install fastapi pydantic "uvicorn[standard]" google-cloud-firestore pytest pytest-cov

# Firestore emulator para testar sem custo e sem tocar produção
gcloud components install cloud-firestore-emulator
```

Adicionar `requirements.txt` com as versões travadas (`pip freeze > requirements.txt` depois de instalar).

**Critério de saída:** `uvicorn` roda um "hello world" FastAPI local, emulador do Firestore sobe sem erro (`gcloud emulators firestore start`).

### Etapa B4 — Commitar a ticket e abrir o board de tasks
**Tempo:** 10 min.

```bash
cp TASK-0001_catalogo.md sales-platform/tasks/
cd sales-platform
git add .
git commit -m "docs: setup inicial + TASK-0001 catálogo"
git push
```

**✅ Checkpoint de saída do Track B:** repositório criado, GCP configurado, ambiente local funcional, ticket versionada no repo (não mais um arquivo solto).

---

## TRACK C — Execução da TASK-0001 com o DeepSeek

**Pré-requisito:** Track B completo. **Não depende do Track A.**

### Etapa C1 — Prompt inicial ao DeepSeek
**Quem:** você, no ambiente/harness do DeepSeek (Project ou CLI, conforme você já usa).

Instrução a passar (adaptar ao formato do seu harness):

> Você é o Engineering Agent do projeto Sales Platform. Leia o arquivo `tasks/TASK-0001_catalogo.md` neste repositório e implemente exatamente o que está especificado — sem adicionar funcionalidade fora do "Fora de Escopo". Siga o ciclo: ler a ticket → planejar a estrutura de arquivos → implementar → escrever testes → rodar testes → corrigir até passar. Ao final, gere um `implementation_report.md` na pasta `tasks/` descrevendo o que foi feito, decisões tomadas e cobertura de teste alcançada.

### Etapa C2 — Ciclo de implementação (feito pelo DeepSeek)
Sem intervenção sua, exceto se ele travar em alguma ambiguidade — nesse caso, ele deve perguntar, não assumir.

### Etapa C3 — Validação local (você)
**Tempo:** ~15 min.

```bash
cd sales-platform
source venv/bin/activate
pytest --cov=app --cov-report=term-missing
```

Confirmar: cobertura ≥ 90% (exigido na ticket), nenhum teste falhando.

```bash
docker build -t sales-catalog .
docker run -p 8080:8080 sales-catalog
curl http://localhost:8080/produtos
```

### Etapa C4 — Code review comigo (Claude)
**Quem:** você me traz o código gerado (ou o repo, se eu tiver acesso via GitHub tool).

Peço que você cole aqui (ou eu leio via ferramenta) os arquivos implementados + `implementation_report.md`, e eu reviso contra:
- As 4 regras de negócio da ticket (com teste de falha esperada para cada uma).
- Os 6 endpoints e seus contratos.
- Ausência de placeholders/TODOs.
- Aderência ao Firestore (não Cloud SQL) e ao Service Account de privilégio mínimo.

Retorno: `APPROVE` ou `CHANGES_REQUIRED` com lista específica.

### Etapa C5 — Ciclo de correção (se necessário)
Se `CHANGES_REQUIRED`, você repassa minha lista ao DeepSeek, ele corrige, volta pra Etapa C3.

### Etapa C6 — Deploy em staging
**Tempo:** ~10 min.

```bash
gcloud run deploy sales-catalog-staging \
  --source . \
  --region southamerica-east1 \
  --service-account sales-catalog-sa@sales-platform-axe.iam.gserviceaccount.com \
  --allow-unauthenticated=false \
  --no-cpu-throttling=false
```

*(mantenho `--allow-unauthenticated=false` por padrão em staging — não é o mesmo IAP do Hub ainda, mas evita exposição pública prematura; ajustamos autenticação de cliente final numa ticket futura.)*

### Etapa C7 — Validação manual dos endpoints
Usar `curl` ou Postman contra a URL de staging, testando os 6 endpoints com casos de sucesso e os casos de erro (SKU duplicado, margem B2B < 100%, produto sem preço B2C).

### Etapa C8 — Merge e tag
```bash
git tag v0.1.0-catalogo
git push --tags
```

**✅ Checkpoint de saída do Track C:** endpoints funcionando em staging, cobertura de teste documentada, ticket TASK-0002 (Carrinho + MOQ) pronta para ser redigida com base no que foi de fato implementado aqui (não no que foi especulado).

---

## Timeline Sugerida

| Semana | Track A (sócia) | Track B (você) | Track C (você + DeepSeek) |
|---|---|---|---|
| 1 | Etapas A1-A2 (setup + treino) | Etapas B1-B4 (repo, GCP, ambiente) | — |
| 2 | Coleta contínua (A3) | — | Etapas C1-C3 (implementação + testes locais) |
| 3 | Coleta contínua (A3) | — | Etapas C4-C5 (review + correções) |
| 4 | Checkpoint: 15-20 publicações coletadas | — | Etapas C6-C8 (deploy + tag) |

Ao final da semana 4, os dois tracks convergem: Track A libera a Fase 2 do Hub (retroalimentação), Track C libera a TASK-0002 (Carrinho).

## Riscos e Mitigação

| Risco | Mitigação |
|---|---|
| Sócia esquece de preencher `Resultados_Publicacao` | Checagem semanal leve por você (Etapa A3), não deixar acumular |
| DeepSeek extrapola escopo (implementa carrinho junto) | Seção "Fora de Escopo" da ticket é explícita — rejeitar no code review (Etapa C4) |
| Custo GCP surpresa | Firestore + Cloud Run ficam no Free Tier neste volume — conferir no Billing após 1 semana de staging ativo |
| Dois projetos GCP aumentam complexidade de gestão | Aceitável nesta fase — isolamento vale mais que simplicidade de billing único, dado que são sistemas com ciclos de vida diferentes |
