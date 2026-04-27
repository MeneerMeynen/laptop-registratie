"""Authentication middleware and helpers (single shared login)."""
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp

from app.config import settings

LOGIN_PATH = "/login"
LOGOUT_PATH = "/logout"
SESSION_USER_KEY = "user"

PUBLIC_PREFIXES: tuple[str, ...] = (
    "/login",
    "/logout",
    "/static",
    "/favicon",
)


def _is_public(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in PUBLIC_PREFIXES)


def verify_credentials(username: str, password: str) -> bool:
    if not settings.auth_password:
        return False
    user_ok = secrets.compare_digest(username or "", settings.auth_username)
    pass_ok = secrets.compare_digest(password or "", settings.auth_password)
    return user_ok and pass_ok


def login_user(request: Request, username: str) -> None:
    request.session[SESSION_USER_KEY] = username


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


def current_user(request: Request) -> str | None:
    try:
        return request.session.get(SESSION_USER_KEY)
    except AssertionError:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Gate every request behind a session cookie unless the path is public."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if _is_public(path):
            return await call_next(request)

        if current_user(request):
            return await call_next(request)

        # Unauthenticated. Choose response style based on the request.
        if request.headers.get("HX-Request"):
            response = Response(status_code=204)
            response.headers["HX-Redirect"] = LOGIN_PATH
            return response

        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            next_url = request.url.path
            if request.url.query:
                next_url = f"{next_url}?{request.url.query}"
            return RedirectResponse(
                url=f"{LOGIN_PATH}?next={next_url}",
                status_code=303,
            )

        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
