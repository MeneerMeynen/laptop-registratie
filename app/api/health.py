"""Health endpoint — one call that shows what the app sees.

Public (no login) so it can be curl'ed from the server and pasted into a
bug report. It never returns passwords: the database URL is masked.
"""
import logging
import os
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.logging_config import mask_url
from app.models.laptop import Laptop
from app.models.student import Student

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

router = APIRouter(tags=["health"])


def db_revision(session: Session) -> str | None:
    """Alembic revision stored in the database, or None if it was never set.

    A missing alembic_version table is not a connection problem: it means the
    migrations never ran here. The caller reports that separately.
    """
    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception as exc:
        logger.warning("Geen alembic_version-tabel gevonden: %s", exc)
        session.rollback()
        return None
    return row[0] if row else None


def expected_revision() -> str | None:
    """Alembic head revision shipped in this image."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(BASE_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BASE_DIR / "alembic"))
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception as exc:  # pragma: no cover - depends on alembic layout
        logger.warning("Kon alembic head niet bepalen: %s", exc)
        return None


def collect_health(session: Session) -> dict:
    """Gather version, database state and row counts. Never raises."""
    info: dict = {
        "status": "ok",
        "version": pkg_version("laptop-registratie"),
        "debug": settings.debug,
        "database": {"ok": False, "url": mask_url(settings.database_url)},
    }

    try:
        session.execute(text("SELECT 1"))
        current = db_revision(session)
        head = expected_revision()
        up_to_date = head is None or current == head
        info["database"].update(
            {
                "ok": True,
                "revision": current,
                "expected_revision": head,
                "migrations_up_to_date": up_to_date,
            }
        )
        info["counts"] = {
            "leerlingen": session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.is_leerkracht.is_(False))
            ),
            "leerkrachten": session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.is_leerkracht.is_(True))
            ),
            "laptops": session.scalar(select(func.count()).select_from(Laptop)),
        }
        if not up_to_date:
            info["status"] = "degraded"
            info["hint"] = (
                f"Database staat op migratie {current or '(geen)'}, deze image "
                f"verwacht {head}. Draai: docker compose exec app alembic upgrade head"
            )
    except Exception as exc:
        info["status"] = "error"
        info["database"]["error"] = f"{type(exc).__name__}: {exc}"
        info["hint"] = (
            "De app bereikt de database niet. Controleer of de db-container "
            "draait en of het wachtwoord in .env klopt."
        )
        logger.exception("Health check: databasetoegang mislukt")

    uploads = BASE_DIR / "uploads" / "laptops"
    info["uploads_writable"] = os.access(uploads, os.W_OK)
    return info


@router.get("/health")
def health(db: Session = Depends(get_db)):
    info = collect_health(db)
    status_code = 200 if info["status"] == "ok" else 503
    return JSONResponse(info, status_code=status_code)
