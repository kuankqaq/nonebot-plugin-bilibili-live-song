from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from .models import PlaylistTrack, SongInfo


class MusicServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class PlayUrlInfo:
    url: str = ""
    source: str = "none"
    is_trial: bool = False


class NeteaseMusicService:
    def __init__(
        self,
        base_url: str,
        auth_token: str = "",
        cookie: str = "",
        timeout: float = 8.0,
        song_level: str = "exhigh",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.song_level = song_level
        self.headers = {}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
        if cookie:
            self.headers["Cookie"] = cookie

    async def search_first_song(self, keyword: str) -> SongInfo | None:
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self.headers
        ) as client:
            song_id = self._extract_song_id(keyword)
            if song_id is not None:
                return await self._get_song_info_by_id(client, song_id)

            response = await client.get(
                f"{self.base_url}/cloudsearch",
                params={"keywords": keyword, "type": 1, "limit": 1},
            )
            response.raise_for_status()
            data = response.json()
            songs = data.get("result", {}).get("songs", []) or data.get("data", {}).get(
                "songs", []
            )
            if not songs:
                return None
            song = songs[0]
            play_url = await self._get_song_url(client, int(song["id"]))
        return self._to_song_info(song, play_url)

    async def _get_song_info_by_id(
        self,
        client: httpx.AsyncClient,
        song_id: int,
    ) -> SongInfo | None:
        response = await client.get(
            f"{self.base_url}/song/detail",
            params={"ids": str(song_id)},
        )
        response.raise_for_status()
        data = response.json()
        songs = data.get("songs", [])
        if not songs:
            return None
        play_url = await self._get_song_url(client, song_id)
        return self._to_song_info(songs[0], play_url)

    async def get_playlist_tracks(
        self,
        playlist_input: str,
        limit: int,
    ) -> tuple[str, list[PlaylistTrack]]:
        playlist_id = self._extract_playlist_id(playlist_input)
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self.headers
        ) as client:
            response = await client.get(
                f"{self.base_url}/playlist/track/all",
                params={"id": playlist_id, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            songs = data.get("songs", [])
            playlist = data.get("playlist", {})
            playlist_name = playlist.get("name") or f"歌单{playlist_id}"
            urls = await self._get_song_urls(
                client,
                [int(song["id"]) for song in songs[:limit]],
            )
        tracks = [
            self._to_playlist_track(song, urls.get(int(song["id"]), PlayUrlInfo()))
            for song in songs[:limit]
        ]
        return playlist_name, tracks

    async def _get_song_url(
        self, client: httpx.AsyncClient, song_id: int
    ) -> PlayUrlInfo:
        urls = await self._get_song_urls(client, [song_id])
        return urls.get(song_id, PlayUrlInfo())

    async def get_song_url(self, song_id: int) -> PlayUrlInfo:
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self.headers
        ) as client:
            return await self._get_song_url(client, song_id)

    async def _get_song_urls(
        self,
        client: httpx.AsyncClient,
        song_ids: list[int],
    ) -> dict[int, PlayUrlInfo]:
        if not song_ids:
            return {}
        response = await client.get(
            f"{self.base_url}/song/url/v1",
            params={
                "id": ",".join(str(song_id) for song_id in song_ids),
                "level": self.song_level,
            },
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])
        result: dict[int, PlayUrlInfo] = {}
        for item in items:
            song_id = int(item.get("id", 0))
            if not song_id:
                continue
            url = item.get("url") or ""
            if url:
                result[song_id] = PlayUrlInfo(
                    url=url,
                    source="netease",
                    is_trial=bool(item.get("freeTrialInfo")),
                )
        return result

    @staticmethod
    def _extract_playlist_id(playlist_input: str) -> int:
        text = playlist_input.strip()
        digits = "".join(char for char in text if char.isdigit())
        if not digits:
            raise MusicServiceError("未识别到歌单 ID")
        return int(digits)

    @staticmethod
    def _extract_song_id(keyword: str) -> int | None:
        text = keyword.strip()
        if text.isdigit():
            return int(text)
        match = re.search(r"(?:[?&]id=|/song/)(\d+)", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _artist_text(song: dict) -> str:
        artists = song.get("ar") or song.get("artists") or []
        return (
            "/".join(artist_item.get("name", "") for artist_item in artists)
            or "未知歌手"
        )

    def _to_song_info(self, song: dict, play_url: PlayUrlInfo) -> SongInfo:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return SongInfo(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
            play_url=play_url.url,
            fee=int(song.get("fee") or 0),
            is_trial=play_url.is_trial,
            play_url_source=play_url.source,
        )

    def _to_playlist_track(self, song: dict, play_url: PlayUrlInfo) -> PlaylistTrack:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return PlaylistTrack(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
            play_url=play_url.url,
            fee=int(song.get("fee") or 0),
            is_trial=play_url.is_trial,
            play_url_source=play_url.source,
        )
