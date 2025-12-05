#!/bin/bash

# Скрипт автоматической настройки MCP Agent проекта
# Использование: ./setup_agent.sh

set -e  # Остановка при ошибке

echo "🚀 Начинаю настройку MCP Agent проекта..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "${RED}❌ Python3 не найден. Установите Python 3.8+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "${GREEN}✓ Python ${PYTHON_VERSION} найден${NC}"

# Создание структуры проекта
echo "📁 Создаю структуру проекта..."

mkdir -p src/{agents,tools,core,utils}
mkdir -p tests/{unit,integration}
mkdir -p logs
mkdir -p screenshots
mkdir -p config
mkdir -p docs

echo "${GREEN}✓ Структура создана${NC}"

# Создание .env файла
echo "🔐 Создаю .env конфигурацию..."
cat > .env << 'EOF'
# API Configuration
API_KEY=your_api_key_here
BASE_URL=https://api.aitunnel.ru/v1
MODEL_NAME=gpt-5-nano

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Redis Configuration (optional)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/agent.log

# Browser Configuration
HEADLESS=true
SLOW_MO=50
TIMEOUT=30000

# Security
SECRET_KEY=$(openssl rand -hex 32)
JWT_EXPIRATION=3600
EOF

echo "${YELLOW}⚠️  ВАЖНО: Отредактируйте .env и добавьте ваш API_KEY${NC}"

# Обновленный requirements.txt
echo "📦 Создаю requirements.txt..."
cat > requirements.txt << 'EOF'
# Core Dependencies
aiofiles==25.1.0
annotated-types==0.7.0
anyio==4.12.0
attrs==25.4.0

# HTTP & API
httpx==0.28.1
httpx-sse==0.4.3
certifi==2025.11.12
h11==0.16.0
httpcore==1.0.9
idna==3.11

# MCP & AI
mcp==1.23.1
openai==1.12.0

# Web Server
uvicorn==0.38.0
starlette==0.50.0
sse-starlette==3.0.3

# Browser Automation
playwright==1.40.0
pyee==11.0.1

# Data Validation
pydantic==2.12.5
pydantic-settings==2.12.0
pydantic_core==2.41.5
jsonschema==4.25.1
jsonschema-specifications==2025.9.1

# Security
cryptography==46.0.3
PyJWT==2.10.1
python-dotenv==1.0.0

# HTML Parsing
beautifulsoup4==4.12.3
lxml==5.1.0

# Caching & Storage
redis==5.0.1
aioredis==2.0.1

# Utilities
click==8.3.1
distro==1.9.0
greenlet==3.0.1
python-multipart==0.0.20
tqdm==4.67.1
typing-inspection==0.4.2
typing_extensions==4.15.0

# Development
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
black==23.12.1
flake8==6.1.0
mypy==1.7.1

# Monitoring
prometheus-client==0.19.0
EOF

echo "${GREEN}✓ requirements.txt создан${NC}"

# Создание основного конфига
echo "⚙️  Создаю config.py..."
cat > src/config.py << 'EOF'
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
EOF

echo "${GREEN}✓ config.py создан${NC}"

# Создание утилит
echo "🛠️  Создаю utils..."

# Logger
cat > src/utils/logger.py << 'EOF'
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
EOF

# Cache manager
cat > src/utils/cache.py << 'EOF'
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
EOF

# Retry helper
cat > src/utils/retry.py << 'EOF'
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
EOF

echo "${GREEN}✓ Утилиты созданы${NC}"

# Создание агента
echo "🤖 Создаю adaptive agent..."
cat > src/agents/adaptive_agent.py << 'EOFAGENT'
"""Адаптивный агент с обучением на ошибках"""
from typing import Dict, List, Optional
from src.utils.logger import logger
from src.utils.cache import CacheManager
from src.utils.retry import async_retry

