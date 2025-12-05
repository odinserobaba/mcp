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
