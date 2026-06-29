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


def playlist_success_text(prefix: str, count: int, playlist_name: str) -> str:
    return reply_text(prefix, f"已导入歌单：{playlist_name}，共添加 {count} 首")


def queue_text(prefix: str, lines: list[str]) -> str:
    if not lines:
        return reply_text(prefix, "当前歌单为空")
    return reply_text(prefix, "歌单：" + " | ".join(lines[:5]))


def help_text(prefix: str) -> str:
    return reply_text(
        prefix,
        "命令：/点歌 关键词 /添加歌单 歌单ID或链接 /歌单 /当前 /取消 /切歌 /点歌帮助",
    )
