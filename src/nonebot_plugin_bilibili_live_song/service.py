from __future__ import annotations

import httpx

from .models import PlaylistTrack, SongInfo


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
        return self._to_song_info(songs[0])

    async def get_playlist_tracks(
        self,
        playlist_input: str,
        limit: int,
    ) -> tuple[str, list[PlaylistTrack]]:
        playlist_id = self._extract_playlist_id(playlist_input)
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(
                f"{self.base_url}/playlist/track/all",
                params={"id": playlist_id, "limit": limit},
            )
        response.raise_for_status()
        data = response.json()
        songs = data.get("songs", [])
        playlist = data.get("playlist", {})
        playlist_name = playlist.get("name") or f"歌单{playlist_id}"
        tracks = [self._to_playlist_track(song) for song in songs[:limit]]
        return playlist_name, tracks

    @staticmethod
    def _extract_playlist_id(playlist_input: str) -> int:
        text = playlist_input.strip()
        digits = "".join(char for char in text if char.isdigit())
        if not digits:
            raise MusicServiceError("未识别到歌单 ID")
        return int(digits)

    @staticmethod
    def _artist_text(song: dict) -> str:
        artists = song.get("ar") or song.get("artists") or []
        return "/".join(artist_item.get("name", "") for artist_item in artists) or "未知歌手"

    def _to_song_info(self, song: dict) -> SongInfo:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return SongInfo(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
        )

    def _to_playlist_track(self, song: dict) -> PlaylistTrack:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return PlaylistTrack(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
        )
