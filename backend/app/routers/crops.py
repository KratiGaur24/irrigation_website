from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Crop
from app.schemas import CropRead

router = APIRouter(tags=["crops"])


@router.get("/crops", response_model=list[CropRead])
def list_crops(db: Session = Depends(get_db)):
    return db.scalars(select(Crop).where(Crop.active.is_(True)).order_by(Crop.crop_name)).all()
