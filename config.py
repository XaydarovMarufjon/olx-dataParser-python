from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str
    database_name: str = "olx_tracker"
    keyword_file: str = "keywords.txt"

    # scraping sozlamalari
    request_delay_min: float = 8.0     # soniya
    request_delay_max: float = 25.0
    max_pages_per_keyword: int = 15    # bir keyword uchun maks sahifa
    headless: bool = False              # True = ko‘rinmas, False = brauzer ochiq

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()