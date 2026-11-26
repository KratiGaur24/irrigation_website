from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models import IrrigationEvent
from app.schemas_irrigation import IrrigationEventRead, ControlStatus, EmergencyResult
from app.services.device_control_service import get_control
from app.services import irrigation_control_service as service

router = APIRouter(prefix='/fields/{field_id}/irrigation', tags=['manual irrigation'])


@router.get('/control', response_model=ControlStatus)
def control_status(field_id: UUID, db: Session = Depends(get_db), control=Depends(get_control)):
    return service.availability(db, field_id, control)


@router.post('/start', response_model=IrrigationEventRead, status_code=201)
def start(field_id: UUID, db: Session = Depends(get_db), control=Depends(get_control)):
    return service.start(db, field_id, control)


@router.post('/stop', response_model=IrrigationEventRead)
def stop(field_id: UUID, db: Session = Depends(get_db), control=Depends(get_control)):
    return service.stop(db, field_id, control)


@router.post('/emergency-stop', response_model=EmergencyResult)
def emergency_stop(field_id: UUID, db: Session = Depends(get_db), control=Depends(get_control)):
    return service.stop(db, field_id, control, emergency=True)


@router.get('/active', response_model=Optional[IrrigationEventRead])
def active(field_id: UUID, db: Session = Depends(get_db)):
    service.field_exists(db, field_id)
    event = service.open_event(db, field_id)
    return service.event_view(db, event) if event else None


@router.get('/history', response_model=list[IrrigationEventRead])
def history(field_id: UUID, db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200),
            from_time: Optional[datetime] = Query(None, alias='from'), to: Optional[datetime] = None):
    service.field_exists(db, field_id)
    for value in (from_time, to):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(422, 'History timestamps must include a timezone.')
    if from_time and to and from_time > to:
        raise HTTPException(422, 'from must be earlier than or equal to to')
    query = select(IrrigationEvent).where(IrrigationEvent.field_id == field_id, IrrigationEvent.ended_at.is_not(None))
    if from_time:
        query = query.where(IrrigationEvent.started_at >= from_time)
    if to:
        query = query.where(IrrigationEvent.started_at <= to)
    return list(db.scalars(query.order_by(IrrigationEvent.started_at.desc(), IrrigationEvent.event_id.desc()).limit(limit)))
