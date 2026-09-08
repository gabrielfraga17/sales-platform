"""Ponto de entrada principal da aplicação FastAPI Sales Platform API."""

import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers.cart_router import router as cart_router
from app.routers.order_router import router as order_router
from app.routers.product_router import router as product_router

# Configuração de logging estruturado padrão Python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API de Catálogo de Produtos e Vendas (B2C & B2B) para a Sales Platform.",
)

# CORS: necessário para que o frontend (ex.: página de produto Palhas
# Douradas em React, rodando em outro domínio/porta) consiga consumir a
# API diretamente do navegador. Em desenvolvimento (ENVIRONMENT != "production")
# liberamos qualquer origem para facilitar testes locais. Em produção,
# restringimos à lista explícita em ALLOWED_ORIGINS (settings) — atualize
# essa lista assim que o domínio final da loja for definido, para não
# deixar a API aberta a qualquer site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra os roteadores da aplicação
app.include_router(product_router)
app.include_router(cart_router)
app.include_router(order_router)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler global para formatar erros de validação Pydantic em respostas HTTP 400 amigáveis."""
    logger.warning("Erro de validação no request para %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Erro de validação nos dados enviados.",
            "erros": exc.errors(),
        },
    )


@app.get("/health", tags=["Health Check"])
def health_check() -> dict:
    """Endpoint para monitoramento de integridade da API."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
