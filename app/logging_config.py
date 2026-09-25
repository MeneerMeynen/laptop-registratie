"""Logging setup and helpers for safe (password-free) diagnostics."""
import logging
import re
import sys

from app.config import settings

_PASSWORD_IN_URL = re.compile(r"(://[^:/@]+:)[^@]*(@)")

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def mask_url(url: str) -> str:
    """Replace the password in a database URL with ***, for safe logging."""
    return _PASSWORD_IN_URL.sub(r"\1***\2", url or "")


def setup_logging() -> None:
    """Configure root logging once, at the level from LOG_LEVEL (default INFO)."""
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
    # Uvicorn installs its own handlers; align their level with ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)
    # Alembic logs a plugin-setup line per extension on every revision lookup;
    # that noise would bury the startup diagnostics.
    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)
