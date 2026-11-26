"""Location search and one coordinate policy shared by weather reads and refreshes."""
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException

from app.models import Farm, Field

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def coordinate_pair(latitude, longitude):
    try:
        lat, lon = Decimal(str(latitude)), Decimal(str(longitude))
        if lat.is_finite() and lon.is_finite() and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (InvalidOperation, TypeError, ValueError):
        pass
    return None


def weather_location(db, field_id):
    field = db.get(Field, field_id)
    if field is None:
        raise HTTPException(404, "Field not found")
    farm = db.get(Farm, field.farm_id)
    pair = coordinate_pair(field.latitude, field.longitude)
    source = "field"
    label = field.field_name
    if pair is None and farm:
        pair = coordinate_pair(farm.latitude, farm.longitude)
        source, label = "farm", farm.location_name or farm.farm_name
    return {
        "field_id": str(field.field_id), "status": "configured" if pair else "missing",
        "latitude": pair[0] if pair else None, "longitude": pair[1] if pair else None,
        "source": source if pair else None, "label": label if pair else None,
        # A named settlement/farm point does not establish the precise field location.
        "approximate": source == "farm" if pair else False,
    }


async def search_locations(query: str, language: str):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(GEOCODING_URL, params={
                "name": query, "count": 10, "language": language, "countryCode": "IN", "format": "json",
            })
            response.raise_for_status()
            payload = response.json()
        rows = payload.get("results", [])
        if not isinstance(rows, list):
            raise ValueError("Invalid location results")
        results = []
        for row in rows:
            pair = coordinate_pair(row.get("latitude"), row.get("longitude"))
            if not pair or not isinstance(row.get("name"), str) or row.get("country_code") != "IN":
                continue
            parts = dict.fromkeys(str(row[key]) for key in ("name", "admin4", "admin3", "admin2", "admin1", "country") if row.get(key))
            results.append({"label": ", ".join(parts)[:255], "latitude": pair[0], "longitude": pair[1]})
        return results
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(503, "Location search is temporarily unavailable") from exc
