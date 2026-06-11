"""E2e-specifieke conftest — geen FastAPI/SQLAlchemy imports nodig.

pytest-playwright leest de --base-url CLI-optie automatisch in.
"""
import os
import re

import pytest


@pytest.fixture(autouse=True)
def _e2e_login(page, base_url):
    """Log in via /login zodat elke test een geldige sessiecookie heeft.

    De app zet de sessiecookie met het Secure-attribuut (DEBUG=false). Binnen
    het Docker-netwerk draait e2e over plain http, dus Chromium zou die cookie
    weigeren — we registreren hem daarom handmatig zonder Secure-vlag.
    """
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
    match = re.search(r"session=([^;]+)", response.headers.get("set-cookie", ""))
    assert match, "e2e login: geen sessiecookie in login-response"
    page.context.add_cookies(
        [{"name": "session", "value": match.group(1), "url": base_url}]
    )
    yield
