from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Field, WeatherRecord
from app.services.location_service import weather_location

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ",".join(("temperature_2m", "relative_humidity_2m", "precipitation", "rain", "precipitation_probability", "wind_speed_10m", "shortwave_radiation", "et0_fao_evapotranspiration", "weather_code"))
DAILY = ",".join(("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "rain_sum", "precipitation_probability_max", "shortwave_radiation_sum", "et0_fao_evapotranspiration", "weather_code"))


def _local_to_utc(value: str, timezone_name: str) -> datetime:
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Provider returned an unknown timezone") from exc
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_zone)
    return parsed.astimezone(timezone.utc)


def _series(data: dict, name: str, index: int):
    values = data.get(name)
    if values is None:
        return None
    if not isinstance(values, list) or index >= len(values):
        raise ValueError(f"Invalid provider series: {name}")
    return values[index]


async def refresh_field_weather(db: Session, field_id) -> dict:
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(404, "Field not found")
    location = weather_location(db, field_id)
    if location['status'] != 'configured':
        raise HTTPException(422, "Set your farm location to view weather forecasts.")
    params = {
        "latitude": float(location['latitude']), "longitude": float(location['longitude']),
        "hourly": HOURLY, "daily": DAILY, "timezone": "auto",
        "temperature_unit": "celsius", "wind_speed_unit": "ms", "precipitation_unit": "mm",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        hourly = payload["hourly"]
        times = hourly["time"]
        if times == []:
            raise HTTPException(404, "Forecast unavailable for the selected location")
        if not isinstance(times, list):
            raise ValueError("Missing hourly timestamps")
        for name in ("temperature_2m", "relative_humidity_2m", "precipitation", "precipitation_probability", "wind_speed_10m", "shortwave_radiation", "et0_fao_evapotranspiration", "weather_code"):
            values = hourly.get(name)
            if not isinstance(values, list) or len(values) != len(times):
                raise ValueError(f"Invalid provider series: {name}")
        if not any(value is not None for name in ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m") for value in hourly[name]):
            raise HTTPException(404, "Forecast unavailable for the selected location")
        daily = payload.get("daily", {})
        daily_times = daily.get("time", [])
        if not isinstance(daily_times, list):
            raise ValueError("Invalid daily timestamps")
        for name in ("temperature_2m_max", "temperature_2m_min"):
            values = daily.get(name)
            if not isinstance(values, list) or len(values) != len(daily_times):
                raise ValueError(f"Invalid provider series: {name}")
        day_index = {d: i for i, d in enumerate(daily_times)}
        fetched_at = datetime.now(timezone.utc)
        records = []
        for i, local_time in enumerate(times):
            if not isinstance(local_time, str):
                raise ValueError("Invalid hourly timestamp")
            date_key = local_time[:10]
            di = day_index.get(date_key)
            radiation_wm2 = _series(hourly, "shortwave_radiation", i)
            row = WeatherRecord(
                field_id=field.field_id,
                request_latitude=location['latitude'], request_longitude=location['longitude'],
                forecast_time=_local_to_utc(local_time, payload["timezone"]),
                fetched_at=fetched_at, source="open-meteo",
                temperature_c=_series(hourly, "temperature_2m", i),
                humidity_pct=_series(hourly, "relative_humidity_2m", i),
                wind_speed_mps=_series(hourly, "wind_speed_10m", i),
                # Open-Meteo hourly radiation is mean W/m² over the preceding hour.
                # W/m² * 3600 seconds / 1,000,000 = MJ/m² for that hour.
                solar_radiation_mj_m2=(float(radiation_wm2) * 3600 / 1_000_000) if radiation_wm2 is not None else None,
                rain_probability_pct=_series(hourly, "precipitation_probability", i),
                forecast_rainfall_mm=_series(hourly, "precipitation", i),
                eto_mm=_series(hourly, "et0_fao_evapotranspiration", i),
                actual_rainfall_mm=None,
                temperature_min_c=_series(daily, "temperature_2m_min", di) if di is not None else None,
                temperature_max_c=_series(daily, "temperature_2m_max", di) if di is not None else None,
            )
            records.append(row)
        if not records:
            raise ValueError("Provider returned no hourly forecast records")
    except httpx.TimeoutException as exc:
        raise HTTPException(503, "Open-Meteo request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, "Open-Meteo provider returned an error") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Could not reach Open-Meteo") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Open-Meteo returned an invalid weather payload") from exc

    try:
        db.add_all(records)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "Weather records could not be saved") from exc
    return {"field_id": str(field.field_id), "source": "open-meteo", "fetched_at": fetched_at, "records_saved": len(records), "timezone": payload.get("timezone")}
