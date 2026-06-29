from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class RoomSettings(BaseModel):
    enabled: bool = True
    max_queue_size: int = 50
    max_user_pending: int = 2
    request_cooldown_seconds: int = 15
    superchat_priority: bool = True


class Config(BaseModel):
    bili_live_song_enabled: bool = True
    bili_live_song_service_base_url: str
    bili_live_song_service_auth_token: str = ""
    bili_live_song_service_timeout_seconds: float = 8.0
    bili_live_song_reply_prefix: str = "🎵"
    bili_live_song_request_cooldown_seconds: int = 15
    bili_live_song_max_queue_size: int = 50
    bili_live_song_max_user_pending: int = 2
    bili_live_song_db_path: str = ".bili_live_song/song_queue.sqlite3"
    bili_live_song_admin_user_ids: set[str] = Field(default_factory=set)
    bili_live_song_room_settings: dict[int, RoomSettings] = Field(default_factory=dict)
    bili_live_song_playlist_max_tracks: int = 100
    bili_live_song_song_level: str = "exhigh"
    bili_live_song_overlay_enabled: bool = True
    bili_live_song_overlay_host: str = "127.0.0.1"
    bili_live_song_overlay_port: int = 18080
    bili_live_song_overlay_dir: str = ".bili_live_song/overlay"

    def get_room_settings(self, room_id: int) -> RoomSettings:
        return self.bili_live_song_room_settings.get(
            room_id,
            RoomSettings(
                max_queue_size=self.bili_live_song_max_queue_size,
                max_user_pending=self.bili_live_song_max_user_pending,
                request_cooldown_seconds=self.bili_live_song_request_cooldown_seconds,
            ),
        )

    @property
    def overlay_dir(self) -> Path:
        return Path(self.bili_live_song_overlay_dir).resolve()
