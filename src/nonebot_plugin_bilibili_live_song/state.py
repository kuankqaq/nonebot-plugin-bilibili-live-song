from __future__ import annotations

import time
import uuid
from typing import Optional

from .config import RoomSettings
from .models import PlaylistTrack, SongInfo, SongRequest
from .storage import Storage


class QueueManager:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.last_request_time: dict[tuple[int, str], float] = {}

    def can_request(
        self,
        room_id: int,
        user_id: str,
        settings: RoomSettings,
    ) -> tuple[bool, str]:
        queue = self.storage.list_queue(room_id)
        if len(queue) >= settings.max_queue_size:
            return False, "当前歌单已满"

        user_pending = sum(1 for item in queue if item.user_id == user_id)
        if user_pending >= settings.max_user_pending:
            return False, "你排队的歌曲已经达到上限"

        key = (room_id, user_id)
        last_time = self.last_request_time.get(key, 0.0)
        if time.time() - last_time < settings.request_cooldown_seconds:
            return False, "点歌太快啦，请稍后再试"
        return True, ""

    def add_request(
        self,
        room_id: int,
        user_id: str,
        user_name: str,
        keyword: str,
        song: SongInfo,
        is_superchat: bool,
        superchat_price: float,
    ) -> SongRequest:
        now = time.time()
        request = SongRequest(
            request_id=uuid.uuid4().hex,
            room_id=room_id,
            user_id=user_id,
            user_name=user_name,
            keyword=keyword,
            song_id=song.song_id,
            song_name=song.song_name,
            artist=song.artist,
            priority=1 if is_superchat else 0,
            is_superchat=is_superchat,
            superchat_price=superchat_price,
            created_at=now,
            updated_at=now,
        )
        self.storage.upsert_request(request)
        self.last_request_time[(room_id, user_id)] = now
        return request

    def add_playlist_tracks(
        self,
        room_id: int,
        user_id: str,
        user_name: str,
        playlist_name: str,
        tracks: list[PlaylistTrack],
    ) -> int:
        added = 0
        now = time.time()
        for track in tracks:
            request = SongRequest(
                request_id=uuid.uuid4().hex,
                room_id=room_id,
                user_id=user_id,
                user_name=user_name,
                keyword=playlist_name,
                song_id=track.song_id,
                song_name=track.song_name,
                artist=track.artist,
                priority=0,
                is_superchat=False,
                superchat_price=0.0,
                created_at=now + added / 1000,
                updated_at=now + added / 1000,
            )
            self.storage.upsert_request(request)
            added += 1
        return added

    def list_queue(self, room_id: int) -> list[SongRequest]:
        return self.storage.list_queue(room_id)

    def get_current(self, room_id: int) -> Optional[SongRequest]:
        return self.storage.get_current(room_id)

    def cancel_own_request(self, room_id: int, user_id: str) -> Optional[SongRequest]:
        queue = self.storage.list_queue(room_id)
        for item in reversed(queue):
            if item.user_id == user_id:
                item.status = "cancelled"
                item.updated_at = time.time()
                self.storage.delete_request(item.request_id)
                return item
        return None

    def skip_current(self, room_id: int) -> Optional[SongRequest]:
        current = self.storage.get_current(room_id)
        if current is None:
            queue = self.storage.list_queue(room_id)
            if not queue:
                return None
            current = queue[0]
        current.status = "done"
        current.updated_at = time.time()
        self.storage.delete_request(current.request_id)
        self.storage.clear_current(room_id)
        next_queue = self.storage.list_queue(room_id)
        if next_queue:
            self.storage.set_current(room_id, next_queue[0].request_id)
        return current

    def ensure_current(self, room_id: int) -> Optional[SongRequest]:
        current = self.storage.get_current(room_id)
        if current is not None:
            return current
        queue = self.storage.list_queue(room_id)
        if not queue:
            return None
        self.storage.set_current(room_id, queue[0].request_id)
        return self.storage.get_current(room_id)
