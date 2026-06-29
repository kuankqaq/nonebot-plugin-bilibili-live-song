from __future__ import annotations

import httpx

from .models import SongInfo


class MusicServiceError(RuntimeError):
    pass


class NeteaseMusicService:
    def __init__(
        self,
        base_url: str,
        auth_token: str = "",
        timeout: float = 8.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    async def search_first_song(self, keyword: str) -> SongInfo | None:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(
                f"{self.base_url}/cloudsearch",
                params={"keywords": keyword, "type": 1, "limit": 1},
            )
        response.raise_for_status()
        data = response.json()
        songs = (
            data.get("result", {}).get("songs", [])
            or data.get("data", {}).get("songs", [])
        )
        if not songs:
            return None
        song = songs[0]
        artists = song.get("ar") or song.get("artists") or []
        artist = "/".join(artist_item.get("name", "") for artist_item in artists) or "未知歌手"
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return SongInfo(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=artist,
            album=album,
        )
