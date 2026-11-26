from datetime import date
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import AgronomicProfile, CropCycle, CropVariety, VarietyProfile
from app.schemas_agronomic import AgronomicProfileRead, VarietyRead, ResolvedProfile


def profile_read(profile):
    return AgronomicProfileRead(code=profile.code, crop=profile.crop.crop_name, country=profile.country,
        state=profile.state, region=profile.region, zone_code=profile.zone_code, zone_name=profile.zone_name,
        sowing_condition=profile.sowing_condition, irrigation_condition=profile.irrigation_condition,
        fertility_condition=profile.fertility_condition, verification_status=profile.verification_status, scope_note=profile.scope_note,
        source_organization=profile.source_organization, source_url=profile.source_url)


def variety_read(mapping):
    profile, variety = mapping.profile, mapping.variety
    return VarietyRead(code=variety.code, display_name=variety.display_name, release_year=mapping.release_year,
        zone_code=profile.zone_code, sowing_condition=profile.sowing_condition,
        irrigation_condition=profile.irrigation_condition, sowing_window_start=mapping.sowing_window_start,
        sowing_window_end=mapping.sowing_window_end, first_irrigation_about_das=mapping.first_irrigation_about_das,
        irrigation_note=mapping.irrigation_note, verification_status=mapping.verification_status,
        source_organization=mapping.source_organization, source_url=mapping.source_url)


def profile_query():
    return select(AgronomicProfile).options(joinedload(AgronomicProfile.crop))


def mapping_query():
    return (select(VarietyProfile).join(VarietyProfile.profile).join(VarietyProfile.variety)
            .options(joinedload(VarietyProfile.profile).joinedload(AgronomicProfile.crop), joinedload(VarietyProfile.variety)))


def month_day_in_window(sowing_date, start, end):
    if not start or not end:
        return None
    value = sowing_date.strftime('%m-%d')
    return start <= value <= end if start <= end else value >= start or value <= end


def resolve(db, cycle_id, today=None):
    cycle = db.scalar(select(CropCycle).where(CropCycle.crop_cycle_id == cycle_id))
    if cycle is None:
        raise HTTPException(404, 'Crop cycle not found')
    if not cycle.agronomic_profile_code:
        raise HTTPException(409, 'Agronomic profile is not configured for this crop cycle.')
    profile = db.scalar(profile_query().where(AgronomicProfile.code == cycle.agronomic_profile_code, AgronomicProfile.active.is_(True)))
    if profile is None or profile.crop_id != cycle.crop_id:
        raise HTTPException(409, 'Configured agronomic profile is unavailable or incompatible with this crop.')
    agricultural_date = today
    if agricultural_date is None:
        from datetime import datetime, timezone
        agricultural_date = datetime.now(timezone.utc).astimezone(ZoneInfo(profile.agricultural_timezone)).date()
    days = (agricultural_date - cycle.sowing_date).days
    if days < 0:
        raise HTTPException(409, 'Sowing date is after the current agricultural date.')
    selected, window = None, None
    if cycle.variety:
        mapping = db.scalar(mapping_query().where(VarietyProfile.profile_code == profile.code,
            VarietyProfile.variety_code == cycle.variety, VarietyProfile.active.is_(True)))
        if mapping is None:
            raise HTTPException(409, 'Selected variety is not compatible with this agronomic profile.')
        selected = variety_read(mapping)
        window = month_day_in_window(cycle.sowing_date, mapping.sowing_window_start, mapping.sowing_window_end)
    return ResolvedProfile(crop_cycle_id=str(cycle.crop_cycle_id), profile=profile_read(profile), sowing_date=cycle.sowing_date,
        agricultural_date=agricultural_date, days_after_sowing=days, selected_variety=selected,
        profile_specificity='variety' if selected else 'regional',
        variety_message='Variety-specific official metadata is available.' if selected else "You can continue without selecting a variety. Variety-specific guidance may be less precise. Check the seed bag or label if available.",
        sowing_window_match=window)


def set_selection(db, cycle_id, profile_code, variety_code, preserve_variety=False):
    cycle = db.scalar(select(CropCycle).where(CropCycle.crop_cycle_id == cycle_id).with_for_update())
    if cycle is None:
        raise HTTPException(404, 'Crop cycle not found')
    profile = db.scalar(profile_query().where(AgronomicProfile.code == profile_code, AgronomicProfile.active.is_(True)))
    if profile is None:
        raise HTTPException(404, 'Agronomic profile not found')
    if profile.crop_id != cycle.crop_id:
        raise HTTPException(409, 'Agronomic profile is not compatible with this crop cycle.')
    chosen = cycle.variety if preserve_variety else variety_code
    normalized = chosen.strip().upper() if chosen else None
    if normalized:
        mapping = db.scalar(mapping_query().where(VarietyProfile.profile_code == profile_code,
            VarietyProfile.variety_code == normalized, VarietyProfile.active.is_(True), CropVariety.active.is_(True)))
        if mapping is None:
            raise HTTPException(409, 'Selected variety is not compatible with this zone and production condition.')
    cycle.agronomic_profile_code = profile.code
    cycle.regional_profile = profile.code  # Preserve the existing legacy field as a stable profile code.
    cycle.variety = normalized
    db.flush()
    result = resolve(db, cycle_id)
    db.commit()
    return result
