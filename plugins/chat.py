"""
AI 聊天插件
============
功能:
  - 只回复 @机器人 的消息(群聊);私聊正常回复
  - 带长期记忆:对话存进 SQLite,重启后还记得
  - 工具调用:时间/天气/搜索
  - 识图:发送图片能识别

数据流:
  QQ 消息 → 读历史 → 调 DeepSeek → 存历史 → 回复
"""

import os
import json
import base64
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.rule import Rule, to_me

# ── 密钥:优先读 secrets.json(不受环境变量快照影响),读不到再回退环境变量 ──
SECRETS_FILE = Path(__file__).parent.parent / "secrets.json"


def _load_secrets() -> dict:
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_secrets = _load_secrets()

API_KEY = _secrets.get("llm_api_key") or os.environ.get("LLM_API_KEY", "")
TAVILY_API_KEY = _secrets.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY", "")

# key 缺失时提醒(正常情况不输出)
if not API_KEY:
    print("[chat 警告] 读不到 LLM API key,请检查 secrets.json")
if not TAVILY_API_KEY:
    print("[chat 警告] 读不到 Tavily key,联网搜索将不可用")

API_URL = "https://api.deepseek.com/chat/completions"
# ⭐ 模型:deepseek-flash = DeepSeek-V4.1-Flash(支持文本+图片)
# 可选:deepseek-v4-pro(更强的 Pro 版)
MODEL = "deepseek-flash"

DB_PATH = "memory.db"

SYSTEM_PROMPT = """你是"八千代",一个 QQ 群里的 AI 助手。

关于你的名字:
- 用户会用"八千代"称呼你,那是你的名字,不是对话内容的一部分
- 如果消息里出现"八千代",那是用户在叫你,直接回答后面的问题
- 不要因为名字出现而困惑,也不要反问"八千代是谁"

回答风格:
- 简洁自然,不啰嗦
- 不知道就说不知道,不要编造
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的日期和时间(年月日，星期，时分秒)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某个城市的当前天气(温度，体感温度，天气状况，湿度，风速)",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如:北京，上海，广州",
                    }
                },
                "required": ["city"]
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "搜索互联网上的实时信息。适合查询:最新新闻、近期事件、"
                "模型知识截止后发生的事、以及你不确定或可能过时的信息。"
                "不要用于日常闲聊、算术、或已有明确答案的常识问题。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词,要简洁明确,例如:2026年诺贝尔奖 或 苹果最新发布会",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


async def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city}?format=j1"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url)
            data = resp.json()

        cur = data["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        humidity = cur["humidity"]
        wind = cur["windspeedKmph"]

        return f"{city}:{desc},温度 {temp}°C(体感 {feels}°C),湿度 {humidity}%,风速 {wind} km/h"

    except Exception as e:
        return f"查天气失败: {e}"

async def tavily_search(query: str, max_results: int = 5) -> str:
    if not TAVILY_API_KEY:
        return "搜索未配置:缺少 TAVILY_API_KEY 环境变量"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {TAVILY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "topic": "general",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
            )

        if resp.status_code != 200:
            return f"搜索失败(HTTP {resp.status_code}):{resp.text[:200]}"

        data = resp.json()
        results = data.get("results", [])

        if not results:
            return f"没有找到关于[{query}]的相关信息"

        lines = [f"关于[{query}]的搜索结果:"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            content = r.get("content", "").strip()
            if len(content) > 300:
                content = content[:300] + "..."

            lines.append(f"{i}. {title}")
            lines.append(f"   链接: {url}")
            lines.append(f"   摘要: {content}")

        return "\n".join(lines)

    except Exception as e:
        return f"搜索出错: {e}"

async def download_image(url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        mime = content_type.split(";")[0].strip()
        if not mime.startswith("image/"):
            mime = "image/jpeg"
        b64 = base64.b64encode(resp.content).decode()
        return b64, mime
async def execute_tool(name: str, args: dict) -> str:
    
    if name == "get_current_time":
        now = datetime.now()
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        return now.strftime(f"%Y年%m月%d日 %H:%M:%S 星期{weekdays[now.weekday()]}")

    if name == "get_weather":
        city = args.get("city", "北京")
        return await get_weather(city)

    if name == "web_search":
        query = args.get("query", "")
        if not query:
            return "搜索失败:缺少搜索关键词"
        return await tavily_search(query)

    return f"未知工具: {name}"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def load_history(session: str, limit: int = 30) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session = ? ORDER BY id DESC LIMIT ?",
        (session, limit)
    ).fetchall()
    conn.close()

    return [{"role": role, "content": content} for role, content in reversed(rows)]

def save_message(session: str, role:str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO messages (session, role, content) VALUES (?, ?, ?)",
        (session, role, content)
    )
    conn.commit()
    conn.close()

init_db()

BOT_NAME = "八千代"

def contains_bot_name(event: Event) -> bool:
    return BOT_NAME in event.get_plaintext()

def mention_or_name(event:Event) -> bool:
    if event.is_tome():
        return True

    return BOT_NAME in event.get_plaintext()

chat = on_message(
    rule=Rule(mention_or_name),
    priority=10,
    block=True,
)



# ── 调大模型的函数(人家给你写好了,参考你的 chat.py)──
async def ask(question: str, session: str, image_b64: str | None = None, image_mime: str = "image/jpeg") -> str:
    """调大模型,带记忆"""

    history = load_history(session)

    if image_b64:
        content = [
            {"type": "text", "text": question or "描述这张图片"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}
            },
        ]
    else:
        content = question

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": content}]
    )

    answer = ""

    async with httpx.AsyncClient(timeout=60) as client:

        for _ in range(3):

            resp = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "tools": TOOLS,
                },
            )
            data = resp.json()

            if "choices" not in data:
                return f"API 错误: {data.get('error', data)}"

            msg = data["choices"][0]["message"]

            if msg.get("tool_calls"):
                messages.append(msg)

                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    args = json.loads(fn["arguments"] or "{}")
                    result = await execute_tool(fn["name"], args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                continue

            answer = msg["content"]
            break

    if not answer:
        answer = "(工具调用次数超限)"

    save_message(session, "user", question)
    save_message(session, "assistant", answer)

    return answer
        
        

@chat.handle()
async def handle_chat(bot: Bot, event: Event):
    msg = event.get_plaintext().strip()

    image_b64 = None
    image_mime = "image/jpeg"

    for seg in event.get_message():
        if seg.type == "image":
            url = seg.data.get("url") or ""
            if url.startswith("http"):
                try:
                    image_b64, image_mime = await download_image(url)
                except Exception as e:
                    await chat.finish(f"图片下载失败: {e}")
            break


    if not msg and not image_b64:
        return

    session = event.get_session_id()

    try:
        answer = await ask(msg, session, image_b64, image_mime)
    except Exception as e:
        answer = f"出错啦: {e}"

    await chat.finish(answer)