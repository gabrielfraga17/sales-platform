"""Camada de repositório para acesso aos dados do Carrinho (Firestore e In-Memory)."""

from abc import ABC, abstractmethod
import logging
from typing import Dict, Optional

from app.config import settings
from app.models.cart import Carrinho

logger = logging.getLogger(__name__)


class BaseCartRepository(ABC):
    """Interface abstrata para persistência de carrinhos."""

    @abstractmethod
    def save(self, carrinho: Carrinho) -> Carrinho:
        """Salva ou atualiza um carrinho."""
        pass

    @abstractmethod
    def get_by_id(self, carrinho_id: str) -> Optional[Carrinho]:
        """Obtém um carrinho pelo seu ID único."""
        pass


class InMemoryCartRepository(BaseCartRepository):
    """Repositório em memória para uso em testes unitários e desenvolvimento offline."""

    def __init__(self) -> None:
        self._storage: Dict[str, Carrinho] = {}

    def save(self, carrinho: Carrinho) -> Carrinho:
        self._storage[carrinho.carrinho_id] = carrinho.model_copy(deep=True)
        logger.info("Carrinho armazenado em memória: id=%s", carrinho.carrinho_id)
        return carrinho

    def get_by_id(self, carrinho_id: str) -> Optional[Carrinho]:
        carrinho = self._storage.get(carrinho_id)
        if carrinho:
            return carrinho.model_copy(deep=True)
        return None


class FirestoreCartRepository(BaseCartRepository):
    """Repositório oficial integrando com o Google Cloud Firestore para a coleção carrinhos."""

    def __init__(self) -> None:
        from google.cloud import firestore  # lazy import

        self.db = firestore.Client(project=settings.GCP_PROJECT_ID)
        self.collection_name = getattr(settings, "FIRESTORE_COLLECTION_CARTS", "carrinhos")
        self.collection = self.db.collection(self.collection_name)

    def save(self, carrinho: Carrinho) -> Carrinho:
        doc_ref = self.collection.document(carrinho.carrinho_id)
        doc_ref.set(carrinho.model_dump(mode="json"))
        logger.info("Carrinho salvo no Firestore: id=%s", carrinho.carrinho_id)
        return carrinho

    def get_by_id(self, carrinho_id: str) -> Optional[Carrinho]:
        doc_ref = self.collection.document(carrinho_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        return Carrinho.model_validate(data)
