from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth_routes
from app.api import laptops as laptops_api
from app.api import laptop_issues as laptop_issues_api
from app.api import photos as photos_api
from app.api import storage_cabinets as storage_cabinets_api
from app.api import students as students_api
from app.api import ui as ui_routes
from app.auth import AuthMiddleware
from app.config import settings

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic migrations are run via CLI (alembic upgrade head) before startup,
    # either in the Dockerfile CMD or manually by the developer.
    # No auto-migration or CSV auto-import at startup.
    yield


def create_app() -> FastAPI:
    if not settings.session_secret:
        raise RuntimeError(
            "SESSION_SECRET must be set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not settings.debug and not settings.auth_password:
        raise RuntimeError(
            "AUTH_PASSWORD must be set in production "
            "(set DEBUG=true to bypass for local development)."
        )

    app = FastAPI(title="Laptop Registratie", version=pkg_version("laptop-registratie"), lifespan=lifespan)

    # Static files (CSS, JS)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    # Uploads directory (laptop photos)
    uploads_dir = BASE_DIR.parent / "uploads" / "laptops"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads/laptops", StaticFiles(directory=uploads_dir), name="uploads")

    # Routers
    app.include_router(auth_routes.router)
    app.include_router(laptops_api.router)
    app.include_router(laptop_issues_api.router)
    app.include_router(photos_api.router)
    app.include_router(storage_cabinets_api.router)
    app.include_router(students_api.router)
    app.include_router(ui_routes.router)

    # Middleware: added bottom-up, so SessionMiddleware (added last) runs first
    # and populates request.session before AuthMiddleware reads it.
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=not settings.debug,
        max_age=60 * 60 * 8,
    )

    return app


app = create_app()
