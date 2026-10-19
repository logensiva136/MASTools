import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import auth, models, schemas
from app.config import get_settings
from app.database import get_db
from app.routers.apps import get_owned_app
from app.services.automated_checks import apply_automated_results

router = APIRouter(prefix="/api", tags=["test-runs"])


def get_owned_test_run(test_run_id: uuid.UUID, db: Session, current_user: models.User) -> models.TestRun:
    test_run = (
        db.query(models.TestRun)
        .join(models.App)
        .join(models.Project)
        .filter(models.TestRun.id == test_run_id, models.Project.owner_id == current_user.id)
        .one_or_none()
    )
    if not test_run:
        raise HTTPException(404, "Test run not found")
    return test_run


def get_owned_result(result_id: uuid.UUID, db: Session, current_user: models.User) -> models.ControlResult:
    result = (
        db.query(models.ControlResult)
        .join(models.TestRun)
        .join(models.App)
        .join(models.Project)
        .filter(models.ControlResult.id == result_id, models.Project.owner_id == current_user.id)
        .one_or_none()
    )
    if not result:
        raise HTTPException(404, "Result not found")
    return result


@router.post("/apps/{app_id}/test-runs", response_model=schemas.TestRunOut, status_code=201)
def create_test_run(
    app_id: uuid.UUID,
    payload: schemas.TestRunCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    app_row = get_owned_app(app_id, db, current_user)

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
    db.flush()

    # If a scan already ran on this app (extracted_metadata is already
    # populated), backfill the automated fields into this brand-new test
    # run right away instead of leaving them pending until the next scan.
    apply_automated_results(db, app_row, test_run)

    db.commit()
    db.refresh(test_run)
    return test_run


@router.get("/apps/{app_id}/test-runs", response_model=list[schemas.TestRunOut])
def list_test_runs(
    app_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_app(app_id, db, current_user)
    return (
        db.query(models.TestRun)
        .filter(models.TestRun.app_id == app_id)
        .order_by(models.TestRun.started_at.desc())
        .all()
    )


@router.get("/test-runs/{test_run_id}", response_model=schemas.TestRunOut)
def get_test_run(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return get_owned_test_run(test_run_id, db, current_user)


@router.get("/test-runs/{test_run_id}/results", response_model=list[schemas.ControlResultOut])
def list_results(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_test_run(test_run_id, db, current_user)
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
def update_result(
    result_id: uuid.UUID,
    payload: schemas.ControlResultUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    result = get_owned_result(result_id, db, current_user)

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
def create_finding(
    test_run_id: uuid.UUID,
    payload: schemas.FindingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_test_run(test_run_id, db, current_user)

    finding = models.Finding(test_run_id=test_run_id, **payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/test-runs/{test_run_id}/findings", response_model=list[schemas.FindingOut])
def list_findings(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    get_owned_test_run(test_run_id, db, current_user)
    return (
        db.query(models.Finding)
        .filter(models.Finding.test_run_id == test_run_id)
        .order_by(models.Finding.created_at.desc())
        .all()
    )


@router.post("/test-runs/{test_run_id}/complete", response_model=schemas.TestRunOut)
def complete_test_run(
    test_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from datetime import datetime

    test_run = get_owned_test_run(test_run_id, db, current_user)

    test_run.status = models.TestRunStatus.completed
    test_run.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(test_run)
    return test_run
