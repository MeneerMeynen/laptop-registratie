"""Login / logout routes."""
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import LOGIN_PATH, login_user, logout_user, verify_credentials

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Reuse the static_v helper registered globally in app.api.ui
from app.api.ui import static_v  # noqa: E402

templates.env.globals.setdefault("static_v", static_v)

router = APIRouter(tags=["auth"])


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get(LOGIN_PATH, response_class=HTMLResponse)
def login_form(request: Request, next: str = "/", error: int = 0):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": _safe_next(next), "error": bool(error)},
    )


@router.post(LOGIN_PATH)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    target = _safe_next(next)
    if not verify_credentials(username, password):
        response = templates.TemplateResponse(
            request,
            "login.html",
            {"next": target, "error": True},
            status_code=401,
        )
        return response
    login_user(request, username)
    return RedirectResponse(url=target, status_code=303)


@router.post("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url=LOGIN_PATH, status_code=303)
