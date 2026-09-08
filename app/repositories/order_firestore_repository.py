"""Camada de repositório para acesso aos dados de Pedidos e transação atômica de checkout."""

from abc import ABC, abstractmethod
import logging
from typing import Dict, Optional, Tuple, List

from app.config import settings
from app.models.cart import Carrinho
from app.models.order import Pedido
from app.models.product import Produto

logger = logging.getLogger(__name__)


class BaseOrderRepository(ABC):
    """Interface abstrata para persistência de pedidos e checkout atômico."""

    @abstractmethod
    def save_order(self, order: Pedido) -> Pedido:
        """Salva um pedido."""
        pass

    @abstractmethod
    def get_order_by_id(self, order_id: str) -> Optional[Pedido]:
        """Busca um pedido pelo ID."""
        pass

    @abstractmethod
    def execute_checkout_transaction(
        self,
        carrinho: Carrinho,
        pedido: Pedido,
        cart_repository: any,
        product_repository: any,
    ) -> Tuple[bool, List[str]]:
        """
        Executa a transação atômica do checkout:
        1. Reler o produto e o estoque disponível de cada variação do carrinho.
        2. Se estoque insuficiente em qualquer variação, falhar transação sem alterar nada.
        3. Decrementar estoque das variações.
        4. Marcar carrinho como finalizado=True.
        5. Salvar pedido.

        Retorna (sucesso: bool, skus_sem_estoque: List[str]).
        """
        pass


class InMemoryOrderRepository(BaseOrderRepository):
    """Repositório em memória para uso em testes unitários e desenvolvimento offline."""

    def __init__(self) -> None:
        self._storage: Dict[str, Pedido] = {}

    def save_order(self, order: Pedido) -> Pedido:
        self._storage[order.pedido_id] = order.model_copy(deep=True)
        logger.info("Pedido armazenado em memória: id=%s", order.pedido_id)
        return order

    def get_order_by_id(self, order_id: str) -> Optional[Pedido]:
        pedido = self._storage.get(order_id)
        if pedido:
            return pedido.model_copy(deep=True)
        return None

    def execute_checkout_transaction(
        self,
        carrinho: Carrinho,
        pedido: Pedido,
        cart_repository: any,
        product_repository: any,
    ) -> Tuple[bool, List[str]]:
        """
        Execução simulada em memória com verificação atômica de estoque.
        """
        skus_sem_estoque: List[str] = []
        produtos_para_atualizar: List[Tuple[Produto, str, int]] = []

        # 1. Reler estoque de cada item
        for item in carrinho.itens:
            produto = product_repository.get_by_id(item.produto_id)
            if not produto:
                skus_sem_estoque.append(item.sku_variacao)
                continue

            variacao_encontrada = None
            for var in produto.variacoes:
                if var.sku_variacao == item.sku_variacao:
                    variacao_encontrada = var
                    break

            if not variacao_encontrada or variacao_encontrada.estoque_disponivel < item.quantidade:
                skus_sem_estoque.append(item.sku_variacao)
            else:
                produtos_para_atualizar.append((produto, item.sku_variacao, item.quantidade))

        if skus_sem_estoque:
            logger.warning("Checkout rejeitado por estoque insuficiente em memória para SKUs: %s", skus_sem_estoque)
            return False, skus_sem_estoque

        # 2. Decrementar estoque
        for produto, sku_var, qtd in produtos_para_atualizar:
            for var in produto.variacoes:
                if var.sku_variacao == sku_var:
                    var.estoque_disponivel -= qtd
            product_repository.save(produto)

        # 3. Marcar carrinho como finalizado
        carrinho.finalizado = True
        cart_repository.save(carrinho)

        # 4. Salvar pedido
        self.save_order(pedido)
        logger.info("Checkout em memória executado com sucesso: pedido_id=%s", pedido.pedido_id)
        return True, []


class FirestoreOrderRepository(BaseOrderRepository):
    """Repositório oficial integrando com o Google Cloud Firestore com transações atômicas."""

    def __init__(self) -> None:
        from google.cloud import firestore  # lazy import

        self.db = firestore.Client(project=settings.GCP_PROJECT_ID)
        self.collection_name = getattr(settings, "FIRESTORE_COLLECTION_ORDERS", "pedidos")
        self.collection = self.db.collection(self.collection_name)

    def save_order(self, order: Pedido) -> Pedido:
        doc_ref = self.collection.document(order.pedido_id)
        doc_ref.set(order.model_dump(mode="json"))
        logger.info("Pedido salvo no Firestore: id=%s", order.pedido_id)
        return order

    def get_order_by_id(self, order_id: str) -> Optional[Pedido]:
        doc_ref = self.collection.document(order_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Pedido.model_validate(data)

    def execute_checkout_transaction(
        self,
        carrinho: Carrinho,
        pedido: Pedido,
        cart_repository: any,
        product_repository: any,
    ) -> Tuple[bool, List[str]]:
        from google.cloud import firestore

        transaction = self.db.transaction()
        products_coll = self.db.collection(getattr(settings, "FIRESTORE_COLLECTION_PRODUCTS", "products"))
        carts_coll = self.db.collection(getattr(settings, "FIRESTORE_COLLECTION_CARTS", "carrinhos"))
        orders_coll = self.collection

        @firestore.transactional
        def _transactional_checkout(trans: firestore.Transaction) -> Tuple[bool, List[str]]:
            skus_sem_estoque: List[str] = []
            updates: List[Tuple[firestore.DocumentReference, dict]] = []

            # 1. Agrupar quantidades por produto_id
            itens_por_produto: Dict[str, List[Tuple[str, int]]] = {}
            for item in carrinho.itens:
                itens_por_produto.setdefault(item.produto_id, []).append((item.sku_variacao, item.quantidade))

            # 2. Reler cada produto dentro da transação
            for produto_id, itens_var in itens_por_produto.items():
                prod_ref = products_coll.document(produto_id)
                prod_snapshot = prod_ref.get(transaction=trans)
                if not prod_snapshot.exists:
                    for sku, _ in itens_var:
                        skus_sem_estoque.append(sku)
                    continue

                prod_data = prod_snapshot.to_dict()
                variacoes = prod_data.get("variacoes", [])

                for sku_var, qtd in itens_var:
                    var_encontrada = None
                    for var in variacoes:
                        if var.get("sku_variacao") == sku_var:
                            var_encontrada = var
                            break

                    if not var_encontrada or var_encontrada.get("estoque_disponivel", 0) < qtd:
                        skus_sem_estoque.append(sku_var)
                    elif not skus_sem_estoque:
                        var_encontrada["estoque_disponivel"] -= qtd

                if not skus_sem_estoque:
                    updates.append((prod_ref, prod_data))

            if skus_sem_estoque:
                return False, skus_sem_estoque

            # 3. Aplicar atualizações de estoque
            for prod_ref, prod_data in updates:
                trans.update(prod_ref, {"variacoes": prod_data["variacoes"]})

            # 4. Marcar carrinho como finalizado
            cart_ref = carts_coll.document(carrinho.carrinho_id)
            carrinho.finalizado = True
            trans.update(cart_ref, {"finalizado": True})

            # 5. Salvar pedido
            order_ref = orders_coll.document(pedido.pedido_id)
            trans.set(order_ref, pedido.model_dump(mode="json"))

            return True, []

        return _transactional_checkout(transaction)
