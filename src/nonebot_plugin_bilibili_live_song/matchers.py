from __future__ import annotations

from nonebot import get_plugin_config, on_type
from nonebot.adapters.bilibili_live import DanmakuEvent, RoomAdminsEvent, SuperChatEvent
from nonebot.exception import FinishedException
from nonebot.matcher import Matcher

from .config import Config


config = get_plugin_config(Config)


danmaku_matcher = on_type(DanmakuEvent)
superchat_matcher = on_type(SuperChatEvent)
room_admins_matcher = on_type(RoomAdminsEvent)
