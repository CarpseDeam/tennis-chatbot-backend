# config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Defines the application's configuration settings.
    This has been simplified to only include settings required by the current application.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- Required API Keys ---
    google_api_key: str  # For the Gemini LLM in the chat endpoint
    admin_api_key: str   # For securing any admin/debug endpoints (good practice)

    # --- Redis Configuration ---
    # Railway will provide this URL automatically in production.
    # For local development, it defaults to a standard local Redis instance.
    redis_url: str = "redis://localhost:6379"

    # --- General Settings ---
    log_level: str = "INFO"


try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Failed to load application settings. Error: {e}")
    print("Please ensure a valid .env file exists and contains all required variables.")
    raise