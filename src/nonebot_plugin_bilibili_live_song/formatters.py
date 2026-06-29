from __future__ import annotations

from .models import SongRequest


def reply_text(prefix: str, message: str) -> str:
    if not prefix:
        return message
    return f"{prefix} {message}"


def request_success_text(prefix: str, item: SongRequest) -> str:
    sc_prefix = "[SC] " if item.is_superchat else ""
    return reply_text(
        prefix,
        f"已点歌：{sc_prefix}{item.song_name} - {item.artist}",
    )


def queue_text(prefix: str, lines: list[str]) -> str:
    if not lines:
        return reply_text(prefix, "当前歌单为空")
    return reply_text(prefix, "歌单：" + " | ".join(lines[:5]))


def help_text(prefix: str) -> str:
    return reply_text(
        prefix,
        "命令：/点歌 关键词 /歌单 /当前 /取消 /切歌 /点歌帮助",
    )
