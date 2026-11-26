from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Field, WeatherRecord
from app.schemas import WeatherRecordRead
from app.services.weather_service import refresh_field_weather
from app.services.location_service import weather_location

router = APIRouter(tags=["weather"])


def _latest_snapshot_query(field_id, location):
    newest = select(WeatherRecord.forecast_time, func.max(WeatherRecord.fetched_at).label("fetched_at")).where(
        WeatherRecord.field_id == field_id, WeatherRecord.source == "open-meteo",
        WeatherRecord.request_latitude == location['latitude'], WeatherRecord.request_longitude == location['longitude'],
    ).group_by(WeatherRecord.forecast_time).subquery()
    return select(WeatherRecord).join(newest, (WeatherRecord.forecast_time == newest.c.forecast_time) & (WeatherRecord.fetched_at == newest.c.fetched_at)).where(
        WeatherRecord.field_id == field_id, WeatherRecord.source == "open-meteo",
        WeatherRecord.request_latitude == location['latitude'], WeatherRecord.request_longitude == location['longitude'])


@router.get("/fields/{field_id}/weather/location")
def effective_weather_location(field_id: UUID, db: Session = Depends(get_db)):
    return weather_location(db, field_id)


@router.post("/fields/{field_id}/weather/refresh")
async def refresh_weather(field_id: UUID, db: Session = Depends(get_db)):
    return await refresh_field_weather(db, field_id)


@router.get("/fields/{field_id}/weather/latest", response_model=Optional[WeatherRecordRead])
def latest_weather(field_id: UUID, db: Session = Depends(get_db)):
    location = weather_location(db, field_id)
    if location['status'] != 'configured':
        return None
    now = datetime.now(timezone.utc)
    result = db.scalars(_latest_snapshot_query(field_id, location).where(WeatherRecord.forecast_time <= now).order_by(WeatherRecord.forecast_time.desc()).limit(1)).first()
    if result is None:
        result = db.scalars(_latest_snapshot_query(field_id, location).order_by(WeatherRecord.forecast_time.asc()).limit(1)).first()
    return result


@router.get("/fields/{field_id}/weather/forecast", response_model=list[WeatherRecordRead])
def weather_forecast(field_id: UUID, db: Session = Depends(get_db), limit: int = Query(168, ge=1, le=500)):
    location = weather_location(db, field_id)
    if location['status'] != 'configured':
        return []
    return db.scalars(_latest_snapshot_query(field_id, location).where(WeatherRecord.forecast_time >= datetime.now(timezone.utc)).order_by(WeatherRecord.forecast_time.asc()).limit(limit)).all()


@router.get("/fields/{field_id}/weather/history", response_model=list[WeatherRecordRead])
def weather_history(field_id: UUID, db: Session = Depends(get_db), from_time: Optional[datetime] = Query(None, alias="from"), to: Optional[datetime] = None, limit: int = Query(100, ge=1, le=500)):
    if db.get(Field, field_id) is None:
        raise HTTPException(404, "Field not found")
    if from_time and to and from_time > to:
        raise HTTPException(422, "from must be earlier than or equal to to")
    query = select(WeatherRecord).where(WeatherRecord.field_id == field_id)
    if from_time is not None:
        query = query.where(WeatherRecord.forecast_time >= from_time)
    if to is not None:
        query = query.where(WeatherRecord.forecast_time <= to)
    return db.scalars(query.order_by(WeatherRecord.forecast_time.desc(), WeatherRecord.fetched_at.desc()).limit(limit)).all()
