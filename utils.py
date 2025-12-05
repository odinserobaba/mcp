import os
import httpx
from openai import AsyncOpenAI

# --- КОНФИГУРАЦИЯ ---
API_KEY = os.getenv("OPENAI_API_KEY", "sk-aitunnel-oYUy5dzTcsFEM8ippJCtlQ8WaEYWmHL9")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.aitunnel.ru/v1")
MODEL_NAME = "gpt-5-nano"
SERVER_URL = "http://localhost:8000/sse"

def get_llm_client():
    http_client = httpx.AsyncClient()
    return AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client)

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_AGENT = """
Ты — эксперт по автоматизации (QA Automation Engineer).
Твоя цель — выполнить задачу пользователя, используя инструменты браузера.
1. Сначала перейди на сайт (`navigate`).
2. Если нужно найти элемент, используй селекторы по тексту (`text=...`) или атрибутам.
3. Если открывается новое окно — учитывай это.
"""

PROMPT_GENERATE_TEST = """
Ты — Senior SDET. Напиши валидный тест Playwright на Python (async).

ВХОДНЫЕ ДАННЫЕ (История действий):
{json_str}

ТРЕБОВАНИЯ:
1. Используй ТОЛЬКО асинхронный API: `async with async_playwright() as p`.
2. `browser = await p.chromium.launch(headless=False, slow_mo=1000)`.
3. Если действие `click`, используй `await page.click("...")`.
4. Обработка POPUP/Вкладок:
   Если в логе есть `new_window_opened` или `is_popup: true` ПОСЛЕ клика:
async with page.expect_popup() as popup_info:
await page.click("селектор")
page1 = await popup_info.value
await page1.wait_for_load_state()

text
Далее работай с `page1`.
5. Верни ТОЛЬКО код, без markdown.
"""