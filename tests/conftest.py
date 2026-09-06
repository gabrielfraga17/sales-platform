"""Fixtures de testes automatizados com Pytest."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.firestore_repository import InMemoryProductRepository
from app.routers.product_router import get_repository


@pytest.fixture
def repo_in_memory() -> InMemoryProductRepository:
    """Fixture que fornece um repositório isolado em memória a cada teste."""
    return InMemoryProductRepository()


@pytest.fixture
def client(repo_in_memory: InMemoryProductRepository) -> TestClient:
    """Fixture do TestClient do FastAPI com o repositório em memória injetado."""
    app.dependency_overrides[get_repository] = lambda: repo_in_memory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
