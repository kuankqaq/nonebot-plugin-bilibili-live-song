from __future__ import annotations

import aiohttp.connector
import aiohttp.resolver
import nonebot
from nonebot import get_driver, init, load_plugin
from nonebot.adapters.bilibili_live import Adapter


aiohttp.resolver.DefaultResolver = aiohttp.resolver.ThreadedResolver
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

init()

driver = get_driver()
driver.register_adapter(Adapter)
load_plugin("nonebot_plugin_bilibili_live_song")

app = None


if __name__ == "__main__":
    nonebot.run()
