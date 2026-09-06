"""Rotas e controladores REST para gerenciamento do catálogo de produtos."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.models.product import PrecoPorTipoCliente, Produto, ProdutoCreate, ProdutoUpdate, TipoCliente
from app.repositories.firestore_repository import (
    BaseProductRepository,
    FirestoreProductRepository,
    InMemoryProductRepository,
)
from app.services.product_service import (
    PriceNotAvailableError,
    ProductNotFoundError,
    ProductService,
    SKUConflictError,
)

router = APIRouter(prefix="/produtos", tags=["Produtos"])

# Repositório singleton compartilhado para injeção de dependência
_repo_instance: Optional[BaseProductRepository] = None


def get_repository() -> BaseProductRepository:
    """
    Injeta o repositório correto com base nas configurações da aplicação
    (InMemory ou Firestore real).
    """
    global _repo_instance
    if _repo_instance is None:
        if settings.USE_IN_MEMORY_DB:
            _repo_instance = InMemoryProductRepository()
        else:
            try:
                _repo_instance = FirestoreProductRepository()
            except Exception:
                # Fallback seguro para in-memory se Firestore não estiver configurado localmente
                _repo_instance = InMemoryProductRepository()
    return _repo_instance


def get_product_service(repo: BaseProductRepository = Depends(get_repository)) -> ProductService:
    """Injeta a instância do ProductService."""
    return ProductService(repository=repo)


@router.post("", response_model=Produto, status_code=status.HTTP_210_CREATED if hasattr(status, "HTTP_210_CREATED") else status.HTTP_201_CREATED)
@router.post("/", response_model=Produto, status_code=status.HTTP_201_CREATED)
def criar_produto(
    payload: ProdutoCreate,
    service: ProductService = Depends(get_product_service),
) -> Produto:
    """
    Cria um novo produto no catálogo.
    Validando regras de negócio e unicidade de SKU.
    """
    try:
        return service.create_product(payload)
    except SKUConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{produto_id}", response_model=Produto)
def obter_produto_por_id(
    produto_id: str,
    service: ProductService = Depends(get_product_service),
) -> Produto:
    """Retorna os detalhes de um produto pelo seu ID."""
    try:
        return service.get_product(produto_id)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("", response_model=List[Produto])
def listar_produtos(
    limit: int = Query(default=20, ge=1, le=100, description="Quantidade máxima de itens por página"),
    offset: int = Query(default=0, ge=0, description="Deslocamento de itens para paginação"),
    categoria: Optional[str] = Query(default=None, description="Filtro opcional por categoria"),
    service: ProductService = Depends(get_product_service),
) -> List[Produto]:
    """Lista os produtos ativos com paginação e filtro por categoria."""
    return service.list_products(limit=limit, offset=offset, categoria=categoria)


@router.put("/{produto_id}", response_model=Produto)
def atualizar_produto(
    produto_id: str,
    payload: ProdutoUpdate,
    service: ProductService = Depends(get_product_service),
) -> Produto:
    """Atualiza as informações de um produto existente."""
    try:
        return service.update_product(produto_id, payload)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SKUConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{produto_id}", response_model=Produto)
def remover_produto(
    produto_id: str,
    service: ProductService = Depends(get_product_service),
) -> Produto:
    """Realiza a exclusão lógica (soft delete) desativando o produto."""
    try:
        return service.delete_product(produto_id)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{produto_id}/preco", response_model=PrecoPorTipoCliente)
def consultar_preco_produto(
    produto_id: str,
    tipo_cliente: TipoCliente = Query(..., description="Tipo de cliente: b2c ou b2b"),
    service: ProductService = Depends(get_product_service),
) -> PrecoPorTipoCliente:
    """Consulta o preço aplicável a um produto para o tipo de cliente informado."""
    try:
        return service.get_product_price(produto_id, tipo_cliente)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PriceNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
