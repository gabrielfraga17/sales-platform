"""Modelos de dados Pydantic para o Módulo de Checkout e Pedido."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.product import TipoCliente


class EnderecoEntrega(BaseModel):
    """Endereço de entrega do comprador."""

    destinatario: str
    logradouro: str
    numero: str
    complemento: Optional[str] = None
    bairro: str
    cidade: str
    estado: str = Field(min_length=2, max_length=2, description="UF, ex: RJ")
    cep: str = Field(description="Somente dígitos ou com hífen, ex: 20000-000")


class DadosComprador(BaseModel):
    """Dados de identificação e contato do comprador."""

    nome: str
    email: EmailStr
    telefone: str
    razao_social: Optional[str] = Field(default=None, description="Obrigatório apenas para tipo_cliente=B2B")
    cnpj: Optional[str] = Field(default=None, description="Obrigatório apenas para tipo_cliente=B2B")


class StatusPedido(str, Enum):
    """Status do pedido no ciclo de vida de compras."""

    AGUARDANDO_PAGAMENTO = "aguardando_pagamento"


class ItemPedido(BaseModel):
    """Item do pedido finalizado."""

    produto_id: str
    sku_variacao: str
    nome_produto: str
    quantidade: int = Field(gt=0)
    preco_unitario: float = Field(gt=0)

    @property
    def subtotal(self) -> float:
        """Calcula o subtotal do item arredondado em 2 casas decimais."""
        return round(self.quantidade * self.preco_unitario, 2)


class Pedido(BaseModel):
    """Entidade de Pedido gerada após o checkout."""

    pedido_id: str
    carrinho_id: str
    tipo_cliente: TipoCliente
    comprador: DadosComprador
    endereco_entrega: EnderecoEntrega
    itens: list[ItemPedido]
    total: float
    status: StatusPedido
    criado_em: datetime


class FinalizarCheckoutRequest(BaseModel):
    """Payload enviado para finalizar o checkout de um carrinho."""

    comprador: DadosComprador
    endereco_entrega: EnderecoEntrega

    @model_validator(mode="after")
    def validar_dados_b2b(self) -> "FinalizarCheckoutRequest":
        """
        Validação de razao_social/cnpj obrigatórios para B2B acontece no
        service (onde o tipo_cliente do carrinho está disponível), não aqui
        — este payload isolado não sabe o tipo_cliente do carrinho.
        """
        return self
