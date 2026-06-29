# nonebot-plugin-bilibili-live-song

基于 `nonebot-adapter-bilibili-live` 的 B 站直播点歌插件。

## 特性

- 仅支持 **用户 Bot（Web API）**
- 通过外部 **NeteaseCloudMusicApi** 搜歌
- `/点歌 关键词` 自动取第一首结果
- 支持 `/歌单`、`/当前`、`/取消`、`/切歌`、`/点歌帮助`
- 支持 **SuperChat 优先**
- 使用 **SQLite** 持久化歌单与当前播放状态
- 管理权限支持：配置管理员 + 主播 + 房管

## 安装

```bash
pip install -e .
```

## 依赖适配器

请先正确配置：

- `nonebot-adapter-bilibili-live`
- `BILIBILI_LIVE_BOTS` 使用 **WebBot** 配置

## 配置

```dotenv
BILI_LIVE_SONG_SERVICE_BASE_URL=http://127.0.0.1:3000
BILI_LIVE_SONG_SERVICE_AUTH_TOKEN=
BILI_LIVE_SONG_SERVICE_TIMEOUT_SECONDS=8
BILI_LIVE_SONG_ENABLED=true
BILI_LIVE_SONG_ADMIN_USER_IDS=["123456"]
BILI_LIVE_SONG_REPLY_PREFIX=🎵
BILI_LIVE_SONG_REQUEST_COOLDOWN_SECONDS=15
BILI_LIVE_SONG_MAX_QUEUE_SIZE=50
BILI_LIVE_SONG_MAX_USER_PENDING=2
BILI_LIVE_SONG_DB_PATH=.bili_live_song/song_queue.sqlite3
```

可选的每房间配置：

```dotenv
BILI_LIVE_SONG_ROOM_SETTINGS={
  "544853": {
    "enabled": true,
    "max_queue_size": 30,
    "max_user_pending": 2,
    "request_cooldown_seconds": 10,
    "superchat_priority": true
  }
}
```

## 命令

- `/点歌 稻香`
- `/歌单`
- `/当前`
- `/取消`
- `/切歌`
- `/点歌帮助`

## NeteaseCloudMusicApi

默认搜索接口优先使用：

- `GET /cloudsearch?keywords=xxx&type=1&limit=1`

如果你的服务做了二次封装，可以在代码里扩展 `service.py`。

## 说明

本插件当前只负责：

- 搜歌
- 入队
- 持久化排队状态
- 查询/取消/切歌

如果你后续还要和外部播放器状态联动，可以继续扩展 `service.py` 与 `handlers.py`。