class AdaptiveAgent:
    """Агент, который учится на своих ошибках"""

    def __init__(self):
        self.selector_memory: Dict[str, str] = {}
        self.error_patterns: List[Dict] = []
        self.page_history: List[Dict] = []
        self.cache = CacheManager()
        self.max_history = 100

    async def initialize(self):
        """Инициализация агента"""
        self.selector_memory = await self.cache.load()
        logger.info("Адаптивный агент инициализирован")

    async def process_action(self, session, action: Dict, page_analysis: Dict) -> Dict:
        """Обрабатывает действие с адаптивным подбором селектора"""
        action_type = action.get('type', 'unknown')
        target = action.get('target', '')
        value = action.get('value', '')

        # Проверяем кэш
        memory_key = f"{action_type}:{target}"
        if memory_key in self.selector_memory:
            selector = self.selector_memory[memory_key]
            logger.info(f"🎯 Использую селектор из памяти: {selector}")
            result = await self._try_selector(session, action_type, selector, value)
            if result['success']:
                return result

        # Ищем новые селекторы
        from src.agents.selector_analyzer import AdaptiveSelectorAnalyzer
        selectors = AdaptiveSelectorAnalyzer.find_best_selector_for_action(
            action_type, target, page_analysis
        )

        if not selectors:
            return {
                'success': False,
                'error': f'Не найдены селекторы для {target}',
                'suggestion': 'Вызовите read_page() для анализа'
            }

        # Пробуем селекторы
        for i, selector in enumerate(selectors[:5]):
            logger.info(f"🔄 Попытка {i+1}: {selector}")
            result = await self._try_selector(session, action_type, selector, value)

            if result['success']:
                self.selector_memory[memory_key] = selector
                await self.cache.set(memory_key, selector)
                await self.cache.save()
                return result

        return {
            'success': False,
            'error': f'Все селекторы не сработали',
            'tried_selectors': selectors[:5]
        }

    @async_retry(max_attempts=2, delay=0.5)
    async def _try_selector(self, session, action_type: str, 
                           selector: str, value: str = '') -> Dict:
        """Пробует выполнить действие"""
        try:
            if action_type == 'fill':
                result = await session.call_tool("fill", {
                    "selector": selector,
                    "text": value
                })
            elif action_type == 'click':
                result = await session.call_tool("click", {
                    "selector": selector
                })
            elif action_type == 'navigate':
                result = await session.call_tool("navigate", {
                    "url": value
                })
            else:
                return {'success': False, 'error': f'Неизвестный тип: {action_type}'}

            output = result.content[0].text if result.content else ''

            if "not found" in output.lower() or "error" in output.lower():
                return {'success': False, 'error': output, 'selector': selector}

            return {'success': True, 'output': output, 'selector': selector}

        except Exception as e:
            return {'success': False, 'error': str(e), 'selector': selector}

    def learn_from_error(self, error: str, selector: str, page_analysis: Dict):
        """Учится на ошибках"""
        error_pattern = {
            'error': error,
            'selector': selector,
            'page_stats': page_analysis.get('page_stats', {})
        }
        self.error_patterns.append(error_pattern)

        # Ограничиваем размер истории
        if len(self.error_patterns) > self.max_history:
            self.error_patterns = self.error_patterns[-self.max_history//2:]

        # Проверяем повторяющиеся ошибки
        similar = [e for e in self.error_patterns 
                  if e['selector'] == selector and e['error'] == error]

        if len(similar) > 2:
            logger.warning(f"⚠️ Селектор {selector} часто ошибается")

    async def cleanup(self):
        """Очистка ресурсов"""
        await self.cache.save()
        logger.info("Агент завершил работу")
EOFAGENT

echo "${GREEN}✓ Adaptive agent создан${NC}"

# Создание анализатора селекторов
cat > src/agents/selector_analyzer.py << 'EOFANALYZER'
"""Анализатор селекторов страницы"""
import re
from typing import Dict, List
from bs4 import BeautifulSoup
from src.utils.logger import logger

class AdaptiveSelectorAnalyzer:
    """Анализирует HTML и находит оптимальные селекторы"""

    @staticmethod
    async def analyze_page_structure(page_text: str) -> Dict:
        """Анализ структуры страницы"""
        analysis = {
            'input_fields': [],
            'buttons': [],
            'links': [],
            'detected_frameworks': [],
            'page_stats': {}
        }

        try:
            soup = BeautifulSoup(page_text, 'lxml')
        except:
            soup = BeautifulSoup(page_text, 'html.parser')

        # Определение фреймворков
        frameworks = {
            'Angular': ['ng-', 'mat-', 'formcontrolname', 'cdk-'],
            'React': ['data-react', 'react-', 'className='],
            'Vue': ['v-', 'vue-', '__vue__'],
        }

        page_lower = page_text.lower()
        for framework, markers in frameworks.items():
            if any(marker in page_lower for marker in markers):
                analysis['detected_frameworks'].append(framework)

        # Анализ input полей
        for input_tag in soup.find_all(['input', 'textarea']):
            attrs = input_tag.attrs
            selectors = AdaptiveSelectorAnalyzer._generate_selectors_from_attrs(attrs)

            if selectors:
                analysis['input_fields'].append({
                    'tag': input_tag.name,
                    'attributes': attrs,
                    'selector_suggestions': selectors
                })

        # Анализ кнопок
        for button in soup.find_all(['button', 'a']):
            text = button.get_text(strip=True)
            if text and len(text) > 1:
                analysis['buttons'].append({
                    'text': text,
                    'selector': f'text="{text}"',
                    'tag': button.name
                })

        analysis['page_stats'] = {
            'total_inputs': len(analysis['input_fields']),
            'total_buttons': len(analysis['buttons']),
            'frameworks': list(set(analysis['detected_frameworks']))
        }

        logger.info(f"Анализ завершен: {analysis['page_stats']}")
        return analysis

    @staticmethod
    def _generate_selectors_from_attrs(attrs: Dict) -> List[str]:
        """Генерирует селекторы из атрибутов"""
        selectors = []

        priority_attrs = [
            'data-cy', 'data-testid', 'data-qa', 'data-test',
            'formcontrolname', 'name', 'id', 'placeholder',
            'aria-label', 'type'
        ]

        for attr_name in priority_attrs:
            value = attrs.get(attr_name)
            if value:
                if attr_name.startswith('data-'):
                    selectors.append(f'[{attr_name}="{value}"]')
                elif attr_name == 'formcontrolname':
                    selectors.append(f'[formcontrolname="{value}"]')
                    selectors.append(f'input[formcontrolname="{value}"]')
                elif attr_name == 'name':
                    selectors.append(f'[name="{value}"]')
                elif attr_name == 'id':
                    selectors.append(f'#{value}')

        return selectors[:5]

    @staticmethod
    def find_best_selector_for_action(action_type: str, target: str,
                                     page_analysis: Dict) -> List[str]:
        """Находит лучшие селекторы для действия"""
        suggestions = []
        target_lower = target.lower()

        if action_type in ['fill', 'type']:
            for field in page_analysis.get('input_fields', []):
                score = 0
                attrs = field.get('attributes', {})

                for attr_value in attrs.values():
                    if target_lower in str(attr_value).lower():
                        score += 3

                if score > 0 and 'selector_suggestions' in field:
                    suggestions.extend(field['selector_suggestions'])

        elif action_type in ['click', 'press']:
            for button in page_analysis.get('buttons', []):
                button_text = button.get('text', '').lower()
                if target_lower in button_text:
                    suggestions.append(button['selector'])

        # Убираем дубликаты
        return list(dict.fromkeys(suggestions))[:5]
EOFANALYZER

echo "${GREEN}✓ Selector analyzer создан${NC}"

# Создание MCP клиента
cat > src/core/mcp_client.py << 'EOFMCP'
"""MCP клиент для взаимодействия с серверами"""
import asyncio
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from src.config import get_settings
from src.utils.logger import logger

class MCPClient:
    """Клиент для работы с MCP серверами"""

    def __init__(self):
        self.settings = get_settings()
        self.session: ClientSession = None
        self.http_client: httpx.AsyncClient = None

    async def connect(self, server_url: str):
        """Подключение к MCP серверу"""
        try:
            self.http_client = httpx.AsyncClient(timeout=30.0)

            async with sse_client(server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    await session.initialize()
                    logger.info(f"Подключен к MCP серверу: {server_url}")

                    # Список доступных инструментов
                    tools = await session.list_tools()
                    logger.info(f"Доступно инструментов: {len(tools.tools)}")

                    return session
        except Exception as e:
            logger.error(f"Ошибка подключения к MCP: {e}")
            raise

    async def disconnect(self):
        """Отключение от сервера"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Отключен от MCP сервера")
EOFMCP

echo "${GREEN}✓ MCP client создан${NC}"

# Создание main.py
cat > src/main.py << 'EOFMAIN'
"""Главная точка входа приложения"""
import asyncio
from src.agents.adaptive_agent import AdaptiveAgent
from src.agents.selector_analyzer import AdaptiveSelectorAnalyzer
from src.core.mcp_client import MCPClient
from src.config import get_settings
from src.utils.logger import logger

async def main():
    """Главная функция"""
    settings = get_settings()
    logger.info("🚀 Запуск MCP Agent...")

    # Инициализация
    agent = AdaptiveAgent()
    await agent.initialize()

    mcp_client = MCPClient()

    try:
        # Ваша логика здесь
        logger.info("Агент готов к работе")

        # Пример использования
        # session = await mcp_client.connect("http://localhost:3000")
        # result = await agent.process_action(session, {...}, {...})

    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await agent.cleanup()
        await mcp_client.disconnect()
        logger.info("Завершение работы")

if __name__ == "__main__":
    asyncio.run(main())
EOFMAIN

echo "${GREEN}✓ main.py создан${NC}"

# Создание тестов
echo "🧪 Создаю тесты..."
cat > tests/unit/test_selector_analyzer.py << 'EOFTEST'
"""Тесты для анализатора селекторов"""
import pytest
from src.agents.selector_analyzer import AdaptiveSelectorAnalyzer

@pytest.mark.asyncio
async def test_analyze_angular_page():
    """Тест анализа Angular страницы"""
    html = """
    <input formcontrolname="email" type="email" placeholder="Email">
    <button type="submit">Войти</button>
    """

    analysis = await AdaptiveSelectorAnalyzer.analyze_page_structure(html)

    assert 'Angular' in analysis['detected_frameworks']
    assert analysis['page_stats']['total_inputs'] > 0
    assert analysis['page_stats']['total_buttons'] > 0

@pytest.mark.asyncio
async def test_find_email_selectors():
    """Тест поиска селекторов для email"""
    page_analysis = {
        'input_fields': [{
            'attributes': {'formcontrolname': 'email', 'type': 'email'},
            'selector_suggestions': ['[formcontrolname="email"]']
        }]
    }

    selectors = AdaptiveSelectorAnalyzer.find_best_selector_for_action(
        'fill', 'email', page_analysis
    )

    assert len(selectors) > 0
    assert any('email' in s for s in selectors)
EOFTEST

cat > tests/conftest.py << 'EOFCONF'
"""Конфигурация pytest"""
import pytest
import asyncio

@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
EOFCONF

echo "${GREEN}✓ Тесты созданы${NC}"

# Создание __init__.py файлов
touch src/__init__.py
touch src/agents/__init__.py
touch src/tools/__init__.py
touch src/core/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py

# Создание .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Logs & Cache
logs/
*.log
.cache/
screenshots/
*.png

# Environment
.env
.env.local

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
EOF

# Создание README
cat > README.md << 'EOF'
# MCP Adaptive Agent

Интеллектуальный агент для автоматизации веб-тестирования с адаптивным подбором селекторов.

## Возможности

- 🤖 Адаптивный подбор селекторов
- 🧠 Обучение на ошибках
- 💾 Персистентный кэш селекторов
- 🔍 Автоматический анализ Angular/React/Vue
- 🔄 Автоматические повторные попытки
- 📊 Подробное логирование

## Быстрый старт

1. Настройте окружение:
```bash
./setup_agent.sh
```

2. Активируйте виртуальное окружение:
```bash
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

3. Отредактируйте .env и добавьте API_KEY

4. Запустите:
```bash
python -m src.main
```

## Тестирование

```bash
pytest tests/ -v
```

## Структура проекта

```
.
├── src/
│   ├── agents/         # Агенты и анализаторы
│   ├── core/           # Ядро приложения
│   ├── tools/          # MCP инструменты
│   └── utils/          # Утилиты
├── tests/              # Тесты
├── logs/               # Логи
└── config/             # Конфигурация
```

## Лицензия

MIT
EOF

# Создание виртуального окружения
echo "🐍 Создаю виртуальное окружение..."
python3 -m venv venv

echo "${GREEN}✓ Виртуальное окружение создано${NC}"

# Установка зависимостей
echo "📥 Установка зависимостей..."
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

# Установка Playwright browsers
echo "🌐 Устанавливаю Playwright browsers..."
playwright install chromium

echo "${GREEN}✓ Зависимости установлены${NC}"

# Запуск тестов
echo "🧪 Запуск тестов..."
pytest tests/ -v || echo "${YELLOW}⚠️  Некоторые тесты не прошли${NC}"

# Итоговая информация
echo ""
echo "${GREEN}════════════════════════════════════════${NC}"
echo "${GREEN}✅ Проект успешно настроен!${NC}"
echo "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "📋 Следующие шаги:"
echo "1. ${YELLOW}Отредактируйте .env и добавьте API_KEY${NC}"
echo "2. Активируйте окружение: ${GREEN}source venv/bin/activate${NC}"
echo "3. Запустите: ${GREEN}python -m src.main${NC}"
echo ""
echo "📚 Документация: README.md"
echo "🧪 Тесты: ${GREEN}pytest tests/ -v${NC}"
echo "📊 Логи: logs/"
echo ""
echo "${GREEN}Успехов! 🚀${NC}"
