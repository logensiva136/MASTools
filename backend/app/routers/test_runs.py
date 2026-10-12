import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.config import get_settings
from app.database import get_db

router = APIRouter(prefix="/api", tags=["test-runs"])


@router.post("/apps/{app_id}/test-runs", response_model=schemas.TestRunOut, status_code=201)
def create_test_run(app_id: uuid.UUID, payload: schemas.TestRunCreate, db: Session = Depends(get_db)):
    app_row = db.get(models.App, app_id)
    if not app_row:
        raise HTTPException(404, "App not found")

    settings = get_settings()
    test_run = models.TestRun(
        app_id=app_id,
        catalog_version=settings.catalog_version,
        tester_name=payload.tester_name,
        status=models.TestRunStatus.running,
    )
    db.add(test_run)
    db.flush()

    controls = (
        db.query(models.MasvsControl)
        .filter(models.MasvsControl.version == settings.catalog_version)
        .all()
    )
    for control in controls:
        if app_row.platform.value not in (control.applies_to or []):
            continue
        db.add(
            models.ControlResult(
                test_run_id=test_run.id,
                control_id=control.id,
                status=models.ResultStatus.pending,
                method=models.ResultMethod.manual,
            )
        )

    db.commit()
    db.refresh(test_run)
    return test_run


@router.get("/apps/{app_id}/test-runs", response_model=list[schemas.TestRunOut])
def list_test_runs(app_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.TestRun)
        .filter(models.TestRun.app_id == app_id)
        .order_by(models.TestRun.started_at.desc())
        .all()
    )


@router.get("/test-runs/{test_run_id}", response_model=schemas.TestRunOut)
def get_test_run(test_run_id: uuid.UUID, db: Session = Depends(get_db)):
    test_run = db.get(models.TestRun, test_run_id)
    if not test_run:
        raise HTTPException(404, "Test run not found")
    return test_run


@router.get("/test-runs/{test_run_id}/results", response_model=list[schemas.ControlResultOut])
def list_results(test_run_id: uuid.UUID, db: Session = Depends(get_db)):
    results = (
        db.query(models.ControlResult)
        .options(joinedload(models.ControlResult.control))
        .filter(models.ControlResult.test_run_id == test_run_id)
        .join(models.MasvsControl)
        .order_by(models.MasvsControl.category, models.MasvsControl.sort_order)
        .all()
    )
    return results


@router.patch("/results/{result_id}", response_model=schemas.ControlResultOut)
def update_result(result_id: uuid.UUID, payload: schemas.ControlResultUpdate, db: Session = Depends(get_db)):
    result = db.get(models.ControlResult, result_id)
    if not result:
        raise HTTPException(404, "Result not found")

    if payload.status is not None:
        result.status = payload.status
        # A manual edit from the UI always marks the result as manually reviewed,
        # even if a static check had previously set it automatically.
        result.method = models.ResultMethod.manual
    if payload.evidence is not None:
        result.evidence = payload.evidence
    if payload.notes is not None:
        result.notes = payload.notes

    db.commit()
    db.refresh(result)
    return result


@router.post("/test-runs/{test_run_id}/findings", response_model=schemas.FindingOut, status_code=201)
def create_finding(test_run_id: uuid.UUID, payload: schemas.FindingCreate, db: Session = Depends(get_db)):
    test_run = db.get(models.TestRun, test_run_id)
    if not test_run:
        raise HTTPException(404, "Test run not found")

    finding = models.Finding(test_run_id=test_run_id, **payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/test-runs/{test_run_id}/findings", response_model=list[schemas.FindingOut])
def list_findings(test_run_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Finding)
        .filter(models.Finding.test_run_id == test_run_id)
        .order_by(models.Finding.created_at.desc())
        .all()
    )


@router.post("/test-runs/{test_run_id}/complete", response_model=schemas.TestRunOut)
def complete_test_run(test_run_id: uuid.UUID, db: Session = Depends(get_db)):
    from datetime import datetime

    test_run = db.get(models.TestRun, test_run_id)
    if not test_run:
        raise HTTPException(404, "Test run not found")

    test_run.status = models.TestRunStatus.completed
    test_run.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(test_run)
    return test_run
