import asyncio
import json
import sys
import os
from mcp import ClientSession
from mcp.client.sse import sse_client
from utils import get_llm_client, MODEL_NAME, PROMPT_GENERATE_TEST, SERVER_URL

async def generate_test(timeline_data):
    client_ai = get_llm_client()
    
    # Упрощаем JSON
    clean_data = []
    for step in timeline_data:
        item = {"action": step.get("action"), "is_popup": step.get("is_popup"), "url": step.get("page_url")}
        if "accessibility_tree" in step and isinstance(step["accessibility_tree"], dict):
            # Супер-сжатие дерева
            def simplify(n, d=0):
                if d>3: return "..."
                return {"role": n.get("role"), "name": n.get("name"), "children": [simplify(c,d+1) for c in n.get("children", [])[:3]]}
            if "error" not in step["accessibility_tree"]:
                item["state"] = simplify(step["accessibility_tree"])
        clean_data.append(item)

    json_str = json.dumps(clean_data, ensure_ascii=False, indent=2)
    if len(json_str) > 20000: json_str = json_str[-20000:] # Лимит

    print(f"⏳ Generating test (Input size: {len(json_str)})...")
    try:
        resp = await client_ai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": PROMPT_GENERATE_TEST.format(json_str=json_str)}],
            temperature=0.0, max_tokens=8000
        )
        return resp.choices[0].message.content.replace("``````", "").strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

async def wait_enter():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, sys.stdin.readline)

async def main():
    print(f"🔌 Connecting to {SERVER_URL}...")
    async with sse_client(SERVER_URL) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            
            await session.call_tool("navigate", {"url": "https://ya.ru"})
            await session.call_tool("start_recording", {})
            
            print("\n🔴 RECORDING! Press [ENTER] in console to finish.\n")
            await wait_enter()
            
            res = await session.call_tool("get_timeline", {})
            timeline = json.loads(res.content[0].text)
            print(f"📊 Steps: {len(timeline)}")
            
            if timeline:
                code = await generate_test(timeline)
                if code:
                    os.makedirs("recorded_tests", exist_ok=True)
                    path = "recorded_tests/my_test.py"
                    with open(path, "w", encoding="utf-8") as f: f.write(code)
                    print(f"✅ Saved to {path}")

if __name__ == "__main__":
    asyncio.run(main())
