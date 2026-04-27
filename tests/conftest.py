"""
Test configuration.

Tests run against a real MariaDB instance (the 'db' service in compose.yaml).
The DATABASE_URL env var points to the 'laptops_test' database which is created
automatically before the test session and torn down afterwards.

Run via:
    docker compose run --rm test
"""

import os

# Ensure auth-related env vars are set BEFORE app.config / app.main are imported,
# so the Settings object picks them up. The compose 'test' service also sets these.
os.environ.setdefault("AUTH_USERNAME", "test")
os.environ.setdefault("AUTH_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-test-session-secret")
os.environ.setdefault("DEBUG", "true")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

# ── Database URL ──────────────────────────────────────────────────────────────

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://root:changeme@db:3306/laptops_test",
)

# Admin URL: same server, no database selected (used to CREATE the test DB)
_ADMIN_URL = DATABASE_URL.rsplit("/", 1)[0] + "/"
_DB_NAME = DATABASE_URL.rsplit("/", 1)[-1]


# ── Session-scoped: create / drop the test database ──────────────────────────

@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create the laptops_test database and all tables once per test session."""
    admin_engine = create_engine(_ADMIN_URL)
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{_DB_NAME}`"))
    admin_engine.dispose()

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    engine.dispose()

    yield

    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Function-scoped: clean data between tests ─────────────────────────────────

@pytest.fixture()
def db_session():
    """Yield a database session. All data is wiped before each test."""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    # Wipe all rows (disable FK checks so order doesn't matter)
    session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for table in Base.metadata.sorted_tables:
        session.execute(table.delete())
    session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the test database session injected and an active login."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        # Auto-login so individual tests don't need to handle the auth gate.
        resp = c.post(
            "/login",
            data={"username": "test", "password": "test"},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 303), f"login failed: {resp.status_code}"
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(db_session):
    """Unauthenticated TestClient — for tests that exercise the auth gate itself."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
