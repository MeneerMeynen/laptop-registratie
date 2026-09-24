"""E2e-tests (Playwright) tegen een draaiende Laravel-app.

Starten:
    php artisan serve --port=8000   # met AUTH_USERNAME=admin en AUTH_PASSWORD=test
    pip install pytest pytest-playwright && playwright install chromium
    pytest tests/e2e --base-url http://localhost:8000

Inloggegevens via E2E_USERNAME / E2E_PASSWORD (standaard admin / test);
een eigen Chromium-binary kan via E2E_CHROMIUM.
"""
import os

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    extra = {"executable_path": os.environ["E2E_CHROMIUM"]} if os.environ.get("E2E_CHROMIUM") else {}
    return {**browser_type_launch_args, **extra}


@pytest.fixture(autouse=True)
def _e2e_login(page, base_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base_url}/login")
    page.fill("input[name=username]", os.environ.get("E2E_USERNAME", "admin"))
    page.fill("input[name=password]", os.environ.get("E2E_PASSWORD", "test"))
    page.click("button[type=submit]")
    page.wait_for_url(f"{base_url}/")
    page.js_errors = errors
    yield
    assert not errors, f"JavaScript-fouten: {errors}"
