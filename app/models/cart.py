"""Modelos de dados Pydantic para o Módulo de Carrinho."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.product import TipoCliente


class ItemCarrinho(BaseModel):
    """Representa um item dentro do carrinho de compras."""

    produto_id: str
    sku_variacao: str
    nome_produto: str = Field(description="Snapshot do nome no momento da adição, para exibição")
    quantidade: int = Field(gt=0)
    preco_unitario: float = Field(gt=0, description="Snapshot do preço no momento da adição/atualização")

    @property
    def subtotal(self) -> float:
        """Calcula o subtotal do item arredondado em 2 casas decimais."""
        return round(self.quantidade * self.preco_unitario, 2)


class Carrinho(BaseModel):
    """Entidade de Carrinho de compras."""

    carrinho_id: str
    tipo_cliente: TipoCliente
    itens: List[ItemCarrinho] = Field(default_factory=list)
    criado_em: datetime
    atualizado_em: datetime

    @property
    def total(self) -> float:
        """Calcula o valor total do carrinho somando os subtotais dos itens."""
        return round(sum(item.subtotal for item in self.itens), 2)


class ElegibilidadeCheckout(BaseModel):
    """Resultado da validação de elegibilidade para prosseguir ao checkout."""

    elegivel: bool
    total: float
    motivo: Optional[str] = Field(
        default=None,
        description="Preenchido quando elegivel=False, ex: 'Pedido mínimo B2B de R$350,00 não atingido'",
    )
    valor_faltante_moq: Optional[float] = Field(
        default=None,
        description="Apenas quando aplicável a B2B e não atingido — quanto falta para R$350,00",
    )
