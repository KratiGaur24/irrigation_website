from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class IrrigationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: UUID
    field_id: UUID
    device_id: Optional[UUID]
    mode: str
    status: str
    control_mode: Optional[str]
    command_acknowledged: Optional[bool]
    trigger_reason: Optional[str]
    fault_code: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    moisture_before_pct: Optional[Decimal]
    moisture_after_pct: Optional[Decimal]
    water_used_litres: Optional[Decimal]
    current_duration_seconds: Optional[int] = None
    current_moisture_pct: Optional[Decimal] = None
    current_flow_rate_lpm: Optional[Decimal] = None
    current_water_used_litres: Optional[Decimal] = None
    measurement_time: Optional[datetime] = None
    volume_baseline_time: Optional[datetime] = None
    volume_measurement_time: Optional[datetime] = None


class ControlStatus(BaseModel):
    control_mode: str
    available: bool
    start_available: bool
    device_id: Optional[UUID] = None
    device_status: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    message: str


class EmergencyResult(BaseModel):
    acknowledged: bool
    control_mode: str
    message: str
    session: Optional[IrrigationEventRead] = None
