from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class SongInfo:
    song_id: int
    song_name: str
    artist: str
    album: str = ""
    play_url: str = ""
    fee: int = 0
    is_trial: bool = False
    play_url_source: str = "none"


@dataclass(slots=True)
class SongRequest:
    request_id: str
    room_id: int
    user_id: str
    user_name: str
    keyword: str
    song_id: int
    song_name: str
    artist: str
    source: str = "netease"
    priority: int = 0
    is_superchat: bool = False
    superchat_price: float = 0.0
    play_url: str = ""
    fee: int = 0
    is_trial: bool = False
    play_url_source: str = "none"
    queue_type: Literal["main", "warmup"] = "main"
    status: Literal["queued", "playing", "done", "cancelled"] = "queued"
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass(slots=True)
class PlaylistTrack:
    song_id: int
    song_name: str
    artist: str
    album: str = ""
    play_url: str = ""
    fee: int = 0
    is_trial: bool = False
    play_url_source: str = "none"
