"""Router de endpoints para gerenciamento do Carrinho de Compras."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.models.cart import Carrinho, ElegibilidadeCheckout
from app.models.product import TipoCliente
from app.repositories.cart_firestore_repository import BaseCartRepository, FirestoreCartRepository, InMemoryCartRepository
from app.repositories.firestore_repository import BaseProductRepository, FirestoreProductRepository, InMemoryProductRepository
from app.services.cart_service import (
    CartItemNotFoundError,
    CartNotFoundError,
    CartService,
    InsufficientStockError,
)
from app.services.product_service import PriceNotAvailableError, ProductNotFoundError, ProductService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carrinhos", tags=["Carrinho"])


class CreateCartRequest(BaseModel):
    tipo_cliente: TipoCliente


class AddCartItemRequest(BaseModel):
    produto_id: str
    sku_variacao: str
    quantidade: int = Field(gt=0)


class UpdateCartItemRequest(BaseModel):
    quantidade: int = Field(ge=0)


def get_cart_service() -> CartService:
    """Dependency injection para o CartService."""
    if settings.USE_IN_MEMORY_REPO:
        # Usa repositórios em memória globais simples para desenvolvimento/teste
        if not hasattr(get_cart_service, "_cart_repo"):
            get_cart_service._cart_repo = InMemoryCartRepository()
            get_cart_service._prod_repo = InMemoryProductRepository()
        cart_repo = get_cart_service._cart_repo
        prod_repo = get_cart_service._prod_repo
    else:
        cart_repo = FirestoreCartRepository()
        prod_repo = FirestoreProductRepository()

    product_service = ProductService(repository=prod_repo)
    return CartService(cart_repository=cart_repo, product_service=product_service)


@router.post("", response_model=Carrinho, status_code=status.HTTP_201_CREATED)
def criar_carrinho(
    payload: CreateCartRequest,
    service: CartService = Depends(get_cart_service),
) -> Carrinho:
    """Cria um carrinho vazio associado ao tipo de cliente."""
    return service.create_cart(tipo_cliente=payload.tipo_cliente)


@router.get("/{carrinho_id}", response_model=Carrinho)
def obter_carrinho(
    carrinho_id: str,
    service: CartService = Depends(get_cart_service),
) -> Carrinho:
    """Obtém um carrinho completo pelo seu ID."""
    try:
        return service.get_cart(carrinho_id=carrinho_id)
    except CartNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{carrinho_id}/itens", response_model=Carrinho)
def adicionar_item_carrinho(
    carrinho_id: str,
    payload: AddCartItemRequest,
    service: CartService = Depends(get_cart_service),
) -> Carrinho:
    """Adiciona um item ao carrinho. Preço é obtido internamente pelo Catálogo."""
    try:
        return service.add_item(
            carrinho_id=carrinho_id,
            produto_id=payload.produto_id,
            sku_variacao=payload.sku_variacao,
            quantidade=payload.quantidade,
        )
    except CartNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ProductNotFoundError, PriceNotAvailableError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{carrinho_id}/itens/{sku_variacao}", response_model=Carrinho)
def atualizar_quantidade_item(
    carrinho_id: str,
    sku_variacao: str,
    payload: UpdateCartItemRequest,
    service: CartService = Depends(get_cart_service),
) -> Carrinho:
    """Atualiza a quantidade de um item no carrinho. Se quantidade=0, remove o item."""
    try:
        return service.update_item_quantity(
            carrinho_id=carrinho_id,
            sku_variacao=sku_variacao,
            quantidade=payload.quantidade,
        )
    except (CartNotFoundError, CartItemNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{carrinho_id}/itens/{sku_variacao}", response_model=Carrinho)
def remover_item_carrinho(
    carrinho_id: str,
    sku_variacao: str,
    service: CartService = Depends(get_cart_service),
) -> Carrinho:
    """Remove um item do carrinho."""
    try:
        return service.remove_item(carrinho_id=carrinho_id, sku_variacao=sku_variacao)
    except (CartNotFoundError, CartItemNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{carrinho_id}/elegibilidade-checkout", response_model=ElegibilidadeCheckout)
def verificar_elegibilidade_checkout(
    carrinho_id: str,
    service: CartService = Depends(get_cart_service),
) -> ElegibilidadeCheckout:
    """Verifica se o carrinho está elegível para checkout, incluindo regras de MOQ B2B."""
    try:
        return service.check_checkout_eligibility(carrinho_id=carrinho_id)
    except CartNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
