from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Device, Field, SensorReading
from app.schemas import SensorReadingCreate, SensorReadingRead

router = APIRouter(tags=["sensor readings"])
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def history_query(device_id=None, field_id=None, from_time=None, to_time=None, limit=DEFAULT_LIMIT):
    query = select(SensorReading)
    if device_id is not None:
        query = query.where(SensorReading.device_id == device_id)
    if field_id is not None:
        query = query.where(SensorReading.field_id == field_id)
    if from_time is not None:
        query = query.where(SensorReading.recorded_at >= from_time)
    if to_time is not None:
        query = query.where(SensorReading.recorded_at <= to_time)
    return query.order_by(SensorReading.recorded_at.desc(), SensorReading.reading_id.desc()).limit(limit)


def checked_range(from_time, to_time):
    if from_time is not None and to_time is not None and from_time > to_time:
        raise HTTPException(422, "from must be earlier than or equal to to")


@router.post("/sensor-readings", response_model=SensorReadingRead, status_code=status.HTTP_201_CREATED)
def create_sensor_reading(payload: SensorReadingCreate, db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_code == payload.device_code))
    if device is None:
        raise HTTPException(404, "Unknown device_code")
    reading_data = payload.model_dump(exclude={"device_code"})
    reading = SensorReading(device_id=device.device_id, field_id=device.field_id, **reading_data)
    device.last_seen_at = datetime.now().astimezone()
    try:
        db.add(reading)
        db.commit()
        db.refresh(reading)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Sensor reading conflicts with existing database data") from exc
    return reading


@router.get("/sensor-readings", response_model=list[SensorReadingRead])
def list_sensor_readings(
    device_id: Optional[UUID] = None,
    field_id: Optional[UUID] = None,
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
):
    checked_range(from_time, to_time)
    return db.scalars(history_query(device_id, field_id, from_time, to_time, limit)).all()


@router.get("/devices/{device_id}/sensor-readings", response_model=list[SensorReadingRead])
def list_device_sensor_readings(
    device_id: UUID,
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
):
    if db.get(Device, device_id) is None:
        raise HTTPException(404, "Device not found")
    checked_range(from_time, to_time)
    return db.scalars(history_query(device_id=device_id, from_time=from_time, to_time=to_time, limit=limit)).all()


@router.get("/fields/{field_id}/sensor-readings", response_model=list[SensorReadingRead])
def list_field_sensor_readings(
    field_id: UUID,
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
):
    if db.get(Field, field_id) is None:
        raise HTTPException(404, "Field not found")
    checked_range(from_time, to_time)
    return db.scalars(history_query(field_id=field_id, from_time=from_time, to_time=to_time, limit=limit)).all()
