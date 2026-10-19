import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.Project)
        .filter(models.Project.owner_id == current_user.id)
        .order_by(models.Project.created_at.desc())
        .all()
    )


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    payload: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    project = models.Project(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_owned_project(project_id: uuid.UUID, db: Session, current_user: models.User) -> models.Project:
    """Shared ownership check other routers import — a project that exists
    but belongs to someone else looks exactly like one that doesn't exist,
    so a caller can't probe for other users' project IDs."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.owner_id == current_user.id)
        .one_or_none()
    )
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return get_owned_project(project_id, db, current_user)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    project = get_owned_project(project_id, db, current_user)
    db.delete(project)
    db.commit()
