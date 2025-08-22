# config.py
import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Defines the application's configuration settings.
    This has been simplified to only include settings required by the current application.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- LLM Provider Selection ---
    llm_provider: Literal['google', 'deepseek'] = Field(
        default='google',
        description="The LLM provider to use ('google' or 'deepseek')."
    )

    # --- Provider-Specific API Keys ---
    google_api_key: str | None = None
    deepseek_api_key: str | None = None

    # --- DeepSeek Model Configuration ---
    deepseek_model_name: str = Field(
        default='deepseek-chat',
        description="The DeepSeek model to use (e.g., 'deepseek-chat' or 'deepseek-reasoner')."
    )

    # --- Other Keys & Settings ---
    admin_api_key: str

    # --- Redis Configuration ---
    # This is now a REQUIRED field. The app will not start without the
    # REDIS_URL environment variable from Railway or your .env file.
    redis_url: str

    # --- General Settings ---
    log_level: str = "INFO"


try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Failed to load application settings. Error: {e}")
    print("Please ensure a valid .env file exists and contains all required variables.")
    raise