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
