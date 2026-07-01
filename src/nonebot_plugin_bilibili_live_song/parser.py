from __future__ import annotations

from typing import Optional

from nonebot.adapters.bilibili_live import DanmakuEvent, SuperChatEvent

from .models import SongRequest


class CommandType:
    REQUEST = "request"
    LIST = "list"
    CURRENT = "current"
    CANCEL = "cancel"
    SKIP = "skip"
    HELP = "help"
    PLAYLIST = "playlist"


REQUEST_COMMANDS = ("/点歌 ", "点歌 ")
PLAYLIST_COMMANDS = ("/添加歌单 ", "/导入歌单 ")


def parse_command(event: DanmakuEvent | SuperChatEvent) -> tuple[str | None, str]:
    text = str(event.get_message()).strip()
    if not text:
        return None, ""

    for prefix in REQUEST_COMMANDS:
        if text.startswith(prefix):
            return CommandType.REQUEST, text[len(prefix) :].strip()

    for prefix in PLAYLIST_COMMANDS:
        if text.startswith(prefix):
            return CommandType.PLAYLIST, text[len(prefix) :].strip()

    if text == "/歌单":
        return CommandType.LIST, ""
    if text == "/当前":
        return CommandType.CURRENT, ""
    if text == "/取消":
        return CommandType.CANCEL, ""
    if text == "/切歌":
        return CommandType.SKIP, ""
    if text == "/点歌帮助":
        return CommandType.HELP, ""

    if text.startswith("/"):
        return None, ""
    return CommandType.REQUEST, text


def format_queue_line(index: int, item: SongRequest) -> str:
    flag = "[SC] " if item.is_superchat else ""
    return f"{index}. {flag}{item.song_name} - {item.artist} @{item.user_name}"


def format_current(item: Optional[SongRequest]) -> str:
    if item is None:
        return "当前没有播放中的歌曲"
    return f"当前：{item.song_name} - {item.artist}（点歌人：{item.user_name}）"
