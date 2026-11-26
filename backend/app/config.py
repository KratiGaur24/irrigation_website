from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    database_url: str
    irrigation_control_mode: Literal['simulated', 'hardware'] = 'hardware'
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
