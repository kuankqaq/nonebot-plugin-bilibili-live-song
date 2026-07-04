from __future__ import annotations

import asyncio
import re
import threading
import time
from datetime import datetime, timedelta

from nonebot import get_plugin_config, logger
from nonebot.adapters.bilibili_live import DanmakuEvent, SuperChatEvent, WebBot

from .config import Config
from .overlay import OverlayRenderer, OverlayServer
from .parser import CommandType, parse_command
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
_audience_feedback_by_room: dict[int, str] = {}
_NETEASE_URL_EXPIRES_RE = re.compile(r"music\.126\.net/(\d{14})/")


def update_overlay(room_id: int) -> None:
    if overlay_renderer is None:
        return
    current = queue_manager.ensure_current(room_id)
    queue = queue_manager.list_display_queue(room_id)
    if current is not None:
        queue = [item for item in queue if item.request_id != current.request_id]
    overlay_renderer.render(
        current,
        queue,
        _audience_feedback_by_room.get(room_id, ""),
    )


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


def _event_user_name(event: DanmakuEvent | SuperChatEvent) -> str:
    sender = getattr(event, "sender", None)
    if sender is None:
        return event.get_user_id()
    return (
        getattr(sender, "name", None)
        or getattr(sender, "uname", None)
        or getattr(sender, "user_name", None)
        or event.get_user_id()
    )


