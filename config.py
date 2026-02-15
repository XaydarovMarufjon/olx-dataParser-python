from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str
    database_name: str = "olx_tracker"
    ads_collection: str = "ads"
    keyword_file: str = "keywords.txt"

    # scraping sozlamalari
    request_delay_min: float = 8.0  # soniya
    request_delay_max: float = 25.0
    max_pages_per_keyword: int = 15
    headless: bool = False

    # playwright timeouts (ms)
    goto_timeout: int = 60_000
    selector_timeout: int = 30_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
