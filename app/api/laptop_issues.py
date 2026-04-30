"""API and UI routes for laptop issue tracking."""
import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.laptop_issue import LaptopIssueCreate, LaptopIssueRead, LaptopIssueUpdate
from app.services.laptop_issue_service import (
    VALID_CATEGORIES,
    IssueValidationError,
    add_issue_entry,
    create_issue,
    delete_entry,
    delete_issue,
    get_entries_for_issue,
    get_global_stats,
    get_issues_for_serial,
    get_student_for_serial,
    list_issues,
    list_laptops_with_issues,
    search_laptops_for_autocomplete,
    update_entry,
    update_issue,
)
from app.services.laptop_service import get_assignment_history

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(tags=["laptop-issues"])


@router.get("/api/laptop-issues", response_model=list[LaptopIssueRead])
def get_issues(
    search: str = "",
    include_closed: bool = False,
    db: Session = Depends(get_db),
):
    return list_issues(db, search=search, include_closed=include_closed)


@router.get("/api/laptop-issues/export")
def export_issues(
    include_closed: bool = True,
    db: Session = Depends(get_db),
):
    """Download all issues as a CSV file."""
    issues = list_issues(db, include_closed=include_closed)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "Serienummer", "Leerling", "Categorie",
        "Beschrijving", "Status", "Datum gemeld", "Oplossing",
    ])
    for issue in issues:
        leerling = f"{issue.get('voornaam') or ''} {issue.get('naam') or ''}".strip()
        writer.writerow([
            issue["id"],
            issue["serial_number"],
            leerling,
            issue.get("category") or "",
            issue["description"],
            issue["status"],
            issue["reported_date"],
            issue.get("solution") or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=laptop-defecten.csv"},
    )


@router.post("/api/laptop-issues", response_model=LaptopIssueRead, status_code=201)
def post_issue(body: LaptopIssueCreate, db: Session = Depends(get_db)):
    if not body.serial_number.strip():
        raise HTTPException(status_code=422, detail="Serienummer is verplicht.")
    if not body.description.strip():
        raise HTTPException(status_code=422, detail="Beschrijving is verplicht.")
    try:
        issue = create_issue(
            db,
            body.serial_number,
            body.description,
            body.reported_date,
            category=body.category,
            reserve_laptop_id=body.reserve_laptop_id,
        )
    except IssueValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Re-fetch via list_issues so reserve laptop info is included in response.
    rows = [r for r in list_issues(db, include_closed=True) if r["id"] == issue.id]
    return rows[0] if rows else issue


@router.patch("/api/laptop-issues/{issue_id}", response_model=LaptopIssueRead)
def patch_issue(issue_id: int, body: LaptopIssueUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    try:
        issue = update_issue(db, issue_id, data)
    except IssueValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not issue:
        raise HTTPException(status_code=404, detail="Probleem niet gevonden.")
    rows = [r for r in list_issues(db, include_closed=True) if r["id"] == issue.id]
    return rows[0] if rows else issue


@router.delete("/api/laptop-issues/{issue_id}", status_code=204)
def remove_issue(issue_id: int, db: Session = Depends(get_db)):
    if not delete_issue(db, issue_id):
        raise HTTPException(status_code=404, detail="Probleem niet gevonden.")


@router.get("/api/laptops/search")
def laptop_search(q: str = "", db: Session = Depends(get_db)):
    if len(q) < 2:
        return []
    return search_laptops_for_autocomplete(db, q)


@router.get("/ui/laptop-issues", response_class=HTMLResponse)
def laptop_issues_partial(
    request: Request,
    search: str = "",
    include_closed: bool = False,
    db: Session = Depends(get_db),
):
    issues = list_issues(db, search=search, include_closed=include_closed)
    return templates.TemplateResponse(
        request,
        "partials/laptop_issues_list.html",
        {"issues": issues},
    )


@router.get("/ui/laptop-tracker/sidebar", response_class=HTMLResponse)
def laptop_tracker_sidebar(
    request: Request,
    search: str = "",
    statuses: list[str] = Query(default=["aangemeld", "open"]),
    db: Session = Depends(get_db),
):
    laptops = list_laptops_with_issues(db, search=search, statuses=statuses)
    stats = get_global_stats(db)
    return templates.TemplateResponse(
        request,
        "partials/laptop_tracker_sidebar.html",
        {"laptops": laptops, "stats": stats},
    )


@router.get("/ui/laptop-tracker/detail", response_class=HTMLResponse)
def laptop_tracker_detail(
    request: Request,
    serial: str,
    db: Session = Depends(get_db),
):
    issues = get_issues_for_serial(db, serial)
    student = get_student_for_serial(db, serial)
    history = get_assignment_history(db, serial)
    open_count = sum(1 for i in issues if i["status"] == "open")
    gesloten_count = sum(1 for i in issues if i["status"] == "gesloten")
    aangemeld_count = sum(1 for i in issues if i["status"] == "aangemeld")

    from app.services.photo_service import list_photos
    photo_count = len(list_photos(db, serial))

    return templates.TemplateResponse(
        request,
        "partials/laptop_tracker_detail.html",
        {
            "serial": serial,
            "student": student,
            "issues": issues,
            "history": history,
            "open_count": open_count,
            "gesloten_count": gesloten_count,
            "aangemeld_count": aangemeld_count,
            "categories": VALID_CATEGORIES,
            "photo_count": photo_count,
        },
    )


@router.post("/ui/laptop-issues/{issue_id}/entries", response_class=HTMLResponse)
def post_issue_entry(
    request: Request,
    issue_id: int,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    if not text.strip():
        return HTMLResponse('<p class="lt-entry-error">Opvolgingstekst mag niet leeg zijn.</p>')
    add_issue_entry(db, issue_id, text)
    entries = get_entries_for_issue(db, issue_id)
    return templates.TemplateResponse(
        request,
        "partials/laptop_issue_entries.html",
        {"entries": entries},
    )


@router.patch("/ui/laptop-issues/entries/{entry_id}", response_class=HTMLResponse)
def patch_issue_entry(
    request: Request,
    entry_id: int,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    if not text.strip():
        return HTMLResponse('<p class="lt-entry-error">Tekst mag niet leeg zijn.</p>')
    entry = update_entry(db, entry_id, text)
    if not entry:
        return HTMLResponse('<p class="lt-entry-error">Opvolging niet gevonden.</p>')
    entries = get_entries_for_issue(db, entry.issue_id)
    return templates.TemplateResponse(
        request,
        "partials/laptop_issue_entries.html",
        {"entries": entries},
    )


@router.delete("/ui/laptop-issues/entries/{entry_id}", response_class=HTMLResponse)
def delete_issue_entry(
    request: Request,
    entry_id: int,
    db: Session = Depends(get_db),
):
    issue_id = delete_entry(db, entry_id)
    if issue_id is None:
        return HTMLResponse('<p class="lt-entry-error">Opvolging niet gevonden.</p>')
    entries = get_entries_for_issue(db, issue_id)
    return templates.TemplateResponse(
        request,
        "partials/laptop_issue_entries.html",
        {"entries": entries},
    )
