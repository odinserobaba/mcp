"""Конфигурация приложения"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Настройки приложения"""

    # API Settings
    api_key: str
    base_url: str = "https://api.aitunnel.ru/v1"
    model_name: str = "gpt-5-nano"

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Redis Settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_enabled: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/agent.log"

    # Browser Settings
    headless: bool = True
    slow_mo: int = 50
    timeout: int = 30000

    # Security
    secret_key: str
    jwt_expiration: int = 3600

    # Paths
    screenshots_dir: str = "screenshots"
    logs_dir: str = "logs"
    cache_dir: str = ".cache"

    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Получить настройки"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
