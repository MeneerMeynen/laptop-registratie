"""UI routes – serve full pages and HTMX HTML partials."""
import io
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.laptop_service import (
    get_all_laptops,
    import_laptops_csv,
    list_students,
    parse_column_filters,
    parse_laptop_filters,
)
from app.services.storage_cabinet_service import list_cabinets
from app.services.student_import import import_students_from_stream

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def static_v(path: str) -> str:
    """Return /static/<path>?v=<mtime> for cache-busting on deploys."""
    try:
        mtime = int((STATIC_DIR / path).stat().st_mtime)
    except OSError:
        mtime = 0
    return f"/static/{path}?v={mtime}"


templates.env.globals["static_v"] = static_v
templates.env.globals["app_version"] = pkg_version("laptop-registratie")

router = APIRouter(tags=["ui"])


def _latest_import_at(students) -> dict[bool, object]:
    """Most recent last_import per group, keyed by ``is_leerkracht``.

    Scoped per group so a teacher import doesn't mark every student as
    "Uitgeschreven" (and vice versa).
    """
    latest: dict[bool, object] = {False: None, True: None}
    for s in students:
        group = bool(s.is_leerkracht)
        if s.last_import and (latest[group] is None or s.last_import > latest[group]):
            latest[group] = s.last_import
    return latest


# ── Full page ──────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    students = list_students(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "students": students,
            "latest_import_at": _latest_import_at(students),
        },
    )


@router.get("/barcodes", response_class=HTMLResponse)
def barcodes_print(request: Request):
    return templates.TemplateResponse(request, "barcodes.html", {})


# ── HTMX partials ─────────────────────────────────────────────────────────


@router.get("/ui/students/list", response_class=HTMLResponse)
def students_list_partial(request: Request, db: Session = Depends(get_db)):
    """Laptop-tab student list (HTMX refresh target)."""
    students = list_students(db)
    return templates.TemplateResponse(
        request,
        "partials/student_list.html",
        {
            "students": students,
            "latest_import_at": _latest_import_at(students),
        },
    )


@router.get("/ui/students/manage", response_class=HTMLResponse)
def students_manage_partial(request: Request, db: Session = Depends(get_db)):
    """Manage-tab student list (HTMX refresh target)."""
    students = list_students(db)
    return templates.TemplateResponse(
        request,
        "partials/manage_student_list.html",
        {
            "students": students,
            "latest_import_at": _latest_import_at(students),
        },
    )


@router.get("/photos", response_class=HTMLResponse)
def photos_page(request: Request):
    """Mobile-first photo capture workflow page."""
    return templates.TemplateResponse(request, "photos.html")


@router.get("/ui/photos/gallery", response_class=HTMLResponse)
def photos_gallery_partial(request: Request, serial: str = "", db: Session = Depends(get_db)):
    """HTMX partial: photo gallery for a given serial number."""
    from app.services.photo_service import list_photos

    photos = list_photos(db, serial) if serial else []
    return templates.TemplateResponse(
        request,
        "partials/photo_gallery.html",
        {"photos": photos, "serial_number": serial},
    )


@router.get("/ui/laptops/manage", response_class=HTMLResponse)
def laptops_manage_partial(
    request: Request,
    q: str = "",
    active: str = "all",
    kind: str = "all",
    c_serial: str = "",
    c_student: str = "",
    c_klas: str = "",
    c_status: str = "",
    c_acc: str = "",
    c_date: str = "",
    db: Session = Depends(get_db),
):
    """Instellingen-tab laptop list (HTMX refresh target)."""
    active_filter, kind = parse_laptop_filters(active, kind)
    columns = parse_column_filters(
        serial=c_serial, student=c_student, klas=c_klas,
        status=c_status, acc=c_acc, date=c_date,
    )
    laptops = get_all_laptops(
        db, q=q or None, active=active_filter, kind=kind, columns=columns
    )
    return templates.TemplateResponse(
        request,
        "partials/manage_laptop_list.html",
        {
            "laptops": laptops,
            "q": q,
            "active": active,
            "kind": kind,
        },
    )


@router.get("/ui/storage-cabinets/manage", response_class=HTMLResponse)
def storage_cabinets_manage_partial(
    request: Request,
    q: str = "",
    kind: str = "",
    db: Session = Depends(get_db),
):
    """Instellingen-tab cabinet list (HTMX refresh target)."""
    cabinets = list_cabinets(db, q=q or None, kind=kind or None)
    return templates.TemplateResponse(
        request,
        "partials/manage_cabinet_list.html",
        {"cabinets": cabinets, "q": q},
    )


@router.post("/ui/laptops/import", response_class=HTMLResponse)
async def import_laptops_ui(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        return HTMLResponse(
            '<span class="status error">Alleen CSV-bestanden zijn toegestaan.</span>',
            status_code=400,
        )
    content = (await file.read()).decode("utf-8-sig")
    result = import_laptops_csv(db, io.StringIO(content))
    errors_html = ""
    if result["errors"]:
        errors_html = f' <span style="color:var(--red)">({len(result["errors"])} fout(en))</span>'
    return HTMLResponse(
        f'<span class="status success">✓ {result["created"]} aangemaakt, {result["updated"]} ongewijzigd.{errors_html}</span>'
    )


@router.post("/ui/students/import", response_class=HTMLResponse)
async def import_students_ui(
    request: Request,
    file: UploadFile,
    leerkracht: bool = False,
    db: Session = Depends(get_db),
):
    """Handle CSV import and return a status message partial.

    The frontend (Alpine.js) listens for ``htmx:after-request`` and then
    triggers separate HTMX GETs to refresh both student lists.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        return HTMLResponse(
            '<span class="status error">Alleen CSV-bestanden zijn toegestaan.</span>',
            status_code=400,
        )
    content = (await file.read()).decode("utf-8-sig")
    count = import_students_from_stream(
        db, io.StringIO(content), is_leerkracht=leerkracht
    )
    label = "leerkracht(en)" if leerkracht else "student(en)"
    return HTMLResponse(
        f'<span class="status success">✓ {count} {label} geïmporteerd.</span>'
    )
