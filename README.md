# QQ AI 聊天助手

一个跑在自己电脑上的 QQ 机器人:在群里 **@ 它**(或叫它的名字)就能和 AI 对话,并且**记得你说过的话**,还能**查时间、查天气、联网搜索**。

---

## 功能

| 功能 | 说明 |
|---|---|
| **接入 QQ** | 通过 NapCat 连接,支持群聊和私聊 |
| **AI 对话** | DeepSeek **V4.1-Flash**(`deepseek-flash`),兼容 OpenAI 格式,可换服务商 |
| **长期记忆** | 对话存进 SQLite,**程序重启也不丢** |
| **分会话记忆** | 不同群 / 私聊的历史互相独立 |
| **触发词** | 群里只有 **真 @** 或 **消息里带机器人名字** 才回复;私聊正常回复 |
| **工具调用** | ① 查时间 ② 查天气(wttr.in,免费无 key)③ **联网搜索**(Tavily) |
| **识图** | 发图片能识别内容(`deepseek-flash` 原生支持视觉输入) |
| **人格设定** | 通过 `SYSTEM_PROMPT` 控制名字、性格、回答风格 |
| **开机自启** | Windows 任务计划自动拉起 NapCat + 机器人 |

---

## 架构

```
QQ 群 / 私聊
     ↓
NapCat(E:\NapCatShell)          ← 登录小号,把 QQ 消息转成 OneBot 协议
     ↓ WebSocket(127.0.0.1:3001)
NoneBot2(本项目)                ← 收消息、匹配规则、调插件
     ↓
plugins/chat.py                 ← 读历史 → 调 AI ↔ 执行工具 → 存历史 → 回复
     ↓ HTTPS                        │
     │                              ├── DeepSeek API(对话 + 工具决策)
     │                              ├── wttr.in(天气)
     │                              └── Tavily API(搜索)
     ↓
SQLite(memory.db)               ← 对话历史
```

**工作流程:**
```
① 收到 @ 或带名字的消息
② 从数据库读历史(最近 30 条)
③ 拼上 system prompt + 历史 + 当前问题,发给 AI(附带工具清单)
④ AI 判断:需要工具吗?
     ├─ 需要 → 返回 tool_calls → 执行工具 → 结果发回 → 再问一次(最多 3 轮)
     └─ 不需要 → 直接给回答
⑤ 把这一轮存进数据库
⑥ 回复到 QQ
```

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `bot.py` | **程序入口**:初始化 NoneBot、注册适配器、加载插件 |
| `plugins/chat.py` | **核心插件**:AI 对话 + 记忆 + 触发词 + 工具调用 |
| **`secrets.json`** | **API key(DeepSeek + Tavily)← 敏感,别外传** |
| `memory.db` | SQLite 数据库(对话历史)**← 敏感,别外传** |
| `.env` | NoneBot 配置(驱动、WebSocket 地址) |
| `setup_autostart.ps1` | 配置开机自启的脚本 |
| `.gitignore` | 把敏感 / 生成文件排除在 git 外 |
| `chat.py` | 早期命令行版(独立运行,可作参考) |

---

## 运行

### 前置条件

1. **NapCat** 已安装并登录小号(在 `E:\NapCatShell`)
2. `secrets.json` 里有 key(DeepSeek 和 Tavily)

### secrets.json 格式

```json
{
  "llm_api_key": "sk-你的DeepSeek key",
  "tavily_api_key": "tvly-你的Tavily key"
}
```

> 插件启动时读这个文件(**不受环境变量"进程快照"影响**)。
> 缺 key 时会打印警告,程序照常运行(只是对应功能不可用)。

### 手动启动

```powershell
cd C:\Users\37612\Desktop\学习\qq-bot
.\.venv\Scripts\python.exe bot.py
```

> ⚠️ **不用再设 `$env:LLM_API_KEY`** —— key 从 `secrets.json` 读。

**启动成功的标志:**
```
[SUCCESS] Succeeded to load plugin "chat"
[SUCCESS] OneBot V11 | Bot <QQ号> connected
```

### 开机自启

以**管理员身份**运行:

```powershell
powershell -ExecutionPolicy Bypass -File setup_autostart.ps1
```

会创建两个计划任务:

| 任务名 | 启动什么 | 权限 |
|---|---|---|
| `NapCat-AutoStart` | `E:\NapCatShell\launcher.bat` | 最高 |
| `QQBot-AutoStart` | `.venv\Scripts\python.exe bot.py` | 普通 |

> 想临时关掉:任务计划程序 → 找到任务 → 禁用。

---

## 配置说明

### `plugins/chat.py` 里的关键变量

| 变量 | 说明 |
|---|---|
| `_secrets` | 从 `secrets.json` 读出的 key(优先),读不到回退环境变量 |
| `API_KEY` | DeepSeek key(来自 `llm_api_key`) |
| `TAVILY_API_KEY` | Tavily key(来自 `tavily_api_key`) |
| `API_URL` | 模型接口地址(换服务商改这里) |
| `MODEL` | **`deepseek-flash`**(= V4.1-Flash,支持文本+图片) |
| `DB_PATH` | 数据库文件路径(`memory.db`) |
| `SYSTEM_PROMPT` | **人格设定**(名字、性格、规矩) |
| `BOT_NAME` | 机器人名字(`八千代`),用于"叫名字"触发 |
| `TOOLS` | 工具清单(时间 / 天气 / 搜索) |
| `SECRETS_FILE` | `secrets.json` 的绝对路径 |

