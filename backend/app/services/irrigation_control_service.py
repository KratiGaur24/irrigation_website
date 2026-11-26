"""Manual sessions serialized by a field-row lock; see MANUAL_IRRIGATION_PHASE1.md."""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.models import Field, Device, CropCycle, SensorReading, IrrigationEvent
from app.schemas_irrigation import IrrigationEventRead, ControlStatus, EmergencyResult
from app.services.device_control_service import Acknowledgement

logger = logging.getLogger(__name__)
CONTROLLER_TYPES = {'irrigation_controller', 'pump_controller'}


def utcnow():
    return datetime.now(timezone.utc)


def field_exists(db, field_id, lock=False):
    query = select(Field).where(Field.field_id == field_id)
    field = db.scalar(query.with_for_update() if lock else query)
    if field is None:
        raise HTTPException(404, 'Field not found')
    return field


def open_event(db, field_id):
    return db.scalar(select(IrrigationEvent).where(IrrigationEvent.field_id == field_id, IrrigationEvent.ended_at.is_(None)))


def controller(db, field_id, control):
    devices = list(db.scalars(select(Device).where(Device.field_id == field_id)))
    candidates = [d for d in devices if d.device_type.lower() in CONTROLLER_TYPES]
    if not candidates and control.mode == 'simulated' and len(devices) == 1:
        candidates = devices
    if len(candidates) != 1:
        raise HTTPException(409, 'Configure exactly one irrigation controller for this field.')
    return candidates[0]


def availability(db, field_id, control):
    field_exists(db, field_id)
    event = open_event(db, field_id)
    try:
        device = db.get(Device, event.device_id) if event and event.device_id else controller(db, field_id, control)
    except HTTPException as exc:
        return ControlStatus(control_mode=control.mode, available=False, start_available=False, message=str(exc.detail))
    if device is None:
        return ControlStatus(control_mode=control.mode, available=False, start_available=False, message='Session controller unavailable.')
    usable = device.status.lower() in {'online', 'active', 'connected'} and device.last_seen_at is not None
    available = control.available and (not event or event.control_mode == control.mode)
    message = ('Simulation mode: no physical pump is operated; device availability checks are relaxed.'
               if control.mode == 'simulated' else 'ESP32 command transport is not configured.')
    if event and event.control_mode != control.mode:
        message = 'Session control mode differs from current configuration. Restore its control path to stop safely.'
    elif control.mode == 'hardware' and not usable:
        message = 'Controller is unavailable or has not reported. Hardware transport is not configured.'
    return ControlStatus(control_mode=control.mode, available=available,
                         start_available=available and event is None and (usable or control.mode == 'simulated'),
                         device_id=device.device_id, device_status=device.status, last_seen_at=device.last_seen_at, message=message)


def latest_reading(db, field_id, at, device_id=None, column=None, after=None):
    query = select(SensorReading).where(SensorReading.field_id == field_id,
                                       SensorReading.sensor_valid.is_(True), SensorReading.recorded_at <= at)
    if device_id is not None:
        query = query.where(SensorReading.device_id == device_id)
    if column is not None:
        query = query.where(column.is_not(None))
    if after is not None:
        query = query.where(SensorReading.recorded_at > after)
    return db.scalar(query.order_by(SensorReading.recorded_at.desc(), SensorReading.reading_id.desc()).limit(1))


def measured_volume(db, event, at):
    baseline = db.get(SensorReading, event.start_reading_id) if event.start_reading_id else None
    if baseline is None or not baseline.sensor_valid or baseline.device_id != event.device_id or baseline.cumulative_water_litres is None:
        return None, None, None
    rows = db.scalars(select(SensorReading).where(
        SensorReading.device_id == event.device_id, SensorReading.field_id == event.field_id,
        SensorReading.recorded_at >= baseline.recorded_at, SensorReading.recorded_at <= at,
        SensorReading.cumulative_water_litres.is_not(None),
    ).order_by(SensorReading.recorded_at, SensorReading.reading_id))
    previous, final = baseline.cumulative_water_litres, None
    for reading in rows:
        if reading.recorded_at == baseline.recorded_at and reading.reading_id <= baseline.reading_id:
            continue
        if not reading.sensor_valid or reading.cumulative_water_litres < previous:
            return None, baseline.recorded_at, None
        previous = reading.cumulative_water_litres
        if reading.recorded_at > event.started_at:
            final = reading
    if final is None:
        return None, baseline.recorded_at, None
    volume = (final.cumulative_water_litres - baseline.cumulative_water_litres).quantize(Decimal('0.01'))
    return (volume if volume <= Decimal('99999999.99') else None), baseline.recorded_at, final.recorded_at


def event_view(db, event):
    result = IrrigationEventRead.model_validate(event)
    if event.ended_at is None:
        now = utcnow()
        result.current_duration_seconds = max(0, int((now - event.started_at).total_seconds()))
        reading = latest_reading(db, event.field_id, now, event.device_id)
        if reading:
            result.current_moisture_pct, result.current_flow_rate_lpm = reading.soil_moisture_pct, reading.flow_rate_lpm
            result.measurement_time = reading.recorded_at
        result.current_water_used_litres, result.volume_baseline_time, result.volume_measurement_time = measured_volume(db, event, now)
    return result


