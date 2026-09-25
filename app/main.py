import logging
from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth_routes
from app.api import health as health_api
from app.api import laptops as laptops_api
from app.api import laptop_issues as laptop_issues_api
from app.api import photos as photos_api
from app.api import storage_cabinets as storage_cabinets_api
from app.api import students as students_api
from app.api import ui as ui_routes
from app.auth import AuthMiddleware
from app.config import settings
from app.logging_config import mask_url, setup_logging

BASE_DIR = Path(__file__).parent

logger = logging.getLogger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic migrations are run via CLI (alembic upgrade head) before startup,
    # either in the Dockerfile CMD or manually by the developer.
    # No auto-migration or CSV auto-import at startup.
    _log_startup_state()
    yield
    logger.info("Applicatie wordt afgesloten.")


def _log_startup_state() -> None:
    """Log what the app sees at boot, so failures are visible in the logs.

    Never raises: a broken database must not stop the app from starting, or
    the logs (and /health) would be unreachable exactly when they are needed.
    """
    from app.api.health import collect_health
    from app.db import get_session_factory

    logger.info("Laptop Registratie v%s start op", pkg_version("laptop-registratie"))
    logger.info("DEBUG=%s | database=%s", settings.debug, mask_url(settings.database_url))

    try:
        with get_session_factory()() as session:
            info = collect_health(session)
    except Exception as exc:
        logger.error("Kon de status niet bepalen: %s: %s", type(exc).__name__, exc)
        return

    database = info["database"]
    if not database["ok"]:
        logger.error("DATABASE NIET BEREIKBAAR: %s", database.get("error"))
        logger.error("%s", info.get("hint", ""))
        return

    logger.info(
        "Database ok | migratie %s (verwacht %s)",
        database.get("revision"),
        database.get("expected_revision"),
    )
    if not database.get("migrations_up_to_date", True):
        logger.error("MIGRATIES NIET UITGEVOERD — %s", info.get("hint", ""))
    counts = info.get("counts", {})
    logger.info(
        "Gegevens: %s leerlingen, %s leerkrachten, %s laptops",
        counts.get("leerlingen"), counts.get("leerkrachten"), counts.get("laptops"),
    )
    if not info["uploads_writable"]:
        logger.error("Uploadmap is niet beschrijfbaar — foto-uploads zullen falen.")


def create_app() -> FastAPI:
    setup_logging()
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
    app.include_router(health_api.router)
    app.include_router(laptops_api.router)
    app.include_router(laptop_issues_api.router)
    app.include_router(photos_api.router)
    app.include_router(storage_cabinets_api.router)
    app.include_router(students_api.router)
    app.include_router(ui_routes.router)

    @app.middleware("http")
    async def log_unhandled_errors(request: Request, call_next):
        """Log the full traceback plus the request that triggered it."""
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Onverwerkte fout bij %s %s", request.method, request.url.path
            )
            raise

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
