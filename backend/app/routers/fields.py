from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Farm, Field
from app.schemas import FieldCreate, FieldRead

router = APIRouter(tags=["fields"])


@router.get("/fields", response_model=list[FieldRead])
def list_fields(db: Session = Depends(get_db)):
    return db.scalars(select(Field).order_by(Field.field_name)).all()


@router.get("/fields/{field_id}", response_model=FieldRead)
def get_field(field_id: UUID, db: Session = Depends(get_db)):
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(404, "Field not found")
    return field


@router.get("/farms/{farm_id}/fields", response_model=list[FieldRead])
def list_farm_fields(farm_id: UUID, db: Session = Depends(get_db)):
    if db.get(Farm, farm_id) is None:
        raise HTTPException(404, "Farm not found")
    return db.scalars(select(Field).where(Field.farm_id == farm_id).order_by(Field.field_name)).all()


@router.post("/fields", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)):
    if db.get(Farm, payload.farm_id) is None:
        raise HTTPException(404, "Farm not found")
    field = Field(**payload.model_dump())
    try:
        db.add(field)
        db.commit()
        db.refresh(field)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Field conflicts with existing database data") from exc
    return field
