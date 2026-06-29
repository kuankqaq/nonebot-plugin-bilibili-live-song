from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .models import SongRequest


class Storage:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS song_queue (
                    request_id TEXT PRIMARY KEY,
                    room_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    song_id INTEGER NOT NULL,
                    song_name TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    source TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    is_superchat INTEGER NOT NULL,
                    superchat_price REAL NOT NULL,
                    play_url TEXT NOT NULL DEFAULT '',
                    fee INTEGER NOT NULL DEFAULT 0,
                    is_trial INTEGER NOT NULL DEFAULT 0,
                    play_url_source TEXT NOT NULL DEFAULT 'none',
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(song_queue)").fetchall()
            }
            if "play_url" not in columns:
                conn.execute(
                    "ALTER TABLE song_queue ADD COLUMN play_url TEXT "
                    "NOT NULL DEFAULT ''"
                )
            if "fee" not in columns:
                conn.execute(
                    "ALTER TABLE song_queue ADD COLUMN fee INTEGER NOT NULL DEFAULT 0"
                )
            if "is_trial" not in columns:
                conn.execute(
                    "ALTER TABLE song_queue ADD COLUMN is_trial INTEGER "
                    "NOT NULL DEFAULT 0",
                )
            if "play_url_source" not in columns:
                conn.execute(
                    "ALTER TABLE song_queue ADD COLUMN play_url_source TEXT "
                    "NOT NULL DEFAULT 'none'",
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS now_playing (
                    room_id INTEGER PRIMARY KEY,
                    request_id TEXT NOT NULL
                )
                """
            )

    def upsert_request(self, item: SongRequest) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO song_queue (
                    request_id, room_id, user_id, user_name, keyword, song_id,
                    song_name, artist, source, priority, is_superchat,
                    superchat_price, play_url, fee, is_trial, play_url_source,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    room_id = excluded.room_id,
                    user_id = excluded.user_id,
                    user_name = excluded.user_name,
                    keyword = excluded.keyword,
                    song_id = excluded.song_id,
                    song_name = excluded.song_name,
                    artist = excluded.artist,
                    source = excluded.source,
                    priority = excluded.priority,
                    is_superchat = excluded.is_superchat,
                    superchat_price = excluded.superchat_price,
                    play_url = excluded.play_url,
                    fee = excluded.fee,
                    is_trial = excluded.is_trial,
                    play_url_source = excluded.play_url_source,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    item.request_id,
                    item.room_id,
                    item.user_id,
                    item.user_name,
                    item.keyword,
                    item.song_id,
                    item.song_name,
                    item.artist,
                    item.source,
                    item.priority,
                    int(item.is_superchat),
                    item.superchat_price,
                    item.play_url,
                    item.fee,
                    int(item.is_trial),
                    item.play_url_source,
                    item.status,
                    item.created_at,
                    item.updated_at,
                ),
            )

    def delete_request(self, request_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM song_queue WHERE request_id = ?", (request_id,))
            conn.execute("DELETE FROM now_playing WHERE request_id = ?", (request_id,))

    def list_queue(self, room_id: int) -> list[SongRequest]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT request_id, room_id, user_id, user_name, keyword, song_id,
                       song_name, artist, source, priority, is_superchat,
                       superchat_price, play_url, fee, is_trial, play_url_source,
                       status, created_at, updated_at
                FROM song_queue
                WHERE room_id = ? AND status = 'queued'
                ORDER BY priority DESC, created_at ASC
                """,
                (room_id,),
            ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def get_current(self, room_id: int) -> Optional[SongRequest]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.request_id, q.room_id, q.user_id, q.user_name, q.keyword,
                       q.song_id, q.song_name, q.artist, q.source, q.priority,
                       q.is_superchat, q.superchat_price, q.play_url, q.fee,
                       q.is_trial, q.play_url_source, q.status, q.created_at,
                       q.updated_at
                FROM now_playing n
                JOIN song_queue q ON q.request_id = n.request_id
                WHERE n.room_id = ?
                """,
                (room_id,),
            ).fetchone()
        return self._row_to_request(row) if row else None

    def set_current(self, room_id: int, request_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO now_playing (room_id, request_id)
                VALUES (?, ?)
                ON CONFLICT(room_id)
                DO UPDATE SET request_id = excluded.request_id
                """,
                (room_id, request_id),
            )
            conn.execute(
                "UPDATE song_queue SET status = 'playing' WHERE request_id = ?",
                (request_id,),
            )

    def clear_current(self, room_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM now_playing WHERE room_id = ?", (room_id,))

    @staticmethod
    def _row_to_request(row: tuple) -> SongRequest:
        return SongRequest(
            request_id=row[0],
            room_id=row[1],
            user_id=row[2],
            user_name=row[3],
            keyword=row[4],
            song_id=row[5],
            song_name=row[6],
            artist=row[7],
            source=row[8],
            priority=row[9],
            is_superchat=bool(row[10]),
            superchat_price=row[11],
            play_url=row[12],
            fee=int(row[13] or 0),
            is_trial=bool(row[14]),
            play_url_source=row[15] or "none",
            status=row[16],
            created_at=row[17],
            updated_at=row[18],
        )
