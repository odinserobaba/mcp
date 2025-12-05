#!/usr/bin/env python3
"""
MCP Server для записи действий браузера
Исправленная версия без ошибки NoneType
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from sse_starlette.sse import EventSourceResponse

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp import types

import uvicorn
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальное состояние
class AppState:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.recording = False
        self.timeline: List[Dict] = []
        self.sessions: Dict[str, Dict] = {}

app_state = AppState()

# MCP Server
mcp_server = Server("browser-recorder")

@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Список доступных инструментов"""
    return [
        types.Tool(
            name="navigate",
            description="Переход на URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL для навигации"}
                },
                "required": ["url"]
            }
        ),
        types.Tool(
            name="click",
            description="Клик по элементу",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS селектор"}
                },
                "required": ["selector"]
            }
        ),
        types.Tool(
            name="fill",
            description="Заполнить поле",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["selector", "text"]
            }
        ),
        types.Tool(
            name="start_recording",
            description="Начать запись действий",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="stop_recording",
            description="Остановить запись",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_timeline",
            description="Получить записанные действия",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="read_page",
            description="Прочитать содержимое страницы",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Обработка вызовов инструментов"""
    try:
        logger.info(f"Tool called: {name} with args: {arguments}")

        # Инициализация браузера если нужно
        if not app_state.page and name != "stop_recording":
            await init_browser()

        # Обработка команд
        if name == "navigate":
            url = arguments["url"]
            await app_state.page.goto(url, wait_until="domcontentloaded")

            if app_state.recording:
                app_state.timeline.append({
                    "action": "navigate",
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "page_url": app_state.page.url
                })

            return [types.TextContent(
                type="text",
                text=f"Navigated to {url}"
            )]

        elif name == "click":
            selector = arguments["selector"]
            await app_state.page.click(selector, timeout=5000)

            if app_state.recording:
                app_state.timeline.append({
                    "action": "click",
                    "selector": selector,
                    "timestamp": datetime.now().isoformat(),
                    "page_url": app_state.page.url
                })

            return [types.TextContent(
                type="text",
                text=f"Clicked on {selector}"
            )]

        elif name == "fill":
            selector = arguments["selector"]
            text = arguments["text"]
            await app_state.page.fill(selector, text, timeout=5000)

            if app_state.recording:
                app_state.timeline.append({
                    "action": "fill",
                    "selector": selector,
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                    "page_url": app_state.page.url
                })

            return [types.TextContent(
                type="text",
                text=f"Filled {selector} with text"
            )]

        elif name == "start_recording":
            app_state.recording = True
            app_state.timeline = []
            logger.info("Recording started")

            return [types.TextContent(
                type="text",
                text="Recording started"
            )]

        elif name == "stop_recording":
            app_state.recording = False
            logger.info(f"Recording stopped. Total steps: {len(app_state.timeline)}")

            return [types.TextContent(
                type="text",
                text=f"Recording stopped. Steps: {len(app_state.timeline)}"
            )]

        elif name == "get_timeline":
            import json
            timeline_json = json.dumps(app_state.timeline, ensure_ascii=False)

            return [types.TextContent(
                type="text",
                text=timeline_json
            )]

        elif name == "read_page":
            content = await app_state.page.content()
            # Ограничиваем размер
            if len(content) > 50000:
                content = content[:50000] + "\n... [truncated]"

            return [types.TextContent(
                type="text",
                text=content
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

async def init_browser():
    """Инициализация браузера"""
    if app_state.browser:
        return

    logger.info("Initializing browser...")
    app_state.playwright = await async_playwright().start()
    app_state.browser = await app_state.playwright.chromium.launch(
        headless=False,
        slow_mo=50
    )
    app_state.context = await app_state.browser.new_context(
        viewport={"width": 1920, "height": 1080}
    )
    app_state.page = await app_state.context.new_page()
    logger.info("Browser initialized")

# Starlette приложение
# Создаем транспорт один раз
sse = SseServerTransport("/messages")

async def handle_sse(scope, receive, send):
    """SSE эндпоинт - ИСПРАВЛЕНО"""
    try:
        # ✅ Используем connect_sse() который является async context manager
        async with sse.connect_sse(scope, receive, send) as streams:
            read_stream, write_stream = streams
            
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"SSE error: {e}", exc_info=True)
        raise
async def handle_messages(scope, receive, send):
    """POST сообщения - ИСПРАВЛЕНО"""
    try:
        # ✅ Используем handle_post_message транспорта
        await sse.handle_post_message(scope, receive, send)
    except Exception as e:
        logger.error(f"Messages error: {e}", exc_info=True)
        response = JSONResponse({"error": str(e)}, status_code=500)
        await response(scope, receive, send)


async def health_check(request: Request) -> Response:
    """Health check эндпоинт"""
    return JSONResponse({
        "status": "healthy",
        "browser_ready": app_state.browser is not None,
        "recording": app_state.recording,
        "timeline_steps": len(app_state.timeline)
    })

# Маршруты
routes = [
    Route("/sse", handle_sse, methods=["GET"]),
    Route("/messages", handle_messages, methods=["POST"]),
    Route("/messages/", handle_messages, methods=["POST"]),  # С trailing slash
    Route("/health", health_check, methods=["GET"]),
]

# Создание Starlette app
starlette_app = Starlette(
    debug=True,
    routes=routes
)

# Lifecycle события
@starlette_app.on_event("startup")
async def startup():
    """Запуск сервера"""
    logger.info("MCP Server starting...")
    Path("logs").mkdir(exist_ok=True)
    Path("recorded_tests").mkdir(exist_ok=True)

@starlette_app.on_event("shutdown")
async def shutdown():
    """Остановка сервера"""
    logger.info("MCP Server shutting down...")

    if app_state.page:
        await app_state.page.close()
    if app_state.context:
        await app_state.context.close()
    if app_state.browser:
        await app_state.browser.close()
    if app_state.playwright:
        await app_state.playwright.stop()

def main():
    """Запуск сервера"""
    import os
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 8000))

    logger.info(f"Starting MCP Server on {host}:{port}")

    uvicorn.run(
        starlette_app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()
