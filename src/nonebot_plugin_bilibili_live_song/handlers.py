from __future__ import annotations

import time

from nonebot import get_plugin_config, logger
from nonebot.adapters.bilibili_live import DanmakuEvent, SuperChatEvent, WebBot

from .config import Config
from .formatters import help_text, queue_text, reply_text, request_success_text
from .models import SongRequest
from .parser import CommandType, format_current, format_queue_line, parse_command
from .permission import PermissionChecker
from .service import NeteaseMusicService
from .state import QueueManager
from .storage import Storage


config = get_plugin_config(Config)
storage = Storage(config.bili_live_song_db_path)
queue_manager = QueueManager(storage)
permission_checker = PermissionChecker(config)
music_service = NeteaseMusicService(
    config.bili_live_song_service_base_url,
    config.bili_live_song_service_auth_token,
    config.bili_live_song_service_timeout_seconds,
)


async def handle_message(bot: WebBot, event: DanmakuEvent | SuperChatEvent) -> None:
    if not config.bili_live_song_enabled:
        return

    settings = config.get_room_settings(event.room_id)
    if not settings.enabled:
        return

    command, payload = parse_command(event)
    if command is None:
        return

    if command == CommandType.HELP:
        await bot.send(event, help_text(config.bili_live_song_reply_prefix))
        return

    if command == CommandType.LIST:
        queue = queue_manager.list_queue(event.room_id)
        lines = [format_queue_line(index, item) for index, item in enumerate(queue, start=1)]
        await bot.send(event, queue_text(config.bili_live_song_reply_prefix, lines))
        return

    if command == CommandType.CURRENT:
        current = queue_manager.ensure_current(event.room_id)
        await bot.send(
            event,
            reply_text(
                config.bili_live_song_reply_prefix,
                format_current(current),
            ),
        )
        return

    if command == CommandType.CANCEL:
        cancelled = queue_manager.cancel_own_request(event.room_id, event.get_user_id())
        if cancelled is None:
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "你当前没有可取消的排队歌曲"))
            return
        await bot.send(
            event,
            reply_text(
                config.bili_live_song_reply_prefix,
                f"已取消：{cancelled.song_name} - {cancelled.artist}",
            ),
        )
        return

    if command == CommandType.SKIP:
        anchor_user_id = None
        room = bot.rooms.get(event.room_id)
        if room is not None:
            anchor_user_id = str(room.uid)
        if not permission_checker.can_manage(event, anchor_user_id=anchor_user_id):
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "你没有切歌权限"))
            return
        skipped = queue_manager.skip_current(event.room_id)
        if skipped is None:
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "当前没有可切的歌曲"))
            return
        await bot.send(
            event,
            reply_text(
                config.bili_live_song_reply_prefix,
                f"已切歌：{skipped.song_name} - {skipped.artist}",
            ),
        )
        return

    if command == CommandType.REQUEST:
        if not payload:
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "请输入要点的歌曲关键词"))
            return
        allowed, reason = queue_manager.can_request(
            event.room_id,
            event.get_user_id(),
            settings,
        )
        if not allowed:
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, reason))
            return
        try:
            song = await music_service.search_first_song(payload)
        except Exception as exc:
            logger.exception("搜索网易云歌曲失败")
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "点歌服务暂时不可用，请稍后重试"))
            return
        if song is None:
            await bot.send(event, reply_text(config.bili_live_song_reply_prefix, "没有找到对应歌曲"))
            return
        item = queue_manager.add_request(
            room_id=event.room_id,
            user_id=event.get_user_id(),
            user_name=getattr(event.sender, "name", event.get_user_id()),
            keyword=payload,
            song=song,
            is_superchat=isinstance(event, SuperChatEvent),
            superchat_price=float(getattr(event, "price", 0.0) or 0.0),
        )
        queue_manager.ensure_current(event.room_id)
        await bot.send(event, request_success_text(config.bili_live_song_reply_prefix, item))
