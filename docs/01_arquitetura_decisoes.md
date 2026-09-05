# ADR 001: Decisões de Arquitetura e Persistência de Dados

**Status**: Em Análise / Proposto  
**Data**: 2026-09-04  
**Contexto**: Escolha do banco de dados e arquitetura de dados para a plataforma `sales-platform`.

---

## 1. Comparativo de Bancos de Dados: Firestore vs. Cloud SQL

### Opção A: Google Cloud Firestore (NoSQL Serverless)
- **Vantagens**:
  - Totalmente gerenciado e serverless (escala automática sem provisionamento).
  - Atualizações em tempo real (real-time listeners via SDKs).
  - Integração nativa com Google Cloud IAM e regras de segurança refinadas.
  - Modelo de documentos JSON flexível (ideal para catálogos com atributos variados por produto).
- **Desvantagens**:
  - Consultas complexas com múltiplos JOINs ou agregações analíticas pesadas são mais trabalhosas.
  - Custos baseados em volume de operações de leitura/escrita.

### Opção B: Google Cloud SQL (PostgreSQL / MySQL)
- **Vantagens**:
  - Relacional com suporte completo a SQL, transações ACID rigorosas e JOINs complexos.
  - Ideal para relatórios de vendas pesados, fechamento financeiro e estoque com integridade referencial forte.
  - Compatível com ecossistema ORM (SQLAlchemy, Django ORM, Prisma).
- **Desvantagens**:
  - Requer gerenciamento de instância/tamanho de banco (mesmo gerenciado pela GCP).
  - Custo fixo por hora de instância em execução.

---

## 2. Recomendação Arquitetural

- **Fase Inicial / MVP**: Usar **Firestore** para o módulo de **Catálogo de Produtos** devido à flexibilidade de atributos e agilidade no modelo NoSQL serverless.
- **Evolução Analítica / Finanças**: Utilizar **Cloud SQL (PostgreSQL)** para transações financeiras e histórico de pedidos, ou exportar dados do Firestore diretamente para o **BigQuery** para analytics.

---

## 3. Decisões Pendentes

- [ ] Definir o framework principal do `app/` (FastAPI vs Flask vs Streamlit).
- [ ] Definir estratégia de autenticação de usuários (Firebase Auth / GCP Identity Platform).
- [ ] Configuração de bucket GCS para mídias/imagens do catálogo de produtos.
