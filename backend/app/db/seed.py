"""Create minimal demo entities; no scientific or calibration values are seeded."""
import hashlib
import os
import secrets
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Crop, CropCycle, Device, Farm, Field, User
from app.db.seed_agronomic import seed_catalogue


def make_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def seed() -> None:
    email = os.environ.get("DEMO_USER_EMAIL", "demo@example.test")
    password = os.environ.get("DEMO_USER_PASSWORD")
    if not password:
        raise RuntimeError("Set DEMO_USER_PASSWORD in the environment before seeding.")

    with SessionLocal.begin() as session:
        seed_catalogue(session)
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(name="Demo Farmer", email=email, password_hash=make_password_hash(password))
            session.add(user)
            session.flush()
        farm = session.scalar(select(Farm).where(Farm.user_id == user.user_id, Farm.farm_name == "Demo Farm"))
        if farm is None:
            farm = Farm(user_id=user.user_id, farm_name="Demo Farm")
            session.add(farm)
            session.flush()
        field = session.scalar(select(Field).where(Field.farm_id == farm.farm_id, Field.field_name == "Demo Field"))
        if field is None:
            field = Field(farm_id=farm.farm_id, field_name="Demo Field")
            session.add(field)
            session.flush()
        crop = session.scalar(select(Crop).where(Crop.crop_name == "Wheat"))
        if crop is None:
            crop = Crop(crop_name="Wheat")
            session.add(crop)
            session.flush()
        cycle = session.scalar(select(CropCycle).where(CropCycle.field_id == field.field_id, CropCycle.status == "active"))
        if cycle is None:
            session.add(CropCycle(field_id=field.field_id, crop_id=crop.crop_id, sowing_date=date.today(), status="active"))
        device = session.scalar(select(Device).where(Device.device_code == "ESP32-DEMO-001"))
        if device is None:
            session.add(Device(field_id=field.field_id, device_code="ESP32-DEMO-001", device_type="ESP32", status="not_configured"))


if __name__ == "__main__":
    seed()
