from __future__ import annotations

from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config
from .handlers import (
    handle_message,
    overlay_server,
    permission_checker,
    start_overlay_watcher,
    update_overlay,
)

from .matchers import danmaku_matcher, room_admins_matcher, superchat_matcher


__plugin_meta__ = PluginMetadata(
    name="Bilibili Live Song",
    description="B站直播点歌插件，使用 WebBot 与外部网易云 Node API",
    usage="/点歌 关键词 /添加歌单 歌单ID或链接 /歌单 /当前 /取消 /切歌 /点歌帮助",
    config=Config,
)

config = get_plugin_config(Config)

if overlay_server is not None:
    overlay_server.start()
    start_overlay_watcher()
    update_overlay(0)


@danmaku_matcher.handle()
async def _(bot, event):
    await handle_message(bot, event)


@superchat_matcher.handle()
async def _(bot, event):
    await handle_message(bot, event)


@room_admins_matcher.handle()
async def _(event):
    permission_checker.update_room_admins(event)