def issue(control, action, device, event=None):
    # Never allow a simulated acknowledgement to close a hardware/legacy event.
    if event and event.control_mode != control.mode:
        return Acknowledgement(False, control.mode, 'Session control mode mismatch. Pump-off is unconfirmed.')
    try:
        ack = getattr(control, action)(device, event.event_id if event else None)
        if ack.control_mode != control.mode:
            return Acknowledgement(False, control.mode, 'Command acknowledgement mode mismatch.')
        return ack
    except Exception:
        logger.exception('Pump command outcome unknown action=%s device=%s', action, device.device_id)
        return Acknowledgement(False, control.mode, 'Command acknowledgement unavailable. Pump state is unknown.')


def start(db, field_id, control):
    device, acknowledged, command_attempted = None, False, False
    try:
        field_exists(db, field_id, lock=True)
        if open_event(db, field_id):
            raise HTTPException(409, 'An open irrigation session already exists. Refresh its state before continuing.')
        device = controller(db, field_id, control)
        if not control.available:
            raise HTTPException(503, 'Hardware control transport is not configured. No pump command was sent.')
        if control.mode != 'simulated' and (device.status.lower() not in {'online', 'active', 'connected'} or device.last_seen_at is None):
            raise HTTPException(409, 'Controller unavailable or has not reported. Start rejected.')
        now = utcnow()
        moisture = latest_reading(db, field_id, now, column=SensorReading.soil_moisture_pct)
        meter = latest_reading(db, field_id, now, device.device_id, SensorReading.cumulative_water_litres)
        cycle = db.scalar(select(CropCycle).where(CropCycle.field_id == field_id, CropCycle.status == 'active').order_by(CropCycle.created_at.desc()).limit(1))
        event = IrrigationEvent(field_id=field_id, device_id=device.device_id, crop_cycle_id=cycle.crop_cycle_id if cycle else None,
                                mode='MANUAL', status='started', control_mode=control.mode, started_at=now,
                                trigger_reason='manual farmer request', moisture_before_pct=moisture.soil_moisture_pct if moisture else None,
                                start_reading_id=meter.reading_id if meter else None)
        db.add(event)
        db.flush()  # Detect database constraints before sending any command.
        command_attempted = True
        ack = issue(control, 'start_pump', device, event)
        acknowledged = ack.acknowledged
        event.command_acknowledged = acknowledged
        if not acknowledged:
            event.status = 'failed'
            event.fault_code = 'START_REJECTED' if ack.definitive_rejection else 'START_UNCONFIRMED'
            if ack.definitive_rejection:
                event.ended_at = utcnow()
                event.duration_seconds = max(0, int((event.ended_at - now).total_seconds()))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        if command_attempted and device:
            off = issue(control, 'emergency_stop', device)
            logger.error('Database failure after START; emergency-off acknowledged=%s mode=%s', off.acknowledged, off.control_mode)
        raise HTTPException(503, 'Session could not be saved. Emergency-off was attempted if a start command was sent; verify controller state before retrying.')
    if not acknowledged:
        raise HTTPException(502, 'Start was not acknowledged. Refresh session state; an uncertain command requires a stop retry.')
    return event_view(db, event)


def close_event(db, event, status, emergency=False):
    now = utcnow()
    event.ended_at = now
    event.duration_seconds = max(0, int((now - event.started_at).total_seconds()))
    moisture = latest_reading(db, event.field_id, now, column=SensorReading.soil_moisture_pct, after=event.started_at)
    event.moisture_after_pct = moisture.soil_moisture_pct if moisture else None
    event.water_used_litres = measured_volume(db, event, now)[0]
    event.status, event.command_acknowledged = status, True
    event.fault_code = 'MANUAL_EMERGENCY_STOP' if emergency else None
    if emergency:
        event.trigger_reason = 'manual emergency stop'


def stop(db, field_id, control, emergency=False):
    try:
        field_exists(db, field_id, lock=True)
        event = open_event(db, field_id)
        if event is None and not emergency:
            raise HTTPException(409, 'No active irrigation session.')
        device = db.get(Device, event.device_id) if event and event.device_id else controller(db, field_id, control)
        if device is None:
            raise HTTPException(409, 'Session controller unavailable.')
        # Independent emergency command: no telemetry or availability check first.
        ack = issue(control, 'emergency_stop' if emergency else 'stop_pump', device, event)
        if event:
            if ack.acknowledged:
                close_event(db, event, 'stopped' if emergency else 'completed', emergency)
            else:
                event.status, event.command_acknowledged = 'failed', False
                event.fault_code = 'EMERGENCY_OFF_UNCONFIRMED' if emergency else 'STOP_UNCONFIRMED'
                if emergency:
                    event.trigger_reason = 'manual emergency stop'
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, 'Pump-off outcome could not be saved. Refresh and retry Emergency Stop; do not assume the pump is off.')
    if emergency:
        return EmergencyResult(acknowledged=ack.acknowledged, control_mode=ack.control_mode, message=ack.message,
                               session=event_view(db, event) if event else None)
    if not ack.acknowledged:
        raise HTTPException(502, 'Pump-off was not acknowledged. Session remains open for retry; do not assume the pump is off.')
    return event_view(db, event)
