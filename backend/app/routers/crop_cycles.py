from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from pydantic import ValidationError

from app.dependencies import get_db
from app.models import Crop, CropCycle, Field
from app.schemas import CropCycleCreate, CropCycleRead, CropCycleEdit

router = APIRouter(tags=["crop cycles"])


def cycle_query():
    return select(CropCycle).options(joinedload(CropCycle.crop))


@router.put("/crop-cycles/{crop_cycle_id}", response_model=CropCycleRead)
def edit_crop_cycle(crop_cycle_id: UUID, payload: CropCycleEdit, db: Session = Depends(get_db)):
    cycle = db.get(CropCycle, crop_cycle_id)
    if cycle is None:
        raise HTTPException(404, "Crop cycle not found")
    # Validate against retained dates as well as submitted ones. Never reset profile/stage data.
    try:
        CropCycleCreate.model_validate({
            **{key: getattr(cycle, key) for key in CropCycleCreate.model_fields},
            **payload.model_dump(),
        })
    except ValidationError as exc:
        raise HTTPException(422, "Harvest dates must be on or after sowing date") from exc
    for key, value in payload.model_dump().items():
        setattr(cycle, key, value)
    db.commit()
    return db.scalar(cycle_query().where(CropCycle.crop_cycle_id == crop_cycle_id))


@router.get("/crop-cycles", response_model=list[CropCycleRead])
def list_crop_cycles(db: Session = Depends(get_db)):
    return db.scalars(cycle_query().order_by(CropCycle.sowing_date.desc())).all()


@router.get("/crop-cycles/{crop_cycle_id}", response_model=CropCycleRead)
def get_crop_cycle(crop_cycle_id: UUID, db: Session = Depends(get_db)):
    cycle = db.scalar(cycle_query().where(CropCycle.crop_cycle_id == crop_cycle_id))
    if cycle is None:
        raise HTTPException(404, "Crop cycle not found")
    return cycle


@router.get("/fields/{field_id}/crop-cycles", response_model=list[CropCycleRead])
def list_field_crop_cycles(field_id: UUID, db: Session = Depends(get_db)):
    if db.get(Field, field_id) is None:
        raise HTTPException(404, "Field not found")
    return db.scalars(cycle_query().where(CropCycle.field_id == field_id).order_by(CropCycle.sowing_date.desc())).all()


@router.post("/crop-cycles", response_model=CropCycleRead, status_code=status.HTTP_201_CREATED)
def create_crop_cycle(payload: CropCycleCreate, db: Session = Depends(get_db)):
    if db.get(Field, payload.field_id) is None:
        raise HTTPException(404, "Field not found")
    if db.get(Crop, payload.crop_id) is None:
        raise HTTPException(404, "Crop not found")
    cycle = CropCycle(**payload.model_dump())
    try:
        db.add(cycle)
        db.commit()
        db.refresh(cycle)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Crop cycle conflicts with existing database data") from exc
    return db.scalar(cycle_query().where(CropCycle.crop_cycle_id == cycle.crop_cycle_id))
