from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAI / LangChain
    openai_api_key: Optional[str] = None

    # Langfuse
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None

    # Databases
    database_url: Optional[str] = None
    ps_db_url: Optional[str] = None

    # PeopleSoft credentials and endpoints
    peoplesoft_username: Optional[str] = None
    peoplesoft_password: Optional[str] = None
    peoplesoft_env: Optional[str] = None
    peoplesoft_test_env: Optional[str] = None
    peoplesoft_env_hcm: Optional[str] = None
    peoplesoft_test_env_hcm: Optional[str] = None

    # OCR
    tesseract_cmd: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings loader. Use get_settings() once and reuse the object.
    """
    return Settings()
