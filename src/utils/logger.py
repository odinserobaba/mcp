"""Настройка логирования"""
import logging
from pathlib import Path
from datetime import datetime
from src.config import get_settings

def setup_logger(name: str = "mcp_agent") -> logging.Logger:
    """Настраивает логгер с файловым и консольным выводом"""
    settings = get_settings()

    # Создаем директорию для логов
    log_dir = Path(settings.logs_dir)
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level))

    # Файловый handler
    log_file = log_dir / f"{name}_{datetime.now():%Y%m%d}.log"
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    # Консольный handler
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, settings.log_level))

    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

# Глобальный логгер
logger = setup_logger()
