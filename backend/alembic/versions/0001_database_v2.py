"""Initial PostgreSQL Database V2 schema.

Revision ID: 0001_database_v2
Revises:
"""
from alembic import op

revision = "0001_database_v2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Kept as fixed DDL: later model edits cannot rewrite this migration's schema.
    op.execute("""CREATE TABLE users (
      user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(100) NOT NULL,
      email varchar(255) NOT NULL UNIQUE, password_hash varchar(255) NOT NULL, phone varchar(20),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE farms (
      farm_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
      farm_name varchar(150) NOT NULL, location_name varchar(255), latitude numeric(9,6), longitude numeric(9,6),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_farms_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
      CONSTRAINT ck_farms_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180))""")
    op.execute("""CREATE TABLE fields (
      field_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), farm_id uuid NOT NULL REFERENCES farms(farm_id) ON DELETE RESTRICT,
      field_name varchar(150) NOT NULL, area_value numeric(12,3), area_unit varchar(20), area_m2 numeric(14,3), irrigation_method varchar(100),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_fields_area_value CHECK (area_value IS NULL OR area_value > 0),
      CONSTRAINT ck_fields_area_m2 CHECK (area_m2 IS NULL OR area_m2 > 0))""")
    op.execute("""CREATE TABLE crops (
      crop_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_name varchar(100) NOT NULL UNIQUE,
      scientific_name varchar(150), active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE crop_cycles (
      crop_cycle_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      crop_id uuid NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT, variety varchar(100), regional_profile varchar(150),
      sowing_date date NOT NULL, expected_harvest_date date, actual_harvest_date date, current_stage varchar(50), stage_override varchar(50),
      status varchar(20) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_crop_cycles_status CHECK (status IN ('planned','active','harvested','cancelled')),
      CONSTRAINT ck_crop_cycles_expected_date CHECK (expected_harvest_date IS NULL OR expected_harvest_date >= sowing_date),
      CONSTRAINT ck_crop_cycles_actual_date CHECK (actual_harvest_date IS NULL OR actual_harvest_date >= sowing_date))""")
    op.execute("""CREATE TABLE crop_stage_parameters (
      parameter_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_id uuid NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT,
      regional_profile varchar(150), stage_name varchar(50) NOT NULL, start_day integer, end_day integer,
      kc numeric(6,3), root_depth_m numeric(6,3), depletion_fraction numeric(5,4), critical_stage boolean NOT NULL DEFAULT false,
      technical_notes text, source_name varchar(255), source_reference text, source_version varchar(100),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_stage_start_day CHECK (start_day IS NULL OR start_day >= 0),
      CONSTRAINT ck_stage_end_day CHECK (end_day IS NULL OR end_day >= 0),
      CONSTRAINT ck_stage_day_range CHECK (start_day IS NULL OR end_day IS NULL OR end_day >= start_day),
      CONSTRAINT ck_stage_kc CHECK (kc IS NULL OR kc >= 0), CONSTRAINT ck_stage_root_depth CHECK (root_depth_m IS NULL OR root_depth_m > 0),
      CONSTRAINT ck_stage_depletion_fraction CHECK (depletion_fraction IS NULL OR depletion_fraction BETWEEN 0 AND 1))""")
    op.execute("""CREATE TABLE soil_profiles (
      soil_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      soil_texture varchar(100), field_capacity numeric(7,5), wilting_point numeric(7,5), source_type varchar(50),
      source_reference text, confidence_level varchar(30), active boolean NOT NULL DEFAULT true, sampled_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_soil_field_capacity CHECK (field_capacity IS NULL OR field_capacity BETWEEN 0 AND 1),
      CONSTRAINT ck_soil_wilting_point CHECK (wilting_point IS NULL OR wilting_point BETWEEN 0 AND 1),
      CONSTRAINT ck_soil_capacity_gt_wilting CHECK (field_capacity IS NULL OR wilting_point IS NULL OR field_capacity > wilting_point))""")
    op.execute("""CREATE TABLE devices (
      device_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      device_code varchar(100) NOT NULL UNIQUE, device_name varchar(150), device_type varchar(50) NOT NULL,
      last_seen_at timestamptz, status varchar(30) NOT NULL, firmware_version varchar(50),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE sensor_calibrations (
      calibration_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), device_id uuid NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
      sensor_type varchar(50) NOT NULL, dry_adc integer, wet_adc integer, calibration_method varchar(255),
      calibration_soil_profile_id uuid REFERENCES soil_profiles(soil_profile_id) ON DELETE RESTRICT, calibration_notes text,
      calibrated_at timestamptz NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_calibration_dry_adc CHECK (dry_adc IS NULL OR dry_adc >= 0),
      CONSTRAINT ck_calibration_wet_adc CHECK (wet_adc IS NULL OR wet_adc >= 0))""")
    op.execute("""CREATE TABLE sensor_readings (
      reading_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
      device_id uuid NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
      field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      calibration_id uuid REFERENCES sensor_calibrations(calibration_id) ON DELETE RESTRICT,
      raw_adc integer, soil_moisture_pct numeric(5,2), temperature_c numeric(5,2), humidity_pct numeric(5,2),
      flow_rate_lpm numeric(8,3), flow_pulse_count integer, cumulative_water_litres numeric(12,3),
      sensor_valid boolean NOT NULL DEFAULT true, recorded_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_reading_raw_adc CHECK (raw_adc IS NULL OR raw_adc >= 0),
      CONSTRAINT ck_reading_moisture CHECK (soil_moisture_pct IS NULL OR soil_moisture_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_reading_humidity CHECK (humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_reading_flow CHECK (flow_rate_lpm IS NULL OR flow_rate_lpm >= 0),
      CONSTRAINT ck_reading_pulses CHECK (flow_pulse_count IS NULL OR flow_pulse_count >= 0),
      CONSTRAINT ck_reading_cumulative CHECK (cumulative_water_litres IS NULL OR cumulative_water_litres >= 0))""")
    op.execute("""CREATE TABLE weather_records (
      weather_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
      field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      temperature_c numeric(5,2), temperature_min_c numeric(5,2), temperature_max_c numeric(5,2), humidity_pct numeric(5,2),
      wind_speed_mps numeric(7,3), solar_radiation_mj_m2 numeric(9,3), sunshine_hours numeric(5,2),
      actual_rainfall_mm numeric(8,2), rain_probability_pct numeric(5,2), forecast_rainfall_mm numeric(8,2), eto_mm numeric(8,3),
      forecast_time timestamptz NOT NULL, fetched_at timestamptz NOT NULL DEFAULT now(), source varchar(100),
      CONSTRAINT ck_weather_humidity CHECK (humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_weather_rain_probability CHECK (rain_probability_pct IS NULL OR rain_probability_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_weather_actual_rain CHECK (actual_rainfall_mm IS NULL OR actual_rainfall_mm >= 0),
      CONSTRAINT ck_weather_forecast_rain CHECK (forecast_rainfall_mm IS NULL OR forecast_rainfall_mm >= 0),
      CONSTRAINT ck_weather_eto CHECK (eto_mm IS NULL OR eto_mm >= 0),
      CONSTRAINT ck_weather_wind CHECK (wind_speed_mps IS NULL OR wind_speed_mps >= 0),
      CONSTRAINT ck_weather_sunshine CHECK (sunshine_hours IS NULL OR sunshine_hours >= 0),
      CONSTRAINT ck_weather_solar CHECK (solar_radiation_mj_m2 IS NULL OR solar_radiation_mj_m2 >= 0))""")
    op.execute("""CREATE TABLE water_balance_records (
      balance_id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
      field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      crop_cycle_id uuid NOT NULL REFERENCES crop_cycles(crop_cycle_id) ON DELETE RESTRICT,
      soil_profile_id uuid REFERENCES soil_profiles(soil_profile_id) ON DELETE RESTRICT,
      weather_id bigint REFERENCES weather_records(weather_id) ON DELETE RESTRICT,
      sensor_reading_id bigint REFERENCES sensor_readings(reading_id) ON DELETE RESTRICT,
      crop_stage varchar(50), kc_baseline numeric(6,3), kc_used numeric(6,3), root_depth_m numeric(6,3),
      depletion_fraction_baseline numeric(5,4), depletion_fraction_used numeric(5,4), eto_mm numeric(8,3), etc_mm numeric(8,3),
      field_capacity numeric(7,5), wilting_point numeric(7,5), taw_mm numeric(10,3), raw_mm numeric(10,3),
      root_zone_depletion_mm numeric(10,3), effective_rainfall_mm numeric(10,3), irrigation_depth_mm numeric(10,3),
      sensor_moisture_pct numeric(5,2), decision varchar(20), decision_reason text, calculated_at timestamptz NOT NULL,
      CONSTRAINT ck_balance_kc_baseline CHECK (kc_baseline IS NULL OR kc_baseline >= 0),
      CONSTRAINT ck_balance_kc_used CHECK (kc_used IS NULL OR kc_used >= 0),
      CONSTRAINT ck_balance_root_depth CHECK (root_depth_m IS NULL OR root_depth_m > 0),
      CONSTRAINT ck_balance_depletion_baseline CHECK (depletion_fraction_baseline IS NULL OR depletion_fraction_baseline BETWEEN 0 AND 1),
      CONSTRAINT ck_balance_depletion_used CHECK (depletion_fraction_used IS NULL OR depletion_fraction_used BETWEEN 0 AND 1),
      CONSTRAINT ck_balance_eto CHECK (eto_mm IS NULL OR eto_mm >= 0), CONSTRAINT ck_balance_etc CHECK (etc_mm IS NULL OR etc_mm >= 0),
      CONSTRAINT ck_balance_field_capacity CHECK (field_capacity IS NULL OR field_capacity BETWEEN 0 AND 1),
      CONSTRAINT ck_balance_wilting_point CHECK (wilting_point IS NULL OR wilting_point BETWEEN 0 AND 1),
      CONSTRAINT ck_balance_capacity_gt_wilting CHECK (field_capacity IS NULL OR wilting_point IS NULL OR field_capacity > wilting_point),
      CONSTRAINT ck_balance_taw CHECK (taw_mm IS NULL OR taw_mm >= 0), CONSTRAINT ck_balance_raw CHECK (raw_mm IS NULL OR raw_mm >= 0),
      CONSTRAINT ck_balance_depletion CHECK (root_zone_depletion_mm IS NULL OR root_zone_depletion_mm >= 0),
      CONSTRAINT ck_balance_rain CHECK (effective_rainfall_mm IS NULL OR effective_rainfall_mm >= 0),
      CONSTRAINT ck_balance_irrigation_depth CHECK (irrigation_depth_mm IS NULL OR irrigation_depth_mm >= 0),
      CONSTRAINT ck_balance_sensor_moisture CHECK (sensor_moisture_pct IS NULL OR sensor_moisture_pct BETWEEN 0 AND 100))""")
    op.execute("""CREATE TABLE rule_configurations (
      rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      crop_id uuid NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT, stage_name varchar(50),
      start_moisture_threshold numeric(5,2), target_moisture_threshold numeric(5,2), hysteresis_pct numeric(5,2),
      max_runtime_seconds integer, max_volume_litres numeric(10,2), minimum_flow_lpm numeric(8,3),
      rain_probability_threshold numeric(5,2), minimum_forecast_rain_mm numeric(8,2), weather_window_hours integer,
      stale_sensor_timeout_seconds integer, sensor_model_disagreement_tolerance numeric(8,3), enabled boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_rule_start_moisture CHECK (start_moisture_threshold IS NULL OR start_moisture_threshold BETWEEN 0 AND 100),
      CONSTRAINT ck_rule_target_moisture CHECK (target_moisture_threshold IS NULL OR target_moisture_threshold BETWEEN 0 AND 100),
      CONSTRAINT ck_rule_hysteresis CHECK (hysteresis_pct IS NULL OR hysteresis_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_rule_rain_probability CHECK (rain_probability_threshold IS NULL OR rain_probability_threshold BETWEEN 0 AND 100),
      CONSTRAINT ck_rule_runtime CHECK (max_runtime_seconds IS NULL OR max_runtime_seconds > 0),
      CONSTRAINT ck_rule_volume CHECK (max_volume_litres IS NULL OR max_volume_litres >= 0),
      CONSTRAINT ck_rule_flow CHECK (minimum_flow_lpm IS NULL OR minimum_flow_lpm >= 0),
      CONSTRAINT ck_rule_rain_mm CHECK (minimum_forecast_rain_mm IS NULL OR minimum_forecast_rain_mm >= 0),
      CONSTRAINT ck_rule_weather_window CHECK (weather_window_hours IS NULL OR weather_window_hours > 0),
      CONSTRAINT ck_rule_stale_timeout CHECK (stale_sensor_timeout_seconds IS NULL OR stale_sensor_timeout_seconds > 0),
      CONSTRAINT ck_rule_disagreement CHECK (sensor_model_disagreement_tolerance IS NULL OR sensor_model_disagreement_tolerance >= 0))""")
    op.execute("""CREATE TABLE irrigation_events (
      event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), field_id uuid NOT NULL REFERENCES fields(field_id) ON DELETE RESTRICT,
      crop_cycle_id uuid REFERENCES crop_cycles(crop_cycle_id) ON DELETE RESTRICT,
      device_id uuid REFERENCES devices(device_id) ON DELETE RESTRICT,
      balance_id bigint REFERENCES water_balance_records(balance_id) ON DELETE RESTRICT,
      mode varchar(20) NOT NULL, trigger_reason text, started_at timestamptz NOT NULL, ended_at timestamptz,
      duration_seconds integer, moisture_before_pct numeric(5,2), moisture_after_pct numeric(5,2),
      water_used_litres numeric(10,2), status varchar(30) NOT NULL, fault_code varchar(50), created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_event_mode CHECK (mode IN ('AUTO','MANUAL')),
      CONSTRAINT ck_event_status CHECK (status IN ('started','completed','stopped','failed')),
      CONSTRAINT ck_event_duration CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
      CONSTRAINT ck_event_moisture_before CHECK (moisture_before_pct IS NULL OR moisture_before_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_event_moisture_after CHECK (moisture_after_pct IS NULL OR moisture_after_pct BETWEEN 0 AND 100),
      CONSTRAINT ck_event_water CHECK (water_used_litres IS NULL OR water_used_litres >= 0))""")
    op.execute("""CREATE TABLE notifications (
      notification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
      field_id uuid REFERENCES fields(field_id) ON DELETE RESTRICT, type varchar(50) NOT NULL, title varchar(150) NOT NULL,
      message text NOT NULL, is_read boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now())""")
    for statement in (
        "CREATE INDEX ix_farms_user_id ON farms(user_id)",
        "CREATE INDEX ix_fields_farm_id ON fields(farm_id)",
        "CREATE INDEX ix_crop_cycles_field_id ON crop_cycles(field_id)",
        "CREATE INDEX ix_crop_cycles_crop_id ON crop_cycles(crop_id)",
        "CREATE INDEX ix_crop_stage_parameters_lookup ON crop_stage_parameters(crop_id, regional_profile, stage_name)",
        "CREATE INDEX ix_soil_profiles_field_id ON soil_profiles(field_id)",
        "CREATE INDEX ix_devices_field_id ON devices(field_id)",
        "CREATE INDEX ix_sensor_calibrations_device_calibrated ON sensor_calibrations(device_id, calibrated_at)",
        "CREATE INDEX ix_sensor_readings_device_recorded ON sensor_readings(device_id, recorded_at DESC)",
        "CREATE INDEX ix_sensor_readings_field_recorded ON sensor_readings(field_id, recorded_at DESC)",
        "CREATE INDEX ix_weather_records_field_forecast ON weather_records(field_id, forecast_time)",
        "CREATE INDEX ix_water_balance_field_calculated ON water_balance_records(field_id, calculated_at DESC)",
        "CREATE INDEX ix_rule_configurations_field_crop ON rule_configurations(field_id, crop_id)",
        "CREATE INDEX ix_irrigation_events_field_started ON irrigation_events(field_id, started_at DESC)",
        "CREATE INDEX ix_notifications_user_created ON notifications(user_id, created_at DESC)",
    ):
        op.execute(statement)


def downgrade() -> None:
    # RESTRICT references require dependents to be removed first.
    for table in (
        "notifications", "irrigation_events", "rule_configurations", "water_balance_records",
        "weather_records", "sensor_readings", "sensor_calibrations", "devices", "soil_profiles",
        "crop_stage_parameters", "crop_cycles", "crops", "fields", "farms", "users",
    ):
        op.execute(f"DROP TABLE {table}")
