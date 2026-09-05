# TASK-0001: Módulo de Catálogo de Produtos e Vendas

**Status**: 📋 A Fazer / Em Planejamento  
**Prioridade**: Alta  
**Componente**: `app/catalog`  

---

## 🎯 Objetivo
Desenvolver o módulo de gerenciamento do **Catálogo de Produtos**, permitindo a criação, listagem, atualização e categorização de itens para vendas.

---

## 📌 Requisitos Funcionais

1. **Cadastro de Produtos**:
   - Nome, descrição, SKU/código do produto.
   - Categoria e subcategoria.
   - Preço de venda, preço de custo, moeda (BRL).
   - Atributos dinâmicos (tamanho, cor, especificações técnicas).
   - Status do item (ativo, inativo, fora de estoque).

2. **Consulta e Filtros**:
   - Listagem com paginação e busca por nome ou SKU.
   - Filtros por categoria e faixa de preço.

3. **Gerenciamento de Imagens**:
   - Upload de imagens do produto para o Google Cloud Storage (GCS).

---

## 🛠️ Especificação Técnica & Modelo de Dados

### Modelo de Documento (Firestore - Coleção `products`)
```json
{
  "id": "prod_12345",
  "sku": "PROD-001",
  "name": "Produto Exemplo",
  "description": "Descrição detalhada do produto.",
  "category": "Eletrônicos",
  "price": 199.90,
  "cost_price": 120.00,
  "stock_quantity": 50,
  "status": "active",
  "images": [
    "https://storage.googleapis.com/meu-bucket-sales/products/prod_12345_1.jpg"
  ],
  "attributes": {
    "voltagem": "220V",
    "cor": "Preto"
  },
  "created_at": "2026-09-04T23:00:00Z",
  "updated_at": "2026-09-04T23:00:00Z"
}
```

---

## ✅ Critérios de Aceite

- [ ] Endpoints ou interfaces de CRUD de produtos funcionando.
- [ ] Validação de dados (preço > 0, SKU único, campos obrigatórios).
- [ ] Testes unitários cobrindo o fluxo de criação e edição.
- [ ] Integração com banco de dados configurada.
