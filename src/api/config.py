from pydantic_settings import BaseSettings, SettingsConfigDict


class HealthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # API
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    LOG_LEVEL: str = "INFO"
    CHECK_TIMEOUT: int = 5

    # PostgreSQL
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    HEALTH_POSTGRES_PORT: int = 5432
    
    HEALTH_POSTGRES_HOST: str = "pd_postgres"
    HEALTH_REDIS_HOST: str = "pd_redis"
    HEALTH_KAFKA_HOST: str = "pd_kafka"
    HEALTH_SPARK_MASTER_HOST: str = "pd_spark_master"
    HEALTH_OCR_HOST: str = "pd_ocr_service"

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    HEALTH_REDIS_PORT: int = 6379

    # Kafka
    KAFKA_BROKER: str
    KAFKA_PORT: int
    HEALTH_KAFKA_PORT: int = 9092

    # Spark
    SPARK_MASTER_HOST: str
    SPARK_MASTER_PORT: int
    HEALTH_SPARK_MASTER_PORT: int = 8080

    # OCR
    OCR_HOST: str
    OCR_PORT: int
    HEALTH_OCR_PORT: int = 8000


settings = HealthSettings()