### `.env`(NoneBot 配置)

```ini
DRIVER=~websockets
ONEBOT_WS_URLS=["ws://127.0.0.1:3001"]
LOG_LEVEL=INFO
```

> ⚠️ 驱动必须用 `~websockets`,因为 `~fastapi` **不支持 WebSocket 客户端连接**(会连不上 NapCat)。

### 三个工具的参数速查

| 工具 | 参数 | 依赖 |
|---|---|---|
| `get_current_time` | 无 | 无(本地时间) |
| `get_weather` | `city`(城市名) | wttr.in(免费) |
| `web_search` | `query`(关键词) | Tavily(免费 1000 次/月) |

---

## 常用排查

| 现象 | 检查 |
|---|---|
| **程序跑着但不回复** | 日志有没有 `Bot xxx connected` |
| **群里不回复** | 是不是真 @ 了?手打 `@名字` 不算(除非消息里带 `BOT_NAME`) |
| **回复"缺 API key"** | `secrets.json` 里的 `tavily_api_key` / `llm_api_key` 是否为空 |
| **搜索报 400** | 参数类型错(比如 `"False"` 应该是 `False`) |
| **搜索不触发** | 清 `memory.db`(历史里的旧结论会干扰 AI),换个新问法 |
| **报 `[choices]` 错** | API key 不对 / 余额不足(插件会显示真实错误) |
| **重启后忘了对话** | `memory.db` 是否存在、是否有权限 |
| **重启后要扫码** | NapCat 登录态过期;或用 `-q QQ号` 参数快速登录 |
| **管理端连不上** | `~fastapi` 驱动的问题 → 改 `~websockets` |

---

## ⚠️ 重要提醒

1. **一定用小号** —— NapCat 走非官方协议,主号有封号风险
2. **`secrets.json` / `memory.db` / `.env` 别外传** —— 里面有 key 和聊天记录
3. **电脑别关 / 别睡眠** —— 关了机器人就下线,开机自动回来
4. **6099(WebUI)端口别暴露公网** —— 否则别人能控制你的 QQ
5. **Tavily 免费 1000 次/月** —— 用 `search_depth: basic`(1 credit/次),别用 advanced

---

## 踩过的坑(备忘)

| 坑 | 原因 | 解决 |
|---|---|---|
| `pip` 卡死 | 清华源在这台机器上慢 | 换阿里云源 `https://mirrors.aliyun.com/pypi/simple/` |
| `ModuleNotFoundError` | 用了系统 Python 而非 venv | 用 `.venv\Scripts\python.exe` |
| 连不上 NapCat | `~fastapi` 不支持 WS 客户端 | 改 `DRIVER=~websockets` |
| `Rule` 报 "Or operation not allowed" | NoneBot 2.5 禁止 `rule1 \| rule2` | 合并成一个规则函数 |
| QQ 报"文件已损坏" | 一键安装的 QQ 副本不完整 | 改用手动安装(官方 QQ + launcher.bat) |
| API 报 `[choices]` | key 不对 | 检查 key(现在从 `secrets.json` 读) |
| SQL `execute` TypeError | SQL 和参数之间少逗号 | `execute("SQL", (参数,))` |
| **Tavily 报 400** `Invalid value for include_answer` | 传了字符串 `"False"`,要布尔 `False` | **布尔值不加引号** |
| **环境变量读不到** | 进程启动早于变量设置(快照) | 改成读 `secrets.json` 文件 |
| **`TAVILY` 拼错** | 手打成 `TAVILIY` / `TAVIY` | 复制粘贴,别手打 |

---

## 开发历程

| 阶段 | 做了什么 |
|---|---|
| **① 环境** | Python venv + nonebot2 + onebot 适配器 + fastapi/uvicorn |
| **② 命令行版** | `chat.py`:用 httpx 调 DeepSeek,终端里对话 |
| **③ 接 QQ** | NapCat 手动安装(官方 QQ + launcher.bat)→ 登录小号 → WebUI 配 OneBot WS |
| **④ NoneBot** | `bot.py` + `plugins/chat.py`,从 WS 收消息 → 调 AI → 回复 |
| **⑤ 修复驱动** | `~fastapi` → `~websockets`(否则连不上) |
| **⑥ 长期记忆** | SQLite 存历史,按 `session` 分会话 |
| **⑦ 触发词** | `to_me()` → 自定义 `Rule`(真 @ 或文本含 `BOT_NAME`) |
| **⑧ 开机自启** | 任务计划(管理员权限 + 延迟) |
| **⑨ 工具调用** | 时间 → 天气 → 搜索(Function Calling + Tavily) |
| **⑩ 人格设定** | `SYSTEM_PROMPT`(名字"八千代") |
| **⑪ 密钥改造** | 环境变量 → `secrets.json`(避开快照问题) |

---

## 后续可扩展

- [x] **工具调用**(时间 / 天气 / 搜索)
- [x] **人格设定**
- [ ] **识图** —— `deepseek-flash` 支持图片输入,可以做"发图问这是什么"
- [ ] **MCP 接入** —— 标准化的工具协议(参考 `E:\Shuvi-agent\services\search-mcp`)
- [ ] **RAG 知识库** —— 把课程资料喂进去,做学习助手
- [ ] **主动说话** —— 定时问候 / 提醒
- [ ] **部署到服务器** —— 24 小时在线,不依赖自己电脑
