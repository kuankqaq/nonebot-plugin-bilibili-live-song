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
        song_level: str = "exhigh",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.song_level = song_level
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
            play_url = await self._get_song_url(client, int(song["id"]))
        return self._to_song_info(song, play_url)

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
            urls = await self._get_song_urls(client, [int(song["id"]) for song in songs[:limit]])
        tracks = [self._to_playlist_track(song, urls.get(int(song["id"]), "")) for song in songs[:limit]]
        return playlist_name, tracks

    async def _get_song_url(self, client: httpx.AsyncClient, song_id: int) -> str:
        urls = await self._get_song_urls(client, [song_id])
        return urls.get(song_id, self._outer_url(song_id))

    async def _get_song_urls(
        self,
        client: httpx.AsyncClient,
        song_ids: list[int],
    ) -> dict[int, str]:
        if not song_ids:
            return {}
        response = await client.get(
            f"{self.base_url}/song/url/v1",
            params={"id": ",".join(str(song_id) for song_id in song_ids), "level": self.song_level},
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])
        result: dict[int, str] = {}
        for item in items:
            song_id = int(item.get("id", 0))
            if not song_id:
                continue
            url = item.get("url") or self._outer_url(song_id)
            result[song_id] = url
        for song_id in song_ids:
            result.setdefault(song_id, self._outer_url(song_id))
        return result

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

    @staticmethod
    def _outer_url(song_id: int) -> str:
        return f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"

    def _to_song_info(self, song: dict, play_url: str) -> SongInfo:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return SongInfo(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
            play_url=play_url,
            fee=int(song.get("fee") or 0),
        )

    def _to_playlist_track(self, song: dict, play_url: str) -> PlaylistTrack:
        album = (song.get("al") or song.get("album") or {}).get("name", "")
        return PlaylistTrack(
            song_id=int(song["id"]),
            song_name=song["name"],
            artist=self._artist_text(song),
            album=album,
            play_url=play_url,
            fee=int(song.get("fee") or 0),
        )
