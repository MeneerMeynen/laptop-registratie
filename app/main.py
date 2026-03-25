from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import laptops as laptops_api
from app.api import laptop_issues as laptop_issues_api
from app.api import students as students_api
from app.api import ui as ui_routes

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic migrations are run via CLI (alembic upgrade head) before startup,
    # either in the Dockerfile CMD or manually by the developer.
    # No auto-migration or CSV auto-import at startup.
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Laptop Registratie", version="2.0.0", lifespan=lifespan)

    # Static files (CSS, JS)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    # Routers
    app.include_router(laptops_api.router)
    app.include_router(laptop_issues_api.router)
    app.include_router(students_api.router)
    app.include_router(ui_routes.router)

    return app


app = create_app()
