from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="dbridge_", extra="ignore")
    logging_level: str = "INFO"
    max_rows: int = 100
    cache_ttl_seconds: int = 60


settings = Settings()
