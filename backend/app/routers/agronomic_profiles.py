from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models import AgronomicProfile, CropVariety, VarietyProfile
from app.schemas_agronomic import AgronomicProfileRead, AgronomicProfileSelection, ResolvedProfile, VarietyRead
from app.services import agronomic_profile_service as service

router = APIRouter(tags=['agronomic profiles'])


@router.get('/agronomic-profiles', response_model=list[AgronomicProfileRead])
def profiles(crop: str = 'Wheat', region: Optional[str] = None, zone: Optional[str] = None, db: Session = Depends(get_db)):
    query = service.profile_query().where(AgronomicProfile.active.is_(True))
    if crop: query = query.where(AgronomicProfile.crop.has(crop_name=crop))
    if region: query = query.where(AgronomicProfile.region == region)
    if zone: query = query.where(AgronomicProfile.zone_code == zone.upper())
    return [service.profile_read(item) for item in db.scalars(query.order_by(AgronomicProfile.code))]


@router.get('/wheat-varieties', response_model=list[VarietyRead])
def wheat_varieties(zone: str = Query('NWPZ'), sowing_condition: Optional[str] = None,
                    irrigation_condition: Optional[str] = None, db: Session = Depends(get_db)):
    query = service.mapping_query().where(VarietyProfile.active.is_(True), CropVariety.active.is_(True),
        AgronomicProfile.active.is_(True), AgronomicProfile.zone_code == zone.upper(),
        AgronomicProfile.crop.has(crop_name='Wheat'))
    if sowing_condition: query = query.where(AgronomicProfile.sowing_condition == sowing_condition)
    if irrigation_condition: query = query.where(AgronomicProfile.irrigation_condition == irrigation_condition)
    return [service.variety_read(item) for item in db.scalars(query.order_by(CropVariety.display_name))]


@router.get('/crop-cycles/{crop_cycle_id}/agronomic-profile', response_model=ResolvedProfile)
def resolved(crop_cycle_id: UUID, db: Session = Depends(get_db)):
    return service.resolve(db, crop_cycle_id)


@router.put('/crop-cycles/{crop_cycle_id}/agronomic-profile', response_model=ResolvedProfile)
def update(crop_cycle_id: UUID, payload: AgronomicProfileSelection, db: Session = Depends(get_db)):
    return service.set_selection(db, crop_cycle_id, payload.profile_code, payload.variety_code,
                                 preserve_variety='variety_code' not in payload.model_fields_set)
