"""Serviço de gerenciamento do processo de Checkout e criação de Pedidos."""

from datetime import datetime, timezone
import logging
import uuid
from typing import List, Optional

from app.models.cart import Carrinho
from app.models.order import (
    DadosComprador,
    FinalizarCheckoutRequest,
    ItemPedido,
    Pedido,
    StatusPedido,
)
from app.models.product import TipoCliente
from app.repositories.order_firestore_repository import BaseOrderRepository
from app.services.cart_service import CartNotFoundError, CartService

logger = logging.getLogger(__name__)


class CartNotEligibleError(Exception):
    """Exceção para quando o carrinho não está elegível para checkout."""

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(motivo)


class CartAlreadyFinalizedError(Exception):
    """Exceção para quando o carrinho já foi finalizado anteriormente."""

    pass


class InvalidBuyerDataError(Exception):
    """Exceção para quando os dados do comprador são inválidos (ex: B2B sem razao_social/cnpj)."""

    pass


class StockCommitError(Exception):
    """Exceção para quando o estoque é insuficiente durante a transação de checkout."""

    def __init__(self, skus: List[str]) -> None:
        self.skus = skus
        super().__init__(f"Estoque insuficiente para os SKUs no momento do checkout: {', '.join(skus)}")


class OrderNotFoundError(Exception):
    """Exceção para quando um pedido não é encontrado."""

    pass


class OrderService:
    """Serviço responsável por coordenar a finalização do checkout e criação do pedido."""

    def __init__(
        self,
        order_repository: BaseOrderRepository,
        cart_service: CartService,
    ) -> None:
        self.order_repository = order_repository
        self.cart_service = cart_service

    def _validar_dados_comprador_b2b(self, tipo_cliente: TipoCliente, comprador: DadosComprador) -> None:
        """Valida se dados de B2B (razao_social e cnpj) estão preenchidos se tipo_cliente == B2B."""
        if tipo_cliente == TipoCliente.B2B:
            razao_social_str = (comprador.razao_social or "").strip()
            cnpj_str = (comprador.cnpj or "").strip()
            if not razao_social_str or not cnpj_str:
                logger.warning(
                    "Tentativa de checkout B2B rejeitada por dados incompletos: razao_social='%s', cnpj='%s'",
                    comprador.razao_social,
                    comprador.cnpj,
                )
                raise InvalidBuyerDataError(
                    "Para clientes B2B, os campos 'razao_social' e 'cnpj' são obrigatórios e não podem estar vazios."
                )

    def finalizar_checkout(self, carrinho_id: str, request: FinalizarCheckoutRequest) -> Pedido:
        """
        Finaliza o checkout de um carrinho elegível:
        1. Obtém o carrinho e verifica se já está finalizado.
        2. Valida dados do comprador para B2B.
        3. Valida a elegibilidade do carrinho (reaproveitando CartService).
        4. Monta o objeto Pedido.
        5. Executa a transação atômica do repositório (decrementar estoque, marcar finalizado, salvar pedido).
        """
        carrinho = self.cart_service.get_cart(carrinho_id)

        if carrinho.finalizado:
            logger.warning("Tentativa de finalizar checkout em carrinho já finalizado: %s", carrinho_id)
            raise CartAlreadyFinalizedError(f"O carrinho '{carrinho_id}' já foi finalizado.")

        self._validar_dados_comprador_b2b(carrinho.tipo_cliente, request.comprador)

        elegibilidade = self.cart_service.check_checkout_eligibility(carrinho_id)
        if not elegibilidade.elegivel:
            logger.warning(
                "Tentativa de checkout rejeitada por ineligibilidade no carrinho %s: %s",
                carrinho_id,
                elegibilidade.motivo,
            )
            raise CartNotEligibleError(elegibilidade.motivo or "Carrinho não elegível para checkout.")

        now = datetime.now(timezone.utc)
        pedido_id = f"ped_{uuid.uuid4().hex[:10]}"

        itens_pedido = [
            ItemPedido(
                produto_id=item.produto_id,
                sku_variacao=item.sku_variacao,
                nome_produto=item.nome_produto,
                quantidade=item.quantidade,
                preco_unitario=item.preco_unitario,
            )
            for item in carrinho.itens
        ]

        pedido = Pedido(
            pedido_id=pedido_id,
            carrinho_id=carrinho.carrinho_id,
            tipo_cliente=carrinho.tipo_cliente,
            comprador=request.comprador,
            endereco_entrega=request.endereco_entrega,
            itens=itens_pedido,
            total=carrinho.total,
            status=StatusPedido.AGUARDANDO_PAGAMENTO,
            criado_em=now,
        )

        sucesso, skus_sem_estoque = self.order_repository.execute_checkout_transaction(
            carrinho=carrinho,
            pedido=pedido,
            cart_repository=self.cart_service.cart_repository,
            product_repository=self.cart_service.product_service.product_repository,
        )

        if not sucesso:
            logger.warning(
                "Checkout rejeitado por estoque insuficiente no commit para o carrinho %s. SKUs afetados: %s",
                carrinho_id,
                skus_sem_estoque,
            )
            raise StockCommitError(skus_sem_estoque)

        logger.info(
            "Checkout finalizado com sucesso! pedido_id=%s, carrinho_id=%s, total=R$%.2f",
            pedido.pedido_id,
            carrinho_id,
            pedido.total,
        )
        return pedido

    def get_order(self, pedido_id: str) -> Pedido:
        """Obtém um pedido pelo seu ID único."""
        pedido = self.order_repository.get_order_by_id(pedido_id)
        if not pedido:
            raise OrderNotFoundError(f"Pedido com ID '{pedido_id}' não foi encontrado.")
        return pedido
