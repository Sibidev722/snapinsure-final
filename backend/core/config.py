import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SnapInsure"
    MONGO_URI: str
    DATABASE_NAME: str = "snapinsure"
    
    OPENWEATHER_API_KEY: str | None = None
    MAPS_API_KEY: str | None = None
    NEWS_API_KEY: str | None = None
    MAPBOX_API_KEY: str | None = None
    GNEWS_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    
    class Config:
        env_file = ".env"

settings = Settings()
print("Mongo URI Loaded:", settings.MONGO_URI[:20])
