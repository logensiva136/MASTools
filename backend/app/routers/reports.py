import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import auth, models
from app.database import get_db
from app.routers.test_runs import get_owned_test_run
from app.services import report_generator

router = APIRouter(prefix="/api/test-runs", tags=["reports"])


@router.get("/{test_run_id}/report.md")
def get_report_markdown(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_test_run(test_run_id, db, current_user)
    try:
        content = report_generator.render_markdown(db, test_run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(content=content, media_type="text/markdown")


@router.get("/{test_run_id}/report.html")
def get_report_html(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_test_run(test_run_id, db, current_user)
    try:
        content = report_generator.render_html(db, test_run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(content=content, media_type="text/html")
