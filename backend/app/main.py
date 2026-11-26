from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers import crop_cycles, crops, devices, farms, fields, sensor_readings, soil_profiles, weather, irrigation, agronomic_profiles, locations

app = FastAPI(title="Smart Irrigation API", version="2.0.0")

cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

for api_router in (crops.router, farms.router, fields.router, crop_cycles.router, devices.router, soil_profiles.router, sensor_readings.router, weather.router, irrigation.router, agronomic_profiles.router, locations.router):
    app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

