# config.py
import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional

load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Defines the application's configuration settings.
    Now supports multiple LLM providers and optional web search capabilities.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- LLM Provider Selection ---
    llm_provider: Literal['google', 'deepseek'] = Field(
        default='google',
        description="The LLM provider to use ('google' or 'deepseek')."
    )

    # --- Provider-Specific API Keys ---
    google_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None

    # --- DeepSeek Model Configuration ---
    deepseek_model_name: str = Field(
        default='deepseek-chat',
        description="The DeepSeek model to use (e.g., 'deepseek-chat' or 'deepseek-reasoner')."
    )

    # --- NEW: Google Custom Search API Keys for the Web Search Tool ---
    google_search_api_key: Optional[str] = None
    google_cse_id: Optional[str] = None

    # --- Other Keys & Settings ---
    admin_api_key: str
    redis_url: str

    # --- General Settings ---
    log_level: str = "INFO"


try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Failed to load application settings. Error: {e}")
    print("Please ensure a valid .env file exists and contains all required variables.")
    raise