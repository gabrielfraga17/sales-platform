"""Serviço de gerenciamento do catálogo de produtos e aplicação das regras de negócio."""

from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

from app.models.product import PrecoPorTipoCliente, Produto, ProdutoCreate, ProdutoUpdate, TipoCliente
from app.repositories.firestore_repository import BaseProductRepository

logger = logging.getLogger(__name__)


class ProductNotFoundError(Exception):
    """Exceção para quando um produto não for encontrado."""

    pass


class SKUConflictError(Exception):
    """Exceção para quando um SKU já existe cadastrado na base."""

    pass


class PriceNotAvailableError(Exception):
    """Exceção para quando um preço específico de tipo de cliente não estiver configurado."""

    pass


class ProductService:
    """Serviço que gerencia operações de catálogo e aplica validações de negócio."""

    def __init__(self, repository: BaseProductRepository) -> None:
        self.repository = repository

    def create_product(self, payload: ProdutoCreate) -> Produto:
        """
        Cria um novo produto no catálogo garantindo unicidade de SKU e validações de regras.
        """
        skus_variacao = [v.sku_variacao for v in payload.variacoes]
        sku_duplicado = self.repository.check_sku_exists(payload.sku_base, skus_variacao)
        if sku_duplicado:
            logger.warning("Tentativa de criar produto com SKU duplicado: %s", sku_duplicado)
            raise SKUConflictError(f"O SKU '{sku_duplicado}' já está cadastrado no sistema.")

        now = datetime.now(timezone.utc)
        produto_id = f"prod_{uuid.uuid4().hex[:10]}"

        produto = Produto(
            produto_id=produto_id,
            sku_base=payload.sku_base,
            nome=payload.nome,
            descricao=payload.descricao,
            pilar_conteudo=payload.pilar_conteudo,
            categoria=payload.categoria,
            variacoes=payload.variacoes,
            precos=payload.precos,
            ativo=True,
            criado_em=now,
            atualizado_em=now,
        )

        salvo = self.repository.save(produto)
        logger.info("Produto criado com sucesso: id=%s, sku_base=%s", salvo.produto_id, salvo.sku_base)
        return salvo

    def get_product(self, produto_id: str) -> Produto:
        """Busca um produto pelo ID."""
        produto = self.repository.get_by_id(produto_id)
        if not produto:
            raise ProductNotFoundError(f"Produto com ID '{produto_id}' não foi encontrado.")
        return produto

    def list_products(
        self, limit: int = 20, offset: int = 0, categoria: Optional[str] = None
    ) -> List[Produto]:
        """Lista os produtos ativos cadastrados com suporte a paginação e filtro."""
        return self.repository.list_active(limit=limit, offset=offset, categoria=categoria)

    def update_product(self, produto_id: str, payload: ProdutoUpdate) -> Produto:
        """Atualiza um produto existente."""
        existente = self.get_product(produto_id)

        sku_base_check = payload.sku_base or existente.sku_base
        variacoes_check = payload.variacoes if payload.variacoes is not None else existente.variacoes
        skus_variacao_check = [v.sku_variacao for v in variacoes_check]

        sku_duplicado = self.repository.check_sku_exists(
            sku_base=sku_base_check,
            skus_variacao=skus_variacao_check,
            exclude_produto_id=produto_id,
        )
        if sku_duplicado:
            logger.warning(
                "Tentativa de atualizar produto %s com SKU duplicado: %s",
                produto_id,
                sku_duplicado,
            )
            raise SKUConflictError(f"O SKU '{sku_duplicado}' já pertence a outro produto.")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return existente

        current_dict = existente.model_dump()
        current_dict.update(update_data)
        current_dict["atualizado_em"] = datetime.now(timezone.utc)

        produto_atualizado = Produto.model_validate(current_dict)
        salvo = self.repository.save(produto_atualizado)
        logger.info("Produto %s atualizado com sucesso.", produto_id)
        return salvo

    def delete_product(self, produto_id: str) -> Produto:
        """Soft delete: define ativo=False para desativar o produto."""
        existente = self.get_product(produto_id)
        if not existente.ativo:
            return existente

        existente.ativo = False
        existente.atualizado_em = datetime.now(timezone.utc)
        salvo = self.repository.save(existente)
        logger.info("Produto %s desativado (soft delete).", produto_id)
        return salvo

    def get_product_price(self, produto_id: str, tipo_cliente: TipoCliente) -> PrecoPorTipoCliente:
        """Retorna a estrutura de preço aplicável ao produto de acordo com o tipo de cliente."""
        produto = self.get_product(produto_id)
        for preco in produto.precos:
            if preco.tipo_cliente == tipo_cliente:
                return preco

        raise PriceNotAvailableError(
            f"Preço para tipo de cliente '{tipo_cliente.value}' não está configurado para este produto."
        )
