"""Camada de repositório para acesso aos dados do Produto (Firestore e In-Memory)."""

from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Optional
from app.config import settings
from app.models.product import Produto

logger = logging.getLogger(__name__)


class BaseProductRepository(ABC):
    """Interface abstrata para persistência de produtos."""

    @abstractmethod
    def save(self, produto: Produto) -> Produto:
        """Salva ou atualiza um produto."""
        pass

    @abstractmethod
    def get_by_id(self, produto_id: str) -> Optional[Produto]:
        """Obtém um produto pelo seu ID único."""
        pass

    @abstractmethod
    def list_active(self, limit: int = 20, offset: int = 0, categoria: Optional[str] = None) -> List[Produto]:
        """Lista produtos ativos com suporte a paginação e filtro opcional por categoria."""
        pass

    @abstractmethod
    def check_sku_exists(self, sku_base: str, skus_variacao: List[str], exclude_produto_id: Optional[str] = None) -> Optional[str]:
        """
        Verifica se um sku_base ou qualquer sku_variacao já existe na base de dados.
        Retorna a string do SKU duplicado se encontrado, ou None se todos forem únicos.
        """
        pass


class InMemoryProductRepository(BaseProductRepository):
    """Repositório em memória para uso em testes unitários e desenvolvimento offline."""

    def __init__(self) -> None:
        self._storage: Dict[str, Produto] = {}

    def save(self, produto: Produto) -> Produto:
        self._storage[produto.produto_id] = produto.model_copy()
        logger.info("Produto armazenado em memória: %s (id=%s)", produto.nome, produto.produto_id)
        return produto

    def get_by_id(self, produto_id: str) -> Optional[Produto]:
        produto = self._storage.get(produto_id)
        if produto:
            return produto.model_copy()
        return None

    def list_active(self, limit: int = 20, offset: int = 0, categoria: Optional[str] = None) -> List[Produto]:
        produtos = [p.model_copy() for p in self._storage.values() if p.ativo]
        if categoria:
            produtos = [p for p in produtos if p.categoria.lower() == categoria.lower()]
        
        # Ordenação estável por criado_em
        produtos.sort(key=lambda x: x.criado_em, reverse=True)
        return produtos[offset : offset + limit]

    def check_sku_exists(self, sku_base: str, skus_variacao: List[str], exclude_produto_id: Optional[str] = None) -> Optional[str]:
        for prod in self._storage.values():
            if exclude_produto_id and prod.produto_id == exclude_produto_id:
                continue
            
            if prod.sku_base.upper() == sku_base.upper():
                return prod.sku_base
            
            for var in prod.variacoes:
                if var.sku_variacao.upper() == sku_base.upper():
                    return var.sku_variacao
                for target_var_sku in skus_variacao:
                    if var.sku_variacao.upper() == target_var_sku.upper() or prod.sku_base.upper() == target_var_sku.upper():
                        return target_var_sku
        return None


class FirestoreProductRepository(BaseProductRepository):
    """Repositório oficial integrando com o Google Cloud Firestore."""

    def __init__(self) -> None:
        from google.cloud import firestore  # lazy import
        self.db = firestore.Client(project=settings.GCP_PROJECT_ID)
        self.collection_name = settings.FIRESTORE_COLLECTION_PRODUCTS
        self.collection = self.db.collection(self.collection_name)

    def save(self, produto: Produto) -> Produto:
        doc_ref = self.collection.document(produto.produto_id)
        doc_ref.set(produto.model_dump(mode="json"))
        logger.info("Produto salvo no Firestore: %s (id=%s)", produto.nome, produto.produto_id)
        return produto

    def get_by_id(self, produto_id: str) -> Optional[Produto]:
        doc_ref = self.collection.document(produto_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Produto.model_validate(data)

    def list_active(self, limit: int = 20, offset: int = 0, categoria: Optional[str] = None) -> List[Produto]:
        query = self.collection.where("ativo", "==", True)
        if categoria:
            query = query.where("categoria", "==", categoria)
        
        # Paginação simples
        docs = query.offset(offset).limit(limit).stream()
        produtos = []
        for doc in docs:
            produtos.append(Produto.model_validate(doc.to_dict()))
        return produtos

    def check_sku_exists(self, sku_base: str, skus_variacao: List[str], exclude_produto_id: Optional[str] = None) -> Optional[str]:
        # Busca por sku_base
        query_base = self.collection.where("sku_base", "==", sku_base).limit(1).stream()
        for doc in query_base:
            if exclude_produto_id and doc.id == exclude_produto_id:
                continue
            return sku_base

        # Busca simples iterando nos documentos ativos para conferência de unicidade de variação
        docs = self.collection.stream()
        for doc in docs:
            if exclude_produto_id and doc.id == exclude_produto_id:
                continue
            data = doc.to_dict()
            prod_sku_base = data.get("sku_base", "").upper()
            if prod_sku_base == sku_base.upper():
                return sku_base
            
            variacoes = data.get("variacoes", [])
            for var in variacoes:
                var_sku = var.get("sku_variacao", "").upper()
                if var_sku == sku_base.upper():
                    return var_sku
                for target_var_sku in skus_variacao:
                    if var_sku == target_var_sku.upper() or prod_sku_base == target_var_sku.upper():
                        return target_var_sku
        return None
