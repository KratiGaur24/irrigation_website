"""Database V2 models. Historical rows use restrictive foreign keys for integrity."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uuid_pk():
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def created_col():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def updated_col():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    farms: Mapped[list["Farm"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")


class Farm(Base):
    __tablename__ = "farms"
    __table_args__ = (CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90"), CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180"), Index("ix_farms_user_id", "user_id"))
    farm_id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    farm_name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    user: Mapped[User] = relationship(back_populates="farms")
    fields: Mapped[list["Field"]] = relationship(back_populates="farm")


class Field(Base):
    __tablename__ = "fields"
    __table_args__ = (CheckConstraint("area_value IS NULL OR area_value > 0"), CheckConstraint("area_m2 IS NULL OR area_m2 > 0"), CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90"), CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180"), CheckConstraint("location_accuracy_m IS NULL OR location_accuracy_m >= 0"), Index("ix_fields_farm_id", "farm_id"))
    field_id: Mapped[UUID] = uuid_pk()
    farm_id: Mapped[UUID] = mapped_column(ForeignKey("farms.farm_id", ondelete="RESTRICT"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(150), nullable=False)
    area_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    area_unit: Mapped[Optional[str]] = mapped_column(String(20))
    area_m2: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3))
    irrigation_method: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    location_source: Mapped[Optional[str]] = mapped_column(String(30))
    location_accuracy_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    farm: Mapped[Farm] = relationship(back_populates="fields")
    crop_cycles: Mapped[list["CropCycle"]] = relationship(back_populates="field")
    soil_profiles: Mapped[list["SoilProfile"]] = relationship(back_populates="field")
    devices: Mapped[list["Device"]] = relationship(back_populates="field")
    sensor_readings: Mapped[list["SensorReading"]] = relationship(back_populates="field")
    weather_records: Mapped[list["WeatherRecord"]] = relationship(back_populates="field")
    water_balance_records: Mapped[list["WaterBalanceRecord"]] = relationship(back_populates="field")
    rule_configurations: Mapped[list["RuleConfiguration"]] = relationship(back_populates="field")
    irrigation_events: Mapped[list["IrrigationEvent"]] = relationship(back_populates="field")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="field")


class Crop(Base):
    __tablename__ = "crops"
    crop_id: Mapped[UUID] = uuid_pk()
    crop_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    scientific_name: Mapped[Optional[str]] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_col()
    crop_cycles: Mapped[list["CropCycle"]] = relationship(back_populates="crop")
    stage_parameters: Mapped[list["CropStageParameter"]] = relationship(back_populates="crop")
    rule_configurations: Mapped[list["RuleConfiguration"]] = relationship(back_populates="crop")


class CropCycle(Base):
    __tablename__ = "crop_cycles"
    __table_args__ = (CheckConstraint("status IN ('planned','active','harvested','cancelled')"), CheckConstraint("expected_harvest_date IS NULL OR expected_harvest_date >= sowing_date"), CheckConstraint("actual_harvest_date IS NULL OR actual_harvest_date >= sowing_date"), Index("ix_crop_cycles_field_id", "field_id"), Index("ix_crop_cycles_crop_id", "crop_id"))
    crop_cycle_id: Mapped[UUID] = uuid_pk()
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    crop_id: Mapped[UUID] = mapped_column(ForeignKey("crops.crop_id", ondelete="RESTRICT"), nullable=False)
    variety: Mapped[Optional[str]] = mapped_column(String(100))
    regional_profile: Mapped[Optional[str]] = mapped_column(String(150))
    agronomic_profile_code: Mapped[Optional[str]] = mapped_column(ForeignKey('agronomic_profiles.code', ondelete='RESTRICT'))
    sowing_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_harvest_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_harvest_date: Mapped[Optional[date]] = mapped_column(Date)
    current_stage: Mapped[Optional[str]] = mapped_column(String(50))
    stage_override: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    field: Mapped[Field] = relationship(back_populates="crop_cycles")
    crop: Mapped[Crop] = relationship(back_populates="crop_cycles")
    water_balance_records: Mapped[list["WaterBalanceRecord"]] = relationship(back_populates="crop_cycle")
    irrigation_events: Mapped[list["IrrigationEvent"]] = relationship(back_populates="crop_cycle")


class CropStageParameter(Base):
    __tablename__ = "crop_stage_parameters"
    __table_args__ = (CheckConstraint("start_day IS NULL OR start_day >= 0"), CheckConstraint("end_day IS NULL OR end_day >= 0"), CheckConstraint("start_day IS NULL OR end_day IS NULL OR end_day >= start_day"), CheckConstraint("kc IS NULL OR kc >= 0"), CheckConstraint("root_depth_m IS NULL OR root_depth_m > 0"), CheckConstraint("depletion_fraction IS NULL OR depletion_fraction BETWEEN 0 AND 1"), Index("ix_crop_stage_parameters_lookup", "crop_id", "regional_profile", "stage_name"))
    parameter_id: Mapped[UUID] = uuid_pk()
    agronomic_profile_code: Mapped[Optional[str]] = mapped_column(ForeignKey('agronomic_profiles.code', ondelete='RESTRICT'))
    variety_code: Mapped[Optional[str]] = mapped_column(ForeignKey('crop_varieties.code', ondelete='RESTRICT'))
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default='experimental')
    verified_on: Mapped[Optional[date]] = mapped_column(Date)
    crop_id: Mapped[UUID] = mapped_column(ForeignKey("crops.crop_id", ondelete="RESTRICT"), nullable=False)
    regional_profile: Mapped[Optional[str]] = mapped_column(String(150))
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_day: Mapped[Optional[int]] = mapped_column(Integer)
    end_day: Mapped[Optional[int]] = mapped_column(Integer)
    kc: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    root_depth_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    depletion_fraction: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    critical_stage: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    technical_notes: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[Optional[str]] = mapped_column(String(255))
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    source_version: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    crop: Mapped[Crop] = relationship(back_populates="stage_parameters")


class SoilProfile(Base):
    __tablename__ = "soil_profiles"
    __table_args__ = (CheckConstraint("field_capacity IS NULL OR field_capacity BETWEEN 0 AND 1"), CheckConstraint("wilting_point IS NULL OR wilting_point BETWEEN 0 AND 1"), CheckConstraint("field_capacity IS NULL OR wilting_point IS NULL OR field_capacity > wilting_point"), Index("ix_soil_profiles_field_id", "field_id"))
    soil_profile_id: Mapped[UUID] = uuid_pk()
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    soil_texture: Mapped[Optional[str]] = mapped_column(String(100))
    field_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 5))
    wilting_point: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 5))
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_reference: Mapped[Optional[str]] = mapped_column(Text)
    confidence_level: Mapped[Optional[str]] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sampled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    field: Mapped[Field] = relationship(back_populates="soil_profiles")
    sensor_calibrations: Mapped[list["SensorCalibration"]] = relationship(back_populates="soil_profile")
    water_balance_records: Mapped[list["WaterBalanceRecord"]] = relationship(back_populates="soil_profile")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_field_id", "field_id"),)
    device_id: Mapped[UUID] = uuid_pk()
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    device_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(150))
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    field: Mapped[Field] = relationship(back_populates="devices")
    sensor_calibrations: Mapped[list["SensorCalibration"]] = relationship(back_populates="device")
    sensor_readings: Mapped[list["SensorReading"]] = relationship(back_populates="device")
    irrigation_events: Mapped[list["IrrigationEvent"]] = relationship(back_populates="device")


class SensorCalibration(Base):
    __tablename__ = "sensor_calibrations"
    __table_args__ = (CheckConstraint("dry_adc IS NULL OR dry_adc >= 0"), CheckConstraint("wet_adc IS NULL OR wet_adc >= 0"), Index("ix_sensor_calibrations_device_calibrated", "device_id", "calibrated_at"))
    calibration_id: Mapped[UUID] = uuid_pk()
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    dry_adc: Mapped[Optional[int]] = mapped_column(Integer)
    wet_adc: Mapped[Optional[int]] = mapped_column(Integer)
    calibration_method: Mapped[Optional[str]] = mapped_column(String(255))
    calibration_soil_profile_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("soil_profiles.soil_profile_id", ondelete="RESTRICT"))
    calibration_notes: Mapped[Optional[str]] = mapped_column(Text)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_col()
    device: Mapped[Device] = relationship(back_populates="sensor_calibrations")
    soil_profile: Mapped[Optional[SoilProfile]] = relationship(back_populates="sensor_calibrations")
    readings: Mapped[list["SensorReading"]] = relationship(back_populates="calibration")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (CheckConstraint("raw_adc IS NULL OR raw_adc >= 0"), CheckConstraint("soil_moisture_pct IS NULL OR soil_moisture_pct BETWEEN 0 AND 100"), CheckConstraint("humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100"), CheckConstraint("flow_rate_lpm IS NULL OR flow_rate_lpm >= 0"), CheckConstraint("flow_pulse_count IS NULL OR flow_pulse_count >= 0"), CheckConstraint("cumulative_water_litres IS NULL OR cumulative_water_litres >= 0"), Index("ix_sensor_readings_device_recorded", "device_id", text("recorded_at DESC")), Index("ix_sensor_readings_field_recorded", "field_id", text("recorded_at DESC")))
    reading_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"), nullable=False)
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    calibration_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("sensor_calibrations.calibration_id", ondelete="RESTRICT"))
    raw_adc: Mapped[Optional[int]] = mapped_column(Integer)
    soil_moisture_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temperature_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    humidity_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    flow_rate_lpm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    flow_pulse_count: Mapped[Optional[int]] = mapped_column(Integer)
    cumulative_water_litres: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    sensor_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    device: Mapped[Device] = relationship(back_populates="sensor_readings")
    field: Mapped[Field] = relationship(back_populates="sensor_readings")
    calibration: Mapped[Optional[SensorCalibration]] = relationship(back_populates="readings")
    water_balance_records: Mapped[list["WaterBalanceRecord"]] = relationship(back_populates="sensor_reading")


class WeatherRecord(Base):
    __tablename__ = "weather_records"
    __table_args__ = (
        CheckConstraint("humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100"),
        CheckConstraint("rain_probability_pct IS NULL OR rain_probability_pct BETWEEN 0 AND 100"),
        CheckConstraint("actual_rainfall_mm IS NULL OR actual_rainfall_mm >= 0"),
        CheckConstraint("forecast_rainfall_mm IS NULL OR forecast_rainfall_mm >= 0"),
        CheckConstraint("eto_mm IS NULL OR eto_mm >= 0"),
        CheckConstraint("wind_speed_mps IS NULL OR wind_speed_mps >= 0"),
        CheckConstraint("sunshine_hours IS NULL OR sunshine_hours >= 0"),
        CheckConstraint("solar_radiation_mj_m2 IS NULL OR solar_radiation_mj_m2 >= 0"),
        Index("ix_weather_records_field_forecast", "field_id", "forecast_time"),
    )
    weather_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    request_longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    temperature_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temperature_min_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    temperature_max_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    humidity_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    wind_speed_mps: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 3))
    solar_radiation_mj_m2: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 3))
    sunshine_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    actual_rainfall_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    rain_probability_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    forecast_rainfall_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    eto_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source: Mapped[Optional[str]] = mapped_column(String(100))
    field: Mapped[Field] = relationship(back_populates="weather_records")
    water_balance_records: Mapped[list["WaterBalanceRecord"]] = relationship(back_populates="weather_record")


class WaterBalanceRecord(Base):
    __tablename__ = "water_balance_records"
    __table_args__ = (
        CheckConstraint("kc_baseline IS NULL OR kc_baseline >= 0"),
        CheckConstraint("kc_used IS NULL OR kc_used >= 0"),
        CheckConstraint("root_depth_m IS NULL OR root_depth_m > 0"),
        CheckConstraint("depletion_fraction_baseline IS NULL OR depletion_fraction_baseline BETWEEN 0 AND 1"),
        CheckConstraint("depletion_fraction_used IS NULL OR depletion_fraction_used BETWEEN 0 AND 1"),
        CheckConstraint("eto_mm IS NULL OR eto_mm >= 0"),
        CheckConstraint("etc_mm IS NULL OR etc_mm >= 0"),
        CheckConstraint("field_capacity IS NULL OR field_capacity BETWEEN 0 AND 1"),
        CheckConstraint("wilting_point IS NULL OR wilting_point BETWEEN 0 AND 1"),
        CheckConstraint("field_capacity IS NULL OR wilting_point IS NULL OR field_capacity > wilting_point"),
        CheckConstraint("taw_mm IS NULL OR taw_mm >= 0"),
        CheckConstraint("raw_mm IS NULL OR raw_mm >= 0"),
        CheckConstraint("root_zone_depletion_mm IS NULL OR root_zone_depletion_mm >= 0"),
        CheckConstraint("effective_rainfall_mm IS NULL OR effective_rainfall_mm >= 0"),
        CheckConstraint("irrigation_depth_mm IS NULL OR irrigation_depth_mm >= 0"),
        CheckConstraint("sensor_moisture_pct IS NULL OR sensor_moisture_pct BETWEEN 0 AND 100"),
        Index("ix_water_balance_field_calculated", "field_id", text("calculated_at DESC")),
    )
    balance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    crop_cycle_id: Mapped[UUID] = mapped_column(ForeignKey("crop_cycles.crop_cycle_id", ondelete="RESTRICT"), nullable=False)
    soil_profile_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("soil_profiles.soil_profile_id", ondelete="RESTRICT"))
    weather_id: Mapped[Optional[int]] = mapped_column(ForeignKey("weather_records.weather_id", ondelete="RESTRICT"))
    sensor_reading_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sensor_readings.reading_id", ondelete="RESTRICT"))
    crop_stage: Mapped[Optional[str]] = mapped_column(String(50))
    kc_baseline: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    kc_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    root_depth_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    depletion_fraction_baseline: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    depletion_fraction_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    eto_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    etc_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    field_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 5))
    wilting_point: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 5))
    taw_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    raw_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    root_zone_depletion_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    effective_rainfall_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    irrigation_depth_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    sensor_moisture_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    decision: Mapped[Optional[str]] = mapped_column(String(20))
    decision_reason: Mapped[Optional[str]] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    field: Mapped[Field] = relationship(back_populates="water_balance_records")
    crop_cycle: Mapped[CropCycle] = relationship(back_populates="water_balance_records")
    soil_profile: Mapped[Optional[SoilProfile]] = relationship(back_populates="water_balance_records")
    weather_record: Mapped[Optional[WeatherRecord]] = relationship(back_populates="water_balance_records")
    sensor_reading: Mapped[Optional[SensorReading]] = relationship(back_populates="water_balance_records")
    irrigation_events: Mapped[list["IrrigationEvent"]] = relationship(back_populates="water_balance_record")


class RuleConfiguration(Base):
    __tablename__ = "rule_configurations"
    __table_args__ = (CheckConstraint("start_moisture_threshold IS NULL OR start_moisture_threshold BETWEEN 0 AND 100"), CheckConstraint("target_moisture_threshold IS NULL OR target_moisture_threshold BETWEEN 0 AND 100"), CheckConstraint("hysteresis_pct IS NULL OR hysteresis_pct BETWEEN 0 AND 100"), CheckConstraint("rain_probability_threshold IS NULL OR rain_probability_threshold BETWEEN 0 AND 100"), CheckConstraint("max_runtime_seconds IS NULL OR max_runtime_seconds > 0"), CheckConstraint("max_volume_litres IS NULL OR max_volume_litres >= 0"), CheckConstraint("minimum_flow_lpm IS NULL OR minimum_flow_lpm >= 0"), CheckConstraint("minimum_forecast_rain_mm IS NULL OR minimum_forecast_rain_mm >= 0"), CheckConstraint("weather_window_hours IS NULL OR weather_window_hours > 0"), CheckConstraint("stale_sensor_timeout_seconds IS NULL OR stale_sensor_timeout_seconds > 0"), CheckConstraint("sensor_model_disagreement_tolerance IS NULL OR sensor_model_disagreement_tolerance >= 0"), Index("ix_rule_configurations_field_crop", "field_id", "crop_id"))
    rule_id: Mapped[UUID] = uuid_pk()
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    crop_id: Mapped[UUID] = mapped_column(ForeignKey("crops.crop_id", ondelete="RESTRICT"), nullable=False)
    stage_name: Mapped[Optional[str]] = mapped_column(String(50))
    start_moisture_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    target_moisture_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    hysteresis_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    max_runtime_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    max_volume_litres: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    minimum_flow_lpm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    rain_probability_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    minimum_forecast_rain_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    weather_window_hours: Mapped[Optional[int]] = mapped_column(Integer)
    stale_sensor_timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    sensor_model_disagreement_tolerance: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    field: Mapped[Field] = relationship(back_populates="rule_configurations")
    crop: Mapped[Crop] = relationship(back_populates="rule_configurations")


class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"
    __table_args__ = (CheckConstraint("mode IN ('AUTO','MANUAL')"), CheckConstraint("status IN ('started','completed','stopped','failed')"), CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0"), CheckConstraint("moisture_before_pct IS NULL OR moisture_before_pct BETWEEN 0 AND 100"), CheckConstraint("moisture_after_pct IS NULL OR moisture_after_pct BETWEEN 0 AND 100"), CheckConstraint("water_used_litres IS NULL OR water_used_litres >= 0"), Index("ix_irrigation_events_field_started", "field_id", text("started_at DESC")))
    event_id: Mapped[UUID] = uuid_pk()
    control_mode: Mapped[Optional[str]] = mapped_column(String(20))
    start_reading_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sensor_readings.reading_id', ondelete='RESTRICT'))
    command_acknowledged: Mapped[Optional[bool]] = mapped_column(Boolean)
    field_id: Mapped[UUID] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"), nullable=False)
    crop_cycle_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("crop_cycles.crop_cycle_id", ondelete="RESTRICT"))
    device_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"))
    balance_id: Mapped[Optional[int]] = mapped_column(ForeignKey("water_balance_records.balance_id", ondelete="RESTRICT"))
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    moisture_before_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    moisture_after_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    water_used_litres: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    fault_code: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = created_col()
    field: Mapped[Field] = relationship(back_populates="irrigation_events")
    crop_cycle: Mapped[Optional[CropCycle]] = relationship(back_populates="irrigation_events")
    device: Mapped[Optional[Device]] = relationship(back_populates="irrigation_events")
    water_balance_record: Mapped[Optional[WaterBalanceRecord]] = relationship(back_populates="irrigation_events")


Index('uq_irrigation_open_field', IrrigationEvent.field_id, unique=True,
      postgresql_where=IrrigationEvent.ended_at.is_(None))
IrrigationEvent.__table__.append_constraint(CheckConstraint(
    "control_mode IS NULL OR control_mode IN ('simulated','hardware')", name='ck_event_control_mode'))


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", text("created_at DESC")),)
    notification_id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    field_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("fields.field_id", ondelete="RESTRICT"))
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_col()
    user: Mapped[User] = relationship(back_populates="notifications")
    field: Mapped[Optional[Field]] = relationship(back_populates="notifications")


class AgronomicProfile(Base):
    __tablename__ = 'agronomic_profiles'
    code: Mapped[str] = mapped_column(String(150), primary_key=True)
    crop_id: Mapped[UUID] = mapped_column(ForeignKey('crops.crop_id', ondelete='RESTRICT'), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(150), nullable=False)
    zone_code: Mapped[str] = mapped_column(String(20), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(150), nullable=False)
    sowing_condition: Mapped[str] = mapped_column(String(30), nullable=False)
    irrigation_condition: Mapped[str] = mapped_column(String(40), nullable=False)
    fertility_condition: Mapped[Optional[str]] = mapped_column(String(40))
    agricultural_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_note: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_organization: Mapped[str] = mapped_column(String(150), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_on: Mapped[Optional[date]] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    crop: Mapped[Crop] = relationship()


class CropVariety(Base):
    __tablename__ = 'crop_varieties'
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    crop_id: Mapped[UUID] = mapped_column(ForeignKey('crops.crop_id', ondelete='RESTRICT'), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))


class VarietyProfile(Base):
    __tablename__ = 'variety_profiles'
    profile_code: Mapped[str] = mapped_column(ForeignKey('agronomic_profiles.code', ondelete='RESTRICT'), primary_key=True)
    variety_code: Mapped[str] = mapped_column(ForeignKey('crop_varieties.code', ondelete='RESTRICT'), primary_key=True)
    release_year: Mapped[Optional[int]] = mapped_column(Integer)
    sowing_window_start: Mapped[Optional[str]] = mapped_column(String(5))
    sowing_window_end: Mapped[Optional[str]] = mapped_column(String(5))
    first_irrigation_about_das: Mapped[Optional[int]] = mapped_column(Integer)
    irrigation_note: Mapped[Optional[str]] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_organization: Mapped[str] = mapped_column(String(150), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_on: Mapped[Optional[date]] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    variety: Mapped[CropVariety] = relationship()
    profile: Mapped[AgronomicProfile] = relationship()


__all__ = ["Base", "User", "Farm", "Field", "Crop", "CropCycle", "CropStageParameter", "SoilProfile", "Device", "SensorCalibration", "SensorReading", "WeatherRecord", "WaterBalanceRecord", "RuleConfiguration", "IrrigationEvent", "Notification", "AgronomicProfile", "CropVariety", "VarietyProfile"]
