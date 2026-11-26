from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Device, Field
from app.schemas import DeviceCreate, DeviceRead

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)):
    return db.scalars(select(Device).order_by(Device.device_code)).all()


@router.get("/devices/code/{device_code}", response_model=DeviceRead)
def get_device_by_code(device_code: str, db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_code == device_code))
    if device is None:
        raise HTTPException(404, "Device not found")
    return device


@router.get("/devices/{device_id}", response_model=DeviceRead)
def get_device(device_id: UUID, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    return device


@router.get("/fields/{field_id}/devices", response_model=list[DeviceRead])
def list_field_devices(field_id: UUID, db: Session = Depends(get_db)):
    if db.get(Field, field_id) is None:
        raise HTTPException(404, "Field not found")
    return db.scalars(select(Device).where(Device.field_id == field_id).order_by(Device.device_code)).all()


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    if db.get(Field, payload.field_id) is None:
        raise HTTPException(404, "Field not found")
    device = Device(**payload.model_dump())
    try:
        db.add(device)
        db.commit()
        db.refresh(device)
    except IntegrityError as exc:
        db.rollback()
        if db.scalar(select(Device.device_id).where(Device.device_code == payload.device_code)) is not None:
            raise HTTPException(409, "device_code already exists") from exc
        raise HTTPException(409, "Device conflicts with existing database data") from exc
    return device
