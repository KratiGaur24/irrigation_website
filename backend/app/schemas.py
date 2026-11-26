from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field as PydanticField, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CropRead(ORMModel):
    crop_id: UUID
    crop_name: str
    scientific_name: Optional[str]
    active: bool


class FarmCreate(BaseModel):
    user_id: UUID
    farm_name: str = PydanticField(min_length=1, max_length=150)
    location_name: Optional[str] = PydanticField(default=None, max_length=255)
    latitude: Optional[Decimal] = PydanticField(default=None, ge=-90, le=90)
    longitude: Optional[Decimal] = PydanticField(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both latitude and longitude, or neither")
        return self


class FarmRead(ORMModel):
    farm_id: UUID
    user_id: UUID
    farm_name: str
    location_name: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


class FarmEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    farm_name: str = PydanticField(min_length=1, max_length=150)
    location_name: Optional[str] = PydanticField(default=None, max_length=255)
    latitude: Optional[Decimal] = PydanticField(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: Optional[Decimal] = PydanticField(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        supplied = self.model_fields_set
        if ('latitude' in supplied) != ('longitude' in supplied) or (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both latitude and longitude, or neither")
        return self


class CropCycleEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sowing_date: date
    expected_harvest_date: Optional[date] = None


class FieldCreate(BaseModel):
    farm_id: UUID
    field_name: str = PydanticField(min_length=1, max_length=150)
    area_value: Optional[Decimal] = PydanticField(default=None, gt=0)
    area_unit: Optional[str] = PydanticField(default=None, max_length=20)
    area_m2: Optional[Decimal] = PydanticField(default=None, gt=0)
    irrigation_method: Optional[str] = PydanticField(default=None, max_length=100)
    latitude: Optional[Decimal] = PydanticField(default=None, ge=-90, le=90)
    longitude: Optional[Decimal] = PydanticField(default=None, ge=-180, le=180)
    location_source: Optional[str] = PydanticField(default=None, max_length=30)
    location_accuracy_m: Optional[Decimal] = PydanticField(default=None, ge=0)


class FieldRead(ORMModel):
    field_id: UUID
    farm_id: UUID
    field_name: str
    area_value: Optional[Decimal]
    area_unit: Optional[str]
    area_m2: Optional[Decimal]
    irrigation_method: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    location_source: Optional[str]
    location_accuracy_m: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


class CropCycleCreate(BaseModel):
    field_id: UUID
    crop_id: UUID
    variety: Optional[str] = PydanticField(default=None, max_length=100)
    regional_profile: Optional[str] = PydanticField(default=None, max_length=150)
    agronomic_profile_code: Optional[str] = PydanticField(default=None, max_length=150)
    sowing_date: date
    expected_harvest_date: Optional[date] = None
    actual_harvest_date: Optional[date] = None
    current_stage: Optional[str] = PydanticField(default=None, max_length=50)
    stage_override: Optional[str] = PydanticField(default=None, max_length=50)
    status: str = PydanticField(pattern="^(planned|active|harvested|cancelled)$")

    @model_validator(mode="after")
    def validate_harvest_dates(self):
        for name in ("expected_harvest_date", "actual_harvest_date"):
            value = getattr(self, name)
            if value is not None and value < self.sowing_date:
                raise ValueError(f"{name} must be on or after sowing_date")
        return self


class CropCycleRead(ORMModel):
    crop_cycle_id: UUID
    field_id: UUID
    crop_id: UUID
    crop: CropRead
    variety: Optional[str]
    regional_profile: Optional[str]
    agronomic_profile_code: Optional[str]
    sowing_date: date
    expected_harvest_date: Optional[date]
    actual_harvest_date: Optional[date]
    current_stage: Optional[str]
    stage_override: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class DeviceCreate(BaseModel):
    field_id: UUID
    device_code: str = PydanticField(min_length=1, max_length=100)
    device_name: Optional[str] = PydanticField(default=None, max_length=150)
    device_type: str = PydanticField(min_length=1, max_length=50)
    status: str = PydanticField(min_length=1, max_length=30)
    firmware_version: Optional[str] = PydanticField(default=None, max_length=50)


class DeviceRead(ORMModel):
    device_id: UUID
    field_id: UUID
    device_code: str
    device_name: Optional[str]
    device_type: str
    last_seen_at: Optional[datetime]
    status: str
    firmware_version: Optional[str]
    created_at: datetime
    updated_at: datetime


class SoilProfileCreate(BaseModel):
    field_id: UUID
    soil_texture: Optional[str] = PydanticField(default=None, max_length=100)
    field_capacity: Optional[Decimal] = PydanticField(default=None, ge=0, le=1)
    wilting_point: Optional[Decimal] = PydanticField(default=None, ge=0, le=1)
    source_type: Optional[str] = PydanticField(default=None, max_length=50)
    source_reference: Optional[str] = None
    confidence_level: Optional[str] = PydanticField(default=None, max_length=30)
    active: bool = True
    sampled_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_soil_values(self):
        if self.field_capacity is not None and self.wilting_point is not None and self.field_capacity <= self.wilting_point:
            raise ValueError("field_capacity must exceed wilting_point")
        return self


class SoilProfileRead(ORMModel):
    soil_profile_id: UUID
    field_id: UUID
    soil_texture: Optional[str]
    field_capacity: Optional[Decimal]
    wilting_point: Optional[Decimal]
    source_type: Optional[str]
    source_reference: Optional[str]
    confidence_level: Optional[str]
    active: bool
    sampled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class SensorReadingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_code: str = PydanticField(min_length=1, max_length=100)
    raw_adc: Optional[int] = PydanticField(default=None, ge=0)
    soil_moisture_pct: Optional[Decimal] = PydanticField(default=None, ge=0, le=100)
    temperature_c: Optional[Decimal] = None
    humidity_pct: Optional[Decimal] = PydanticField(default=None, ge=0, le=100)
    flow_rate_lpm: Optional[Decimal] = PydanticField(default=None, ge=0)
    flow_pulse_count: Optional[int] = PydanticField(default=None, ge=0)
    cumulative_water_litres: Optional[Decimal] = PydanticField(default=None, ge=0)
    sensor_valid: bool = True
    recorded_at: datetime = PydanticField(default_factory=lambda: datetime.now(timezone.utc))


class SensorReadingRead(ORMModel):
    reading_id: int
    device_id: UUID
    field_id: UUID
    calibration_id: Optional[UUID]
    raw_adc: Optional[int]
    soil_moisture_pct: Optional[Decimal]
    temperature_c: Optional[Decimal]
    humidity_pct: Optional[Decimal]
    flow_rate_lpm: Optional[Decimal]
    flow_pulse_count: Optional[int]
    cumulative_water_litres: Optional[Decimal]
    sensor_valid: bool
    recorded_at: datetime
    received_at: datetime

class WeatherRecordRead(ORMModel):
    weather_id: int
    field_id: UUID
    request_latitude: Optional[Decimal] = None
    request_longitude: Optional[Decimal] = None
    temperature_c: Optional[Decimal]
    temperature_min_c: Optional[Decimal]
    temperature_max_c: Optional[Decimal]
    humidity_pct: Optional[Decimal]
    wind_speed_mps: Optional[Decimal]
    solar_radiation_mj_m2: Optional[Decimal]
    sunshine_hours: Optional[Decimal]
    actual_rainfall_mm: Optional[Decimal]
    rain_probability_pct: Optional[Decimal]
    forecast_rainfall_mm: Optional[Decimal]
    eto_mm: Optional[Decimal]
    forecast_time: datetime
    fetched_at: datetime
    source: Optional[str]
