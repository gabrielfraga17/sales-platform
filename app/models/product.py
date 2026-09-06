"""Modelos de dados Pydantic para a entidade Produto e regras associadas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class TipoCliente(str, Enum):
    """Enum com os tipos de clientes aceitos pela plataforma."""

    B2C = "b2c"
    B2B = "b2b"


class PrecoPorTipoCliente(BaseModel):
    """Preço do produto por tipo de cliente (B2C ou B2B)."""

    tipo_cliente: TipoCliente
    preco_unitario: float = Field(gt=0, description="Preço em BRL, sempre positivo")
    margem_minima_revenda_pct: Optional[float] = Field(
        default=None,
        description="Apenas para tipo_cliente=B2B. Deve ser >= 100.0 conforme regra de negócio.",
    )


class VariacaoProduto(BaseModel):
    """Variação do produto (ex: tamanho, cor)."""

    sku_variacao: str = Field(description="SKU único da variação, ex: COLAR-BRANCO-P")
    atributos: Dict[str, str] = Field(description="Ex: {'tamanho': 'P', 'cor': 'branco'}")
    estoque_disponivel: int = Field(ge=0, description="Estoque disponível, não pode ser negativo")


class ProdutoBase(BaseModel):
    """Campos base compartilhados para criação e representação do produto."""

    sku_base: str = Field(description="SKU base do produto, estável — usado por integrações futuras")
    nome: str = Field(description="Nome do produto")
    descricao: str = Field(description="Descrição detalhada do produto")
    pilar_conteudo: Optional[str] = Field(
        default=None,
        description="Vínculo opcional com pilar de conteúdo do Hub (ex: 'Estilo & Modaxé').",
    )
    categoria: str = Field(description="Categoria do produto")
    variacoes: List[VariacaoProduto] = Field(min_length=1, description="Todo produto tem ao menos 1 variação")
    precos: List[PrecoPorTipoCliente] = Field(
        min_length=1,
        description="Todo produto deve ter preço B2C definido. Preço B2B é opcional.",
    )

    @model_validator(mode="after")
    def validar_regras_de_negocio_precos(self) -> "ProdutoBase":
        """
        Valida as regras de negócio de preços:
        1. Todo produto deve ter exatamente um PrecoPorTipoCliente com tipo_cliente=B2C.
        2. Se existir PrecoPorTipoCliente com tipo_cliente=B2B, margem_minima_revenda_pct é obrigatório e >= 100.0.
        """
        precos_b2c = [p for p in self.precos if p.tipo_cliente == TipoCliente.B2C]
        if len(precos_b2c) != 1:
            raise ValueError("Todo Produto deve ter exatamente um preço para tipo_cliente=B2C.")

        for p in self.precos:
            if p.tipo_cliente == TipoCliente.B2B:
                if p.margem_minima_revenda_pct is None:
                    raise ValueError(
                        "Para tipo_cliente=B2B, o campo margem_minima_revenda_pct é obrigatório."
                    )
                if p.margem_minima_revenda_pct < 100.0:
                    raise ValueError(
                        f"Margem mínima de revenda B2B deve ser >= 100.0. Recebido: {p.margem_minima_revenda_pct}%"
                    )

        return self


class ProdutoCreate(ProdutoBase):
    """Payload de criação de produto."""

    pass


class ProdutoUpdate(BaseModel):
    """Payload de atualização de produto."""

    sku_base: Optional[str] = None
    nome: Optional[str] = None
    descricao: Optional[str] = None
    pilar_conteudo: Optional[str] = None
    categoria: Optional[str] = None
    variacoes: Optional[List[VariacaoProduto]] = None
    precos: Optional[List[PrecoPorTipoCliente]] = None
    ativo: Optional[bool] = None

    @model_validator(mode="after")
    def validar_precos_se_presentes(self) -> "ProdutoUpdate":
        """Valida regras de preços caso o campo precos seja atualizado."""
        if self.precos is not None:
            precos_b2c = [p for p in self.precos if p.tipo_cliente == TipoCliente.B2C]
            if len(precos_b2c) != 1:
                raise ValueError("Todo Produto deve ter exatamente um preço para tipo_cliente=B2C.")
            for p in self.precos:
                if p.tipo_cliente == TipoCliente.B2B:
                    if p.margem_minima_revenda_pct is None:
                        raise ValueError(
                            "Para tipo_cliente=B2B, o campo margem_minima_revenda_pct é obrigatório."
                        )
                    if p.margem_minima_revenda_pct < 100.0:
                        raise ValueError(
                            f"Margem mínima de revenda B2B deve ser >= 100.0. Recebido: {p.margem_minima_revenda_pct}%"
                        )
        return self


class Produto(ProdutoBase):
    """Entidade completa de Produto armazenada e retornada pela API."""

    produto_id: str = Field(description="ID único, gerado pelo sistema")
    ativo: bool = Field(default=True, description="Indica se o produto está ativo")
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
