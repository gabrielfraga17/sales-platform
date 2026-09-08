"""Router de endpoints para consulta de Pedidos."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.order import Pedido
from app.routers.cart_router import get_order_service
from app.services.order_service import OrderNotFoundError, OrderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get("/{pedido_id}", response_model=Pedido)
def obter_pedido(
    pedido_id: str,
    service: OrderService = Depends(get_order_service),
) -> Pedido:
    """Retorna o Pedido completo pelo seu ID único."""
    try:
        return service.get_order(pedido_id=pedido_id)
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
