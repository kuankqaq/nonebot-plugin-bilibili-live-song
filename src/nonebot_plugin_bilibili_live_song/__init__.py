from __future__ import annotations

from nonebot.plugin import PluginMetadata

from .config import Config
from .handlers import handle_message, permission_checker
from .matchers import danmaku_matcher, room_admins_matcher, superchat_matcher


__plugin_meta__ = PluginMetadata(
    name="Bilibili Live Song",
    description="B站直播点歌插件，使用 WebBot 与外部网易云 Node API",
    usage="/点歌 关键词 /歌单 /当前 /取消 /切歌 /点歌帮助",
    config=Config,
)


@danmaku_matcher.handle()
async def _(bot, event):
    await handle_message(bot, event)


@superchat_matcher.handle()
async def _(bot, event):
    await handle_message(bot, event)


@room_admins_matcher.handle()
async def _(event):
    permission_checker.update_room_admins(event)
