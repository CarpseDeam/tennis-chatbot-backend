# config.py
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Defines the application's configuration settings.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- Required API Keys ---
    google_api_key: str
    tennis_api_key: str
    admin_api_key: str

    # --- API Service Hosts ---
    tennis_api_host: str

    # --- Custom Scraper Service URL ---
    # The base URL for the custom Tenipo scraper service.
    tenipo_api_base_url: Optional[HttpUrl] = None

    # --- General Settings ---
    log_level: str = "INFO"


try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Failed to load application settings. Error: {e}")
    print("Please ensure a valid .env file exists and contains all required variables.")
    raise