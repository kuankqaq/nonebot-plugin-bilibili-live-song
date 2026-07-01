from __future__ import annotations

import asyncio
import re
import threading
import time
from datetime import datetime, timedelta

from nonebot import get_plugin_config, logger
from nonebot.adapters.bilibili_live import DanmakuEvent, SuperChatEvent, WebBot

from .config import Config
from .formatters import (
    help_text,
    playlist_success_text,
    queue_text,
    reply_text,
    request_success_text,
)
from .overlay import OverlayRenderer, OverlayServer
from .parser import CommandType, format_current, format_queue_line, parse_command
from .permission import PermissionChecker
from .service import MusicServiceError, NeteaseMusicService
from .state import QueueManager
from .storage import Storage

config = get_plugin_config(Config)
storage = Storage(config.bili_live_song_db_path)
queue_manager = QueueManager(storage)
permission_checker = PermissionChecker(config)
music_service = NeteaseMusicService(
    config.bili_live_song_service_base_url,
    config.bili_live_song_service_auth_token,
    config.bili_live_song_service_cookie,
    config.bili_live_song_service_timeout_seconds,
    config.bili_live_song_song_level,
)
overlay_renderer = (
    OverlayRenderer(config.overlay_dir)
    if config.bili_live_song_overlay_enabled
    else None
)
overlay_server = (
    OverlayServer(
        config.overlay_dir,
        config.bili_live_song_overlay_host,
        config.bili_live_song_overlay_port,
    )
    if config.bili_live_song_overlay_enabled
    else None
)
_overlay_watcher_started = False
_NETEASE_URL_EXPIRES_RE = re.compile(r"music\.126\.net/(\d{14})/")


def update_overlay(room_id: int) -> None:
    if overlay_renderer is None:
        return
    current = queue_manager.ensure_current(room_id)
    queue = queue_manager.list_display_queue(room_id)
    overlay_renderer.render(current, queue)


async def update_overlay_with_audio(room_id: int) -> None:
    current = queue_manager.ensure_current(room_id)
    queue = queue_manager.list_display_queue(room_id)
    for item in ([current] if current else []) + queue[:3]:
        if item.play_url and not _is_play_url_expired(item.play_url):
            continue
        play_url = await music_service.get_song_url(item.song_id)
        if play_url.url:
            item.play_url = play_url.url
            item.is_trial = play_url.is_trial
            item.play_url_source = play_url.source
            queue_manager.update_request(item)
    update_overlay(room_id)


def _is_play_url_expired(url: str) -> bool:
    match = _NETEASE_URL_EXPIRES_RE.search(url)
    if not match:
        return False
    expires_at = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    return expires_at <= datetime.now() + timedelta(minutes=3)


def process_next_track(room_id: int) -> None:
    skipped = queue_manager.skip_current(room_id)
    if skipped is None:
        update_overlay(room_id)
        return
    asyncio.run(update_overlay_with_audio(room_id))


def start_overlay_watcher() -> None:
    global _overlay_watcher_started
    if _overlay_watcher_started or overlay_server is None:
        return

    def worker() -> None:
        while True:
            room_ids = overlay_server.consume_next_room_ids()
            for room_id in room_ids:
                process_next_track(room_id)
            time.sleep(1)

    thread = threading.Thread(target=worker, daemon=True, name="overlay-next-watcher")
    thread.start()
    _overlay_watcher_started = True


async def handle_message(bot: WebBot, event: DanmakuEvent | SuperChatEvent) -> None:
    if not config.bili_live_song_enabled:
        return

    settings = config.get_room_settings(event.room_id)
    if not settings.enabled:
        return

    command, payload = parse_command(event)
    if command is None:
        return

    anchor_user_id = None
    room = bot.rooms.get(event.room_id)
    if room is not None:
        anchor_user_id = str(room.uid)

    if command == CommandType.HELP:
        await bot.send(event, help_text(config.bili_live_song_reply_prefix))
        return

    if command == CommandType.LIST:
        queue = queue_manager.list_queue(event.room_id)
        lines = [
            format_queue_line(index, item) for index, item in enumerate(queue, start=1)
        ]
        await bot.send(event, queue_text(config.bili_live_song_reply_prefix, lines))
        return

    if command == CommandType.CURRENT:
        await update_overlay_with_audio(event.room_id)
        current = queue_manager.get_current(event.room_id)
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
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "你当前没有可取消的排队歌曲"
                ),
            )
            return
        await update_overlay_with_audio(event.room_id)
        await bot.send(
            event,
            reply_text(
                config.bili_live_song_reply_prefix,
                f"已取消：{cancelled.song_name} - {cancelled.artist}",
            ),
        )
        return

    if command == CommandType.SKIP:
        if not permission_checker.can_manage(event, anchor_user_id=anchor_user_id):
            await bot.send(
                event, reply_text(config.bili_live_song_reply_prefix, "你没有切歌权限")
            )
            return
        skipped = queue_manager.skip_current(event.room_id)
        if skipped is None:
            await bot.send(
                event,
                reply_text(config.bili_live_song_reply_prefix, "当前没有可切的歌曲"),
            )
            return
        await update_overlay_with_audio(event.room_id)
        current = queue_manager.get_current(event.room_id)
        message = f"已切歌：{skipped.song_name} - {skipped.artist}"
        if current is None:
            message += "，队列已清空"
        await bot.send(
            event,
            reply_text(config.bili_live_song_reply_prefix, message),
        )
        return

    if command == CommandType.PLAYLIST:
        if not permission_checker.can_manage_playlist(
            event, anchor_user_id=anchor_user_id
        ):
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "只有管理员和主播可以添加歌单"
                ),
            )
            return
        if not payload:
            await bot.send(
                event,
                reply_text(config.bili_live_song_reply_prefix, "请输入歌单 ID 或链接"),
            )
            return
        try:
            playlist_name, tracks = await music_service.get_playlist_tracks(
                payload,
                config.bili_live_song_playlist_max_tracks,
            )
        except MusicServiceError as exc:
            await bot.send(
                event, reply_text(config.bili_live_song_reply_prefix, str(exc))
            )
            return
        except Exception:
            logger.exception("获取网易云歌单失败")
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "歌单导入失败，请稍后重试"
                ),
            )
            return
        if not tracks:
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "歌单里没有可导入的歌曲"
                ),
            )
            return
        use_warmup = queue_manager.should_use_warmup_playlist(event.room_id)
        if use_warmup:
            queue_manager.clear_warmup_playlist(event.room_id)
        added = queue_manager.add_playlist_tracks(
            room_id=event.room_id,
            user_id=event.get_user_id(),
            user_name=getattr(event.sender, "name", event.get_user_id()),
            playlist_name=playlist_name,
            tracks=tracks,
            queue_type="warmup" if use_warmup else "main",
        )
        if use_warmup:
            queue_manager.mark_warmup_playlist_initialized(event.room_id)
        await update_overlay_with_audio(event.room_id)
        await bot.send(
            event,
            playlist_success_text(
                config.bili_live_song_reply_prefix, added, playlist_name
            ),
        )
        return

    if command == CommandType.REQUEST:
        if not payload:
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "请输入要点的歌曲关键词"
                ),
            )
            return
        allowed, reason = queue_manager.can_request(
            event.room_id,
            event.get_user_id(),
            settings,
        )
        if not allowed:
            await bot.send(
                event, reply_text(config.bili_live_song_reply_prefix, reason)
            )
            return
        try:
            song = await music_service.search_first_song(payload)
        except Exception:
            logger.exception("搜索网易云歌曲失败")
            await bot.send(
                event,
                reply_text(
                    config.bili_live_song_reply_prefix, "点歌服务暂时不可用，请稍后重试"
                ),
            )
            return
        if song is None:
            await bot.send(
                event,
                reply_text(config.bili_live_song_reply_prefix, "没有找到对应歌曲"),
            )
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
        await update_overlay_with_audio(event.room_id)
        await bot.send(
            event, request_success_text(config.bili_live_song_reply_prefix, item)
        )
