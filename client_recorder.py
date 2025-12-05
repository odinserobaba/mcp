#!/usr/bin/env python3
"""
MCP Client Recorder - Полная версия
Записывает действия в браузере и генерирует Playwright тесты
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from mcp import ClientSession
from mcp.client.sse import sse_client
from utils import get_llm_client, MODEL_NAME, PROMPT_GENERATE_TEST, SERVER_URL
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/recorder.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def generate_test(timeline_data, max_retries=3):
    """Генерация теста с повторными попытками"""
    client_ai = get_llm_client()

    if not timeline_data:
        logger.error("Empty timeline data")
        return None

    # Упрощение данных
    clean_data = []
    for step in timeline_data:
        item = {
            "action": step.get("action"),
            "selector": step.get("selector"),
            "text": step.get("text"),
            "url": step.get("url") or step.get("page_url"),
            "timestamp": step.get("timestamp")
        }
        clean_data.append(item)

    json_str = json.dumps(clean_data, ensure_ascii=False, indent=2)

    # Умное обрезание
    MAX_SIZE = 20000
    if len(json_str) > MAX_SIZE:
        logger.warning(f"Timeline too large ({len(json_str)} chars), truncating...")
        json_str = json_str[:8000] + "\n... [truncated] ...\n" + json_str[-12000:]

    logger.info(f"⏳ Generating test (Input: {len(json_str)} chars, {len(timeline_data)} steps)...")

    # Попытки генерации
    for attempt in range(max_retries):
        try:
            resp = await client_ai.chat.completions.create(
                model=MODEL_NAME,
                messages=[{
                    "role": "user", 
                    "content": PROMPT_GENERATE_TEST.format(json_str=json_str)
                }],
                temperature=0.0,
                max_tokens=8000,
                timeout=60.0
            )

            code = resp.choices[0].message.content
            code = code.replace("```python", "").replace("```", "").strip()

            # Валидация
            if "import" in code or "async def" in code or "def " in code:
                logger.info("✅ Test generated successfully")
                return code

            logger.warning("Generated code looks invalid, retrying...")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"LLM Error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    return None

async def wait_enter():
    """Ожидание Enter с таймаутом"""
    loop = asyncio.get_running_loop()
    print("\n🔴 RECORDING! Press [ENTER] to finish (or auto-stop in 5 min)\n")

    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, sys.stdin.readline),
            timeout=300
        )
    except asyncio.TimeoutError:
        logger.info("Auto-stopping after timeout")

async def save_test(code, base_name="recorded_test"):
    """Сохранение теста"""
    output_dir = Path("recorded_tests")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}.py"
    filepath = output_dir / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            header = f"""
                        Auto-generated Playwright test
                        Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                        Run with: python {filepath}
                        """


            f.write(header + code)

        abs_path = filepath.absolute()
        logger.info(f"✅ Test saved: {abs_path}")
        print(f"\n✅ Test saved to:")
        print(f"   {abs_path}")
        print(f"\n▶️  Run with: python {filepath}")

        return filepath

    except Exception as e:
        logger.error(f"Save failed: {e}")
        return None

async def safe_call_tool(session, tool_name, arguments, max_retries=3):
    """Безопасный вызов tool"""
    for attempt in range(max_retries):
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=30.0
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"Timeout: {tool_name} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error {tool_name}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)

    raise Exception(f"Failed: {tool_name} after {max_retries} attempts")

async def main():
    """Главная функция"""
    logger.info("="*60)
    logger.info("MCP Recorder Started")
    logger.info("="*60)

    try:
        print(f"🔌 Connecting to {SERVER_URL}...")

        async with sse_client(SERVER_URL) as (r, w):
            async with ClientSession(r, w) as session:
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                logger.info("✅ Connected")

                # Навигация
                print("🌐 Opening https://ya.ru...")
                await safe_call_tool(session, "navigate", {"url": "https://ya.ru"})
                await asyncio.sleep(2)

                # Запись
                print("🎬 Recording started...")
                await safe_call_tool(session, "start_recording", {})

                # Ожидание
                await wait_enter()

                # Timeline
                print("\n📊 Fetching timeline...")
                res = await safe_call_tool(session, "get_timeline", {})

                if not res.content:
                    print("❌ No data")
                    return

                timeline = json.loads(res.content[0].text)
                print(f"📊 Steps recorded: {len(timeline)}")

                if not timeline:
                    print("⚠️  No actions")
                    return

                # Генерация
                code = await generate_test(timeline)

                if code:
                    saved = await save_test(code)

                    if saved:
                        # Сохраняем JSON
                        json_path = saved.with_suffix(".json")
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(timeline, f, ensure_ascii=False, indent=2)
                        print(f"📝 Timeline: {json_path}")
                else:
                    print("❌ Generation failed")

    except KeyboardInterrupt:
        print("\n⚠️  Cancelled")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        print(f"❌ Error: {e}")
    finally:
        logger.info("Stopped")

if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    Path("recorded_tests").mkdir(exist_ok=True)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")
