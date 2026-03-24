"""API and UI routes for laptop issue tracking."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.laptop_issue import LaptopIssueCreate, LaptopIssueRead, LaptopIssueUpdate
from app.services.laptop_issue_service import (
    create_issue,
    delete_issue,
    list_issues,
    search_laptops_for_autocomplete,
    update_issue,
)

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


@router.post("/api/laptop-issues", response_model=LaptopIssueRead, status_code=201)
def post_issue(body: LaptopIssueCreate, db: Session = Depends(get_db)):
    if not body.serial_number.strip():
        raise HTTPException(status_code=422, detail="Serienummer is verplicht.")
    if not body.description.strip():
        raise HTTPException(status_code=422, detail="Beschrijving is verplicht.")
    return create_issue(db, body.serial_number, body.description, body.reported_date)


@router.patch("/api/laptop-issues/{issue_id}", response_model=LaptopIssueRead)
def patch_issue(issue_id: int, body: LaptopIssueUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    issue = update_issue(db, issue_id, data)
    if not issue:
        raise HTTPException(status_code=404, detail="Probleem niet gevonden.")
    return issue


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
