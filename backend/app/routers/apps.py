import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import get_settings
from app.database import get_db

router = APIRouter(prefix="/api", tags=["apps"])

ANDROID_EXTENSIONS = {".apk"}
IOS_EXTENSIONS = {".ipa"}


def _detect_platform(filename: str) -> models.Platform:
    suffix = Path(filename).suffix.lower()
    if suffix in ANDROID_EXTENSIONS:
        return models.Platform.android
    if suffix in IOS_EXTENSIONS:
        return models.Platform.ios
    raise HTTPException(400, f"Unsupported file type '{suffix}'. Expected .apk or .ipa.")


@router.post("/projects/{project_id}/apps", response_model=schemas.AppOut, status_code=201)
async def upload_app(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    platform = _detect_platform(file.filename)
    settings = get_settings()

    upload_dir = Path(settings.upload_dir) / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    app_id = uuid.uuid4()
    dest_path = upload_dir / f"{app_id}_{file.filename}"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest_path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit.")
            out.write(chunk)

    app_row = models.App(
        id=app_id,
        project_id=project_id,
        filename=file.filename,
        file_path=str(dest_path),
        platform=platform,
        status=models.AppStatus.uploaded,
    )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return app_row


@router.get("/projects/{project_id}/apps", response_model=list[schemas.AppOut])
def list_apps(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.App)
        .filter(models.App.project_id == project_id)
        .order_by(models.App.uploaded_at.desc())
        .all()
    )


@router.get("/apps/{app_id}", response_model=schemas.AppOut)
def get_app(app_id: uuid.UUID, db: Session = Depends(get_db)):
    app_row = db.get(models.App, app_id)
    if not app_row:
        raise HTTPException(404, "App not found")
    return app_row


@router.post("/apps/{app_id}/scan", status_code=202)
def trigger_scan(app_id: uuid.UUID, db: Session = Depends(get_db)):
    """Kick off the Celery static-analysis pipeline for this app."""
    app_row = db.get(models.App, app_id)
    if not app_row:
        raise HTTPException(404, "App not found")

    from app.celery_app import celery_app

    app_row.status = models.AppStatus.analyzing
    db.commit()

    task = celery_app.send_task("tasks.run_static_analysis", args=[str(app_id)])
    return {"task_id": task.id, "status": "queued"}
