"""Утилиты для повторных попыток"""
import asyncio
from typing import Callable, Any
from functools import wraps
from src.utils.logger import logger

def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Декоратор для повторных попыток async функций"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"Попытка {attempt + 1}/{max_attempts} не удалась: {e}"
                    )

                    if attempt < max_attempts - 1:
                        logger.info(f"Повтор через {current_delay}с...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            logger.error(f"Все {max_attempts} попытки исчерпаны")
            raise last_exception

        return wrapper
    return decorator
