from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Field, SoilProfile
from app.schemas import SoilProfileCreate, SoilProfileRead

router = APIRouter(tags=["soil profiles"])


@router.get("/soil-profiles", response_model=list[SoilProfileRead])
def list_soil_profiles(db: Session = Depends(get_db)):
    return db.scalars(select(SoilProfile).order_by(SoilProfile.created_at.desc())).all()


@router.get("/soil-profiles/{soil_profile_id}", response_model=SoilProfileRead)
def get_soil_profile(soil_profile_id: UUID, db: Session = Depends(get_db)):
    profile = db.get(SoilProfile, soil_profile_id)
    if profile is None:
        raise HTTPException(404, "Soil profile not found")
    return profile


@router.get("/fields/{field_id}/soil-profiles", response_model=list[SoilProfileRead])
def list_field_soil_profiles(field_id: UUID, db: Session = Depends(get_db)):
    if db.get(Field, field_id) is None:
        raise HTTPException(404, "Field not found")
    return db.scalars(select(SoilProfile).where(SoilProfile.field_id == field_id).order_by(SoilProfile.created_at.desc())).all()


@router.post("/soil-profiles", response_model=SoilProfileRead, status_code=status.HTTP_201_CREATED)
def create_soil_profile(payload: SoilProfileCreate, db: Session = Depends(get_db)):
    if db.get(Field, payload.field_id) is None:
        raise HTTPException(404, "Field not found")
    profile = SoilProfile(**payload.model_dump())
    try:
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Soil profile conflicts with existing database data") from exc
    return profile
