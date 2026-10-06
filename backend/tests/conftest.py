"""Shared test fixtures.

Tests run against an in-memory SQLite database so the suite is self-contained
and runs in CI without a database server. The application itself runs against
PostgreSQL; the ORM layer is the same in both cases, and no raw SQL is used.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.services.threshold_service import seed_default_thresholds


@pytest.fixture
def db_session():
    """A clean database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    seed_default_thresholds(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """A test client wired to the per-test database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a user and return an Authorization header for them."""
    client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "full_name": "Test Owner",
            "password": "correct-horse-battery",
        },
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "correct-horse-battery"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