def _set_audience_feedback(room_id: int, user_name: str, message: str) -> None:
    _audience_feedback_by_room[room_id] = f"{user_name}: {message}"


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
    user_name = _event_user_name(event)

    if command == CommandType.HELP:
        _set_audience_feedback(
            event.room_id,
            user_name,
            "命令: /点歌 关键词 /添加歌单 歌单ID或链接 /歌单 /当前 /取消 /切歌",
        )
        update_overlay(event.room_id)
        return

    if command == CommandType.LIST:
        queue = queue_manager.list_queue(event.room_id)
        if queue:
            message = "歌单: " + " | ".join(
                f"{index}. {item.song_name} - {item.artist} @{item.user_name}"
                for index, item in enumerate(queue[:3], start=1)
            )
        else:
            message = "当前歌单为空"
        _set_audience_feedback(event.room_id, user_name, message)
        update_overlay(event.room_id)
        return

    if command == CommandType.CURRENT:
        await update_overlay_with_audio(event.room_id)
        current = queue_manager.get_current(event.room_id)
        message = (
            "当前没有播放中的歌曲"
            if current is None
            else f"当前: {current.song_name} - {current.artist}"
        )
        _set_audience_feedback(event.room_id, user_name, message)
        update_overlay(event.room_id)
        return

    if command == CommandType.CANCEL:
        cancelled = queue_manager.cancel_own_request(event.room_id, event.get_user_id())
        if cancelled is None:
            _set_audience_feedback(
                event.room_id, user_name, "你当前没有可取消的排队歌曲"
            )
            update_overlay(event.room_id)
            return
        await update_overlay_with_audio(event.room_id)
        _set_audience_feedback(
            event.room_id,
            user_name,
            f"已取消: {cancelled.song_name} - {cancelled.artist}",
        )
        update_overlay(event.room_id)
        return

    if command == CommandType.SKIP:
        if not permission_checker.can_manage(event, anchor_user_id=anchor_user_id):
            _set_audience_feedback(event.room_id, user_name, "你没有切歌权限")
            update_overlay(event.room_id)
            return
        skipped = queue_manager.skip_current(event.room_id)
        if skipped is None:
            _set_audience_feedback(event.room_id, user_name, "当前没有可切的歌曲")
            update_overlay(event.room_id)
            return
        await update_overlay_with_audio(event.room_id)
        current = queue_manager.get_current(event.room_id)
        message = f"已切歌: {skipped.song_name} - {skipped.artist}"
        if current is None:
            message += ", 队列已清空"
        _set_audience_feedback(event.room_id, user_name, message)
        update_overlay(event.room_id)
        return

    if command == CommandType.PLAYLIST:
        if not permission_checker.can_manage_playlist(
            event, anchor_user_id=anchor_user_id
        ):
            _set_audience_feedback(
                event.room_id, user_name, "只有管理员和主播可以添加歌单"
            )
            update_overlay(event.room_id)
            return
        if not payload:
            _set_audience_feedback(event.room_id, user_name, "请输入歌单 ID 或链接")
            update_overlay(event.room_id)
            return
        try:
            playlist_name, tracks = await music_service.get_playlist_tracks(
                payload,
                config.bili_live_song_playlist_max_tracks,
            )
        except MusicServiceError as exc:
            _set_audience_feedback(event.room_id, user_name, str(exc))
            update_overlay(event.room_id)
            return
        except Exception:
            logger.exception("获取网易云歌单失败")
            _set_audience_feedback(event.room_id, user_name, "歌单导入失败, 请稍后重试")
            update_overlay(event.room_id)
            return
        if not tracks:
            _set_audience_feedback(event.room_id, user_name, "歌单里没有可导入的歌曲")
            update_overlay(event.room_id)
            return
        use_warmup = queue_manager.should_use_warmup_playlist(event.room_id)
        if use_warmup:
            queue_manager.clear_warmup_playlist(event.room_id)
        added = queue_manager.add_playlist_tracks(
            room_id=event.room_id,
            user_id=event.get_user_id(),
            user_name=user_name,
            playlist_name=playlist_name,
            tracks=tracks,
            queue_type="warmup" if use_warmup else "main",
        )
        if use_warmup:
            queue_manager.mark_warmup_playlist_initialized(event.room_id)
        _set_audience_feedback(
            event.room_id,
            user_name,
            f"已导入歌单: {playlist_name}, 共添加 {added} 首",
        )
        await update_overlay_with_audio(event.room_id)
        return

    if command == CommandType.REQUEST:
        if not payload:
            _set_audience_feedback(event.room_id, user_name, "请输入要点的歌曲关键词")
            update_overlay(event.room_id)
            return
        allowed, reason = queue_manager.can_request(
            event.room_id,
            event.get_user_id(),
            settings,
        )
        if not allowed:
            _set_audience_feedback(event.room_id, user_name, reason)
            update_overlay(event.room_id)
            return
        try:
            song = await music_service.search_first_song(payload)
        except Exception:
            logger.exception("搜索网易云歌曲失败")
            _set_audience_feedback(event.room_id, user_name, "点歌服务暂时不可用")
            update_overlay(event.room_id)
            return
        if song is None:
            _set_audience_feedback(event.room_id, user_name, "没有找到对应歌曲")
            update_overlay(event.room_id)
            return
        current = queue_manager.ensure_current(event.room_id)
        if current is not None and current.song_id == song.song_id:
            _set_audience_feedback(
                event.room_id,
                user_name,
                f"正在播放: {song.song_name} - {song.artist}",
            )
            await update_overlay_with_audio(event.room_id)
            return
        existing = queue_manager.find_queued_by_song(event.room_id, song.song_id)
        if existing is not None:
            if existing.queue_type == "warmup":
                item = queue_manager.promote_request_to_main(
                    existing,
                    user_id=event.get_user_id(),
                    user_name=user_name,
                    keyword=payload,
                    is_superchat=isinstance(event, SuperChatEvent),
                    superchat_price=float(getattr(event, "price", 0.0) or 0.0),
                )
                _set_audience_feedback(
                    event.room_id,
                    user_name,
                    f"已点: {item.song_name} - {item.artist}",
                )
            else:
                _set_audience_feedback(
                    event.room_id,
                    user_name,
                    f"已在队列中: {existing.song_name} - {existing.artist}",
                )
            await update_overlay_with_audio(event.room_id)
            return
        item = queue_manager.add_request(
            room_id=event.room_id,
            user_id=event.get_user_id(),
            user_name=user_name,
            keyword=payload,
            song=song,
            is_superchat=isinstance(event, SuperChatEvent),
            superchat_price=float(getattr(event, "price", 0.0) or 0.0),
        )
        _set_audience_feedback(
            event.room_id,
            user_name,
            f"已点: {item.song_name} - {item.artist}",
        )
        await update_overlay_with_audio(event.room_id)
