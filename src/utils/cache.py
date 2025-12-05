"""Менеджер кэша селекторов"""
import json
import aiofiles
from pathlib import Path
from typing import Dict, Optional
from src.config import get_settings
from src.utils.logger import logger

class CacheManager:
    """Управление кэшем селекторов"""

    def __init__(self):
        self.settings = get_settings()
        self.cache_file = Path(self.settings.cache_dir) / "selector_cache.json"
        self.cache_file.parent.mkdir(exist_ok=True)
        self.memory: Dict[str, str] = {}

    async def load(self) -> Dict[str, str]:
        """Загрузить кэш из файла"""
        if not self.cache_file.exists():
            return {}

        try:
            async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                self.memory = json.loads(content)
                logger.info(f"Загружено {len(self.memory)} селекторов из кэша")
                return self.memory
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша: {e}")
            return {}

    async def save(self):
        """Сохранить кэш в файл"""
        try:
            async with aiofiles.open(self.cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.memory, ensure_ascii=False, indent=2))
            logger.info(f"Сохранено {len(self.memory)} селекторов в кэш")
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")

    def get(self, key: str) -> Optional[str]:
        """Получить селектор из кэша"""
        return self.memory.get(key)

    def set(self, key: str, value: str):
        """Сохранить селектор в кэш"""
        self.memory[key] = value

    def clear(self):
        """Очистить кэш"""
        self.memory = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
