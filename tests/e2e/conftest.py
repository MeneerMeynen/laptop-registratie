"""E2e-specifieke conftest — geen FastAPI/SQLAlchemy imports nodig.

pytest-playwright leest de --base-url CLI-optie automatisch in.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _e2e_login(page, base_url):
    """Log in via /login zodat elke test een geldige sessiecookie heeft."""
    username = os.environ.get("E2E_USERNAME", "admin")
    password = os.environ.get("E2E_PASSWORD", "changeme")
    response = page.context.request.post(
        f"{base_url}/login",
        form={"username": username, "password": password, "next": "/"},
        max_redirects=0,
    )
    # 303 redirect on success (TestClient/HTTPX style); 200 if browser auto-followed.
    assert response.status in (200, 303), (
        f"e2e login failed: {response.status} {response.text()}"
    )
    yield
