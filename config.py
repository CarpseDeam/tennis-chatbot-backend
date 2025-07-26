# config.py
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# This will force the variables from your .env file to be used,
# ignoring any conflicting system variables.
load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Defines the application's configuration settings.
    It automatically reads from environment variables or a .env file.
    """
    # Pydantic will automatically look for these environment variables (case-insensitive).
    # The `env_file` setting tells it where to look.
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # --- Required API Keys (use lowercase for python variables) ---
    # The application will fail to start if these are not found in the .env file.
    google_api_key: str
    tennis_api_key: str
    admin_api_key: str

    # --- API Service Hosts ---
    # This setting is now MANDATORY. The application will not start
    # if this environment variable is missing.
    tennis_api_host: str

    # --- General Settings (with a default value) ---
    log_level: str = "INFO"


# Create a single, importable instance of the settings for the app to use.
try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Failed to load application settings. Error: {e}")
    print("Please ensure a valid .env file exists in the project root and contains all required variables (GOOGLE_API_KEY, TENNIS_API_KEY, ADMIN_API_KEY, TENNIS_API_HOST).")
    raise