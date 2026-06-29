from __future__ import annotations

from nonebot.adapters.bilibili_live import DanmakuEvent, RoomAdminsEvent, SuperChatEvent

from .config import Config


class PermissionChecker:
    def __init__(self, config: Config):
        self.config = config
        self.room_admins: dict[int, set[str]] = {}

    def update_room_admins(self, event: RoomAdminsEvent) -> None:
        self.room_admins[event.room_id] = {str(uid) for uid in event.uids}

    def can_manage(
        self,
        event: DanmakuEvent | SuperChatEvent,
        anchor_user_id: str | None = None,
    ) -> bool:
        user_id = event.get_user_id()
        if user_id in self.config.bili_live_song_admin_user_ids:
            return True
        if anchor_user_id and user_id == anchor_user_id:
            return True
        sender = getattr(event, "sender", None)
        if sender and getattr(sender, "is_admin", False):
            return True
        return user_id in self.room_admins.get(event.room_id, set())
