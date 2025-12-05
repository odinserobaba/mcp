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
