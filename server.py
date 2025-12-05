#!/usr/bin/env python3
import logging
import json
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import uvicorn
from mcp.server.models import InitializationOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# Fallback for NotificationOptions
try:
    from mcp.server import NotificationOptions
except ImportError:
    class NotificationOptions:
        def __init__(self, *args, **kwargs): pass

server = Server("playwright-tools")
sse = SseServerTransport("/messages")

# Глобальное состояние
state = {
    "playwright": None, "browser": None, "context": None, "active_page": None
}
timeline = []

# JS Скрипт (внедряется во все вкладки)
RECORDER_JS = """
(() => {
    if (window._mcpRecorderActive) return;
    window._mcpRecorderActive = true;
    console.log("🔴 [MCP] Recorder injected");

    function getSelector(el) {
        try {
            if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
            if (el.id) return '#' + el.id;
            if (el.tagName === 'A' && el.innerText) return `text=${el.innerText.trim()}`;
            if (el.tagName === 'BUTTON' && el.innerText) return `button:has-text("${el.innerText.trim()}")`;
            if (el.getAttribute('aria-label')) return `[aria-label="${el.getAttribute('aria-label')}"]`;
            return el.tagName.toLowerCase();
        } catch { return "unknown"; }
    }

    async function record(type, target, extra={}) {
        if (!window.mcp_record_event) return;
        const sel = getSelector(target);
        await window.mcp_record_event(JSON.stringify({
            type: type, selector: sel, url: window.location.href, ...extra
        }));
    }

    document.addEventListener('click', (e) => record('click', e.target, {text: e.target.innerText?.substring(0,50)}), true);
    document.addEventListener('change', (e) => record('fill', e.target, {value: e.target.value}), true);
    document.addEventListener('keydown', (e) => { if(e.key === 'Enter') record('press', e.target, {key: 'Enter'}); }, true);
})();
"""

async def init_browser():
    from playwright.async_api import async_playwright
    if not state["playwright"]:
        state["playwright"] = await async_playwright().start()
    if not state["browser"]:
        state["browser"] = await state["playwright"].chromium.launch(headless=False, slow_mo=100, args=["--start-maximized"])
    
    if not state["context"]:
        state["context"] = await state["browser"].new_context(viewport={"width": 1600, "height": 900})

        # Binding для событий
        async def handle_event(source, raw_json):
            try:
                # Пытаемся достать страницу из source
                page = source.page if hasattr(source, "page") else (source.get("page") if isinstance(source, dict) else state["active_page"])
                if page: state["active_page"] = page
                
                event = json.loads(raw_json)
                logger.info(f"📸 {event['type']} on {event.get('selector')}")
                
                await asyncio.sleep(0.5) # Ждем реакции UI
                
                try: snapshot = await page.accessibility.snapshot()
                except: snapshot = {"error": "failed"}
                
                timeline.append({
                    "step": len(timeline)+1, "action": event,
                    "page_url": page.url, "accessibility_tree": snapshot
                })
            except Exception as e:
                logger.error(f"Event Error: {e}")

        await state["context"].expose_binding("mcp_record_event", handle_event)
        await state["context"].add_init_script(RECORDER_JS)
        
        # Обработка новых вкладок
        state["context"].on("page", lambda p: timeline.append({
            "step": len(timeline)+1, "action": {"type": "new_window_opened"}, 
            "is_popup": True, "page_url": "new_window"
        }))
        
        state["active_page"] = await state["context"].new_page()
        
    return state["active_page"]

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="navigate", description="Go to URL", inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
        Tool(name="start_recording", description="Inject JS", inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_timeline", description="Get logs", inputSchema={"type": "object", "properties": {}}),
        # Инструменты для Агента (AI)
        Tool(name="click", description="Click selector", inputSchema={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
        Tool(name="fill", description="Type text", inputSchema={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}),
        Tool(name="read_page", description="Get text", inputSchema={"type": "object", "properties": {}}),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    page = await init_browser()
    
    try:
        if name == "navigate":
            await page.goto(arguments["url"])
            return [TextContent(type="text", text="Navigated")]
        
        elif name == "start_recording":
            await page.evaluate(RECORDER_JS)
            return [TextContent(type="text", text="Recording Active")]
            
        elif name == "get_timeline":
            return [TextContent(type="text", text=json.dumps(timeline, ensure_ascii=False))]
            
        # Инструменты для агента
        elif name == "click":
            sel = arguments["selector"]
            if "text=" in sel: await page.click(sel) # Playwright native text locator
            else: await page.click(sel)
            return [TextContent(type="text", text=f"Clicked {sel}")]
            
        elif name == "fill":
            await page.fill(arguments["selector"], arguments["text"])
            return [TextContent(type="text", text="Filled")]
            
        elif name == "read_page":
            text = await page.inner_text("body")
            return [TextContent(type="text", text=text[:5000])]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    
    return []

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

async def messages_asgi(scope, receive, send):
    await sse.handle_post_message(scope, receive, send)

app = Starlette(routes=[Route("/sse", endpoint=handle_sse), Mount("/messages", app=messages_asgi)])

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
