from uuid import UUID
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Farm, User
from app.schemas import FarmCreate, FarmRead, FarmEdit

router = APIRouter(tags=["farms"])


@router.get("/demo-context")
def demo_context(db: Session = Depends(get_db)):
    """Existing demo entry only; this endpoint does not authenticate a user."""
    user = db.scalar(select(User).where(User.email == os.environ.get("DEMO_USER_EMAIL", "demo@example.test")))
    if user is None:
        raise HTTPException(409, "Demo user is not configured. Run the existing database seed first.")
    return {"mode": "demo", "user_id": str(user.user_id)}


@router.put("/farms/{farm_id}", response_model=FarmRead)
def edit_farm(farm_id: UUID, payload: FarmEdit, db: Session = Depends(get_db)):
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "Farm not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/farms", response_model=list[FarmRead])
def list_farms(db: Session = Depends(get_db)):
    return db.scalars(select(Farm).order_by(Farm.farm_name)).all()


@router.get("/farms/{farm_id}", response_model=FarmRead)
def get_farm(farm_id: UUID, db: Session = Depends(get_db)):
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "Farm not found")
    return farm


@router.post("/farms", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db)):
    if db.get(User, payload.user_id) is None:
        raise HTTPException(404, "User not found")
    farm = Farm(**payload.model_dump())
    try:
        db.add(farm)
        db.commit()
        db.refresh(farm)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Farm conflicts with existing database data") from exc
    return farm
