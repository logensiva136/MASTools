from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.config import get_settings
from app.database import get_db

router = APIRouter(prefix="/api/controls", tags=["controls"])


@router.get("", response_model=list[schemas.ControlOut])
def list_controls(
    version: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    version = version or get_settings().catalog_version
    return (
        db.query(models.MasvsControl)
        .filter(models.MasvsControl.version == version)
        .order_by(models.MasvsControl.category, models.MasvsControl.sort_order)
        .all()
    )
