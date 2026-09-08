"""Serviço de gerenciamento do carrinho de compras e regras de negócio."""

from datetime import datetime, timezone
import logging
import uuid

from app.models.cart import Carrinho, ElegibilidadeCheckout, ItemCarrinho
from app.models.product import TipoCliente
from app.repositories.cart_firestore_repository import BaseCartRepository
from app.services.product_service import ProductNotFoundError, ProductService

logger = logging.getLogger(__name__)


class CartNotFoundError(Exception):
    """Exceção para quando um carrinho não for encontrado."""

    pass


class CartAlreadyFinalizedError(Exception):
    """Exceção para quando o carrinho já tiver sido finalizado."""

    pass


class CartItemNotFoundError(Exception):
    """Exceção para quando um item/variação não for encontrado no carrinho."""

    pass


class InsufficientStockError(Exception):
    """Exceção para quando a quantidade solicitada excede o estoque disponível."""

    pass


class CartService:
    """Serviço que gerencia operações do carrinho de compras."""

    def __init__(self, cart_repository: BaseCartRepository, product_service: ProductService) -> None:
        self.cart_repository = cart_repository
        self.product_service = product_service

    def create_cart(self, tipo_cliente: TipoCliente) -> Carrinho:
        """Cria um novo carrinho vazio associado ao tipo de cliente informado."""
        now = datetime.now(timezone.utc)
        carrinho_id = f"cart_{uuid.uuid4().hex[:10]}"

        carrinho = Carrinho(
            carrinho_id=carrinho_id,
            tipo_cliente=tipo_cliente,
            itens=[],
            criado_em=now,
            atualizado_em=now,
        )

        salvo = self.cart_repository.save(carrinho)
        logger.info("Carrinho criado com sucesso: id=%s, tipo_cliente=%s", salvo.carrinho_id, salvo.tipo_cliente.value)
        return salvo

    def get_cart(self, carrinho_id: str) -> Carrinho:
        """Busca um carrinho pelo ID."""
        carrinho = self.cart_repository.get_by_id(carrinho_id)
        if not carrinho:
            raise CartNotFoundError(f"Carrinho com ID '{carrinho_id}' não foi encontrado.")
        return carrinho

    def add_item(self, carrinho_id: str, produto_id: str, sku_variacao: str, quantidade: int) -> Carrinho:
        """Adiciona um item ao carrinho ou incrementa sua quantidade se já existir."""
        carrinho = self.get_cart(carrinho_id)
        if carrinho.finalizado:
            raise CartAlreadyFinalizedError(f"Não é possível alterar o carrinho '{carrinho_id}' pois ele já foi finalizado.")

        # Valida existência do produto e variação, e obtém preço e estoque
        produto = self.product_service.get_product(produto_id)
        preco_unitario = self.product_service.obter_preco_produto(produto_id, carrinho.tipo_cliente)
        estoque_disponivel = self.product_service.obter_estoque_variacao(produto_id, sku_variacao)

        # Procura se o item já existe no carrinho por sku_variacao
        item_existente = next((item for item in carrinho.itens if item.sku_variacao == sku_variacao), None)

        qtd_existente = item_existente.quantidade if item_existente else 0
        qtd_total_solicitada = qtd_existente + quantidade

        if qtd_total_solicitada > estoque_disponivel:
            logger.warning(
                "Estoque insuficiente para adicionar item. Produto=%s, SKU=%s, Solicitado=%d, Disponível=%d",
                produto_id,
                sku_variacao,
                qtd_total_solicitada,
                estoque_disponivel,
            )
            raise InsufficientStockError(
                f"Estoque insuficiente para a variação '{sku_variacao}'. Solicitado: {qtd_total_solicitada}, Disponível: {estoque_disponivel}."
            )

        if item_existente:
            item_existente.quantidade = qtd_total_solicitada
            item_existente.preco_unitario = preco_unitario
            item_existente.nome_produto = produto.nome
        else:
            novo_item = ItemCarrinho(
                produto_id=produto_id,
                sku_variacao=sku_variacao,
                nome_produto=produto.nome,
                quantidade=quantidade,
                preco_unitario=preco_unitario,
            )
            carrinho.itens.append(novo_item)

        carrinho.atualizado_em = datetime.now(timezone.utc)
        salvo = self.cart_repository.save(carrinho)
        logger.info(
            "Item adicionado/atualizado no carrinho %s: produto=%s, sku=%s, qtd=%d",
            carrinho_id,
            produto_id,
            sku_variacao,
            quantidade,
        )
        return salvo

    def update_item_quantity(self, carrinho_id: str, sku_variacao: str, quantidade: int) -> Carrinho:
        """
        Atualiza a quantidade de um item no carrinho.
        Se quantidade == 0, remove o item.
        """
        carrinho = self.get_cart(carrinho_id)
        if carrinho.finalizado:
            raise CartAlreadyFinalizedError(f"Não é possível alterar o carrinho '{carrinho_id}' pois ele já foi finalizado.")

        item_existente = next((item for item in carrinho.itens if item.sku_variacao == sku_variacao), None)
        if not item_existente:
            raise CartItemNotFoundError(
                f"Item com SKU de variação '{sku_variacao}' não foi encontrado no carrinho '{carrinho_id}'."
            )

        if quantidade == 0:
            carrinho.itens = [item for item in carrinho.itens if item.sku_variacao != sku_variacao]
        else:
            estoque_disponivel = self.product_service.obter_estoque_variacao(item_existente.produto_id, sku_variacao)
            if quantidade > estoque_disponivel:
                logger.warning(
                    "Estoque insuficiente para atualizar quantidade. SKU=%s, Solicitado=%d, Disponível=%d",
                    sku_variacao,
                    quantidade,
                    estoque_disponivel,
                )
                raise InsufficientStockError(
                    f"Estoque insuficiente para a variação '{sku_variacao}'. Solicitado: {quantidade}, Disponível: {estoque_disponivel}."
                )

            preco_unitario = self.product_service.obter_preco_produto(item_existente.produto_id, carrinho.tipo_cliente)
            item_existente.quantidade = quantidade
            item_existente.preco_unitario = preco_unitario

        carrinho.atualizado_em = datetime.now(timezone.utc)
        salvo = self.cart_repository.save(carrinho)
        logger.info("Quantidade do item %s atualizada para %d no carrinho %s", sku_variacao, quantidade, carrinho_id)
        return salvo

    def remove_item(self, carrinho_id: str, sku_variacao: str) -> Carrinho:
        """Remove um item do carrinho."""
        carrinho = self.get_cart(carrinho_id)
        if carrinho.finalizado:
            raise CartAlreadyFinalizedError(f"Não é possível alterar o carrinho '{carrinho_id}' pois ele já foi finalizado.")

        item_existente = next((item for item in carrinho.itens if item.sku_variacao == sku_variacao), None)
        if not item_existente:
            raise CartItemNotFoundError(
                f"Item com SKU de variação '{sku_variacao}' não foi encontrado no carrinho '{carrinho_id}'."
            )

        carrinho.itens = [item for item in carrinho.itens if item.sku_variacao != sku_variacao]
        carrinho.atualizado_em = datetime.now(timezone.utc)
        salvo = self.cart_repository.save(carrinho)
        logger.info("Item %s removido do carrinho %s", sku_variacao, carrinho_id)
        return salvo

    def check_checkout_eligibility(self, carrinho_id: str) -> ElegibilidadeCheckout:
        """Valida a elegibilidade do carrinho para prosseguir ao checkout, incluindo regras de MOQ B2B."""
        carrinho = self.get_cart(carrinho_id)
        total = carrinho.total

        if not carrinho.itens:
            return ElegibilidadeCheckout(
                elegivel=False,
                total=total,
                motivo="O carrinho está vazio.",
                valor_faltante_moq=None,
            )

        if carrinho.tipo_cliente == TipoCliente.B2B:
            moq_minimo = 350.00
            if total < moq_minimo:
                faltante = round(moq_minimo - total, 2)
                logger.warning(
                    "Elegibilidade de checkout negada para B2B no carrinho %s: total R$ %.2f abaixo do MOQ de R$ %.2f",
                    carrinho_id,
                    total,
                    moq_minimo,
                )
                return ElegibilidadeCheckout(
                    elegivel=False,
                    total=total,
                    motivo=f"Pedido mínimo B2B de R$350,00 não atingido. Faltam R$ {faltante:.2f}.",
                    valor_faltante_moq=faltante,
                )

        return ElegibilidadeCheckout(
            elegivel=True,
            total=total,
            motivo=None,
            valor_faltante_moq=None,
        )
