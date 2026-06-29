from nonebot import get_asgi, init, load_plugin
from nonebot.adapters.bilibili_live import Adapter


init()

driver = get_asgi().driver

driver.register_adapter(Adapter)
load_plugin("nonebot_plugin_bilibili_live_song")

app = get_asgi()
