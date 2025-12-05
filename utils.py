"""Утилиты для MCP клиента"""
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.aitunnel.ru/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000/sse")

# Промпт для генерации тестов
PROMPT_GENERATE_TEST = """
Ты — Senior SDET эксперт по Playwright.
На основе записанных действий пользователя создай полный автотест на Python + Playwright.

Записанные действия (JSON):
{json_str}

Требования к коду:
1. Используй async/await
2. Добавь явные ожидания элементов
3. Используй надежные селекторы (data-*, id, formcontrolname)
4. Добавь логирование действий
5. Обработай ошибки
6. Добавь скриншоты при падении
7. Используй Page Object паттерн если нужно

Верни ТОЛЬКО Python код без пояснений.
"""

def get_llm_client():
    """Получить клиент OpenAI"""
    return AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
