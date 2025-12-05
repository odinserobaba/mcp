import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client
from utils import get_llm_client, MODEL_NAME, SYSTEM_PROMPT_AGENT, SERVER_URL

async def run_agent(session, task):
    client_ai = get_llm_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT_AGENT}, {"role": "user", "content": task}]
    
    print(f"🤖 Task: {task}")
    
    while True:
        tools = await session.list_tools()
        openai_tools = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.inputSchema}} for t in tools.tools]

        resp = await client_ai.chat.completions.create(
            model=MODEL_NAME, messages=messages, tools=openai_tools, tool_choice="auto", temperature=0.0
        )
        msg = resp.choices[0].message
        messages.append(msg)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                name, args = tc.function.name, json.loads(tc.function.arguments)
                print(f"🔧 {name}({args})")
                try:
                    res = await session.call_tool(name, args)
                    out = res.content[0].text
                except Exception as e: out = str(e)
                
                print(f"📄 {out[:100]}...")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        else:
            print(f"🤖 Answer: {msg.content}")
            break

async def main():
    async with sse_client(SERVER_URL) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            task = input("Enter task (e.g., 'Find weather in Moscow on ya.ru'): ")
            await run_agent(session, task)

if __name__ == "__main__":
    asyncio.run(main())
