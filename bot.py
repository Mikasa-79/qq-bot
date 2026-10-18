"""
QQ 聊天助手 - 程序入口
========================
运行:  .venv\Scripts\python.exe bot.py

这个文件只做三件事:
  ① 初始化 NoneBot(自动读 .env)
  ② 注册 OneBot v11 适配器(和 NapCat 通信)
  ③ 加载 plugins 目录下的所有插件
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter


# ① 初始化:NoneBot 会读同目录的 .env
nonebot.init()

# ② 注册适配器:告诉 NoneBot 用 OneBot v11 协议(就是 NapCat 说的那套)
driver = nonebot.get_driver()
driver.register_adapter(Adapter)

# ③ 加载插件:把 plugins/ 目录下所有插件装进来
nonebot.load_plugins("plugins")

# ④ 启动(会一直运行,别关)
if __name__ == "__main__":
    nonebot.run()
