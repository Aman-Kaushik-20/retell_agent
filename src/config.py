from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# Pydantic BaseSettings instance for storing secrets from .env
class Settings(BaseSettings):
    retell_api_key: str
    retell_base_url: str = "https://api.retellai.com"
    # Default `from_number` used when POST /calls omits one. Must be a number
    # imported into Retell. Optional — but if you don't set it, every /calls
    # request must include `from_number`.
    retell_from_number: Optional[str] = None

    slack_bot_token: str
    slack_base_url: str = "https://slack.com/api"
    slack_alert_channel: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
