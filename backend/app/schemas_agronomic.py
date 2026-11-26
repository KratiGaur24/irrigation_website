from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class VarietyRead(BaseModel):
    code: str
    display_name: str
    release_year: Optional[int]
    zone_code: str
    sowing_condition: str
    irrigation_condition: str
    sowing_window_start: Optional[str]
    sowing_window_end: Optional[str]
    first_irrigation_about_das: Optional[int]
    irrigation_note: Optional[str]
    verification_status: str
    source_organization: str
    source_url: str


class AgronomicProfileRead(BaseModel):
    code: str
    crop: str
    country: str
    state: str
    region: str
    zone_code: str
    zone_name: str
    sowing_condition: str
    irrigation_condition: str
    fertility_condition: Optional[str]
    verification_status: str
    scope_note: str
    source_organization: str
    source_url: str


class AgronomicProfileSelection(BaseModel):
    profile_code: str = Field(max_length=150)
    variety_code: Optional[str] = Field(default=None, max_length=100)


class ResolvedProfile(BaseModel):
    crop_cycle_id: str
    profile: AgronomicProfileRead
    sowing_date: date
    agricultural_date: date
    days_after_sowing: int
    selected_variety: Optional[VarietyRead]
    profile_specificity: Literal['regional', 'variety']
    variety_message: str
    sowing_window_match: Optional[bool]
    current_stage: None = None
    stage_status: Literal['not_configured'] = 'not_configured'
    stage_message: str = 'Validated crop-stage timing is not configured for this profile.'
