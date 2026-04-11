from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # APP
    APP_NAME: str
    APP_ENV: str
    LOG_LEVEL: str

    # POSTGRESQL
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SSLMODE: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={self.POSTGRES_SSLMODE}"
        )

    # REDIS
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_DB: int

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # KAFKA
    KAFKA_BROKER: str
    KAFKA_PORT: int
    KAFKA_TOPIC_RAW_FILES: str
    KAFKA_TOPIC_EXTRACTED_TEXT: str
    KAFKA_TOPIC_RESULTS: str

    @property
    def kafka_bootstrap_servers(self) -> str:
        return f"{self.KAFKA_BROKER}:{self.KAFKA_PORT}"

    # SCANNER
    SCAN_ROOT_PATH: str
    SCAN_MAX_FILE_SIZE_MB: int
    SCAN_SUPPORTED_EXTENSIONS: list[str] = [
        ".txt", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".html",
        ".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".tmp"
    ]

    # OCR SERVICE
    OCR_SERVICE_HOST: str
    OCR_PORT: int
    OCR_TESSERACT_LANGS: str
    OCR_MAX_IMAGE_SIZE_MB: int


settings = Settings()
