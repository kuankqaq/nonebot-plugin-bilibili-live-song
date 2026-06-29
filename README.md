# nonebot-plugin-bilibili-live-song

基于 `nonebot-adapter-bilibili-live` 的 B 站直播点歌插件。

## 特性

- 仅支持 **用户 Bot（Web API）**
- 通过外部 **NeteaseCloudMusicApi** 搜歌
- `/点歌 关键词` 自动取第一首结果
- 通过 `/song/url/v1` 获取真实可播地址，失败时自动回退到 `outer/url`
- 支持 `/添加歌单 歌单ID或链接`，且**只有管理员和主播能用**
- 支持 `/歌单`、`/当前`、`/取消`、`/切歌`、`/点歌帮助`
- 支持 **SuperChat 优先**
- 使用 **SQLite** 持久化歌单与当前播放状态
- 管理权限支持：配置管理员 + 主播 + 房管
- 自带一个**简单叠加层**页面，用于显示当前播放和队列，并内置浏览器音频播放

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
BILI_LIVE_SONG_PLAYLIST_MAX_TRACKS=100
BILI_LIVE_SONG_SONG_LEVEL=exhigh
BILI_LIVE_SONG_OVERLAY_ENABLED=true
BILI_LIVE_SONG_OVERLAY_HOST=127.0.0.1
BILI_LIVE_SONG_OVERLAY_PORT=18080
BILI_LIVE_SONG_OVERLAY_DIR=.bili_live_song/overlay
```

## 命令

- `/点歌 稻香`
- `/添加歌单 123456789`
- `/添加歌单 https://music.163.com/#/playlist?id=123456789`
- `/歌单`
- `/当前`
- `/取消`
- `/切歌`
- `/点歌帮助`

## NeteaseCloudMusicApi

默认接口：

- 搜歌：`GET /cloudsearch?keywords=xxx&type=1&limit=1`
- 取歌单歌曲：`GET /playlist/track/all?id=歌单ID&limit=100`
- 获取播放地址：`GET /song/url/v1?id=歌曲ID&level=exhigh`

如果 `/song/url/v1` 返回空地址，则自动回退到：

- `https://music.163.com/song/media/outer/url?id=SONG_ID.mp3`

## 简单叠加层

插件会生成一个简单的 overlay 页面和数据文件：

- 页面：`<overlay_dir>/index.html`
- 数据：`<overlay_dir>/queue.json`

启用 overlay 后，插件内部会启动一个静态 HTTP 服务，默认地址：

- `http://127.0.0.1:18080/`

你可以把这个地址作为浏览器源添加到 OBS。

### 注意

这个页面内置了 HTML5 `audio` 播放器：
- 当前播放歌曲会自动切换到对应 `play_url`
- VIP/试听歌曲会在 overlay 中标记出来
- 真正有声音，取决于 **你打开这个 overlay 的浏览器/OBS 浏览器源是否允许播放音频**

## 说明

本插件当前负责：

- 搜歌
- 取播放 URL
- 导入歌单
- 入队
- 持久化排队状态
- 查询/取消/切歌
- 输出简单叠加层队列视图

如果你后续还要更完整的播放器控制（播放完成自动切下一首、播放状态回传、切歌联动），可以继续扩展 `handlers.py` 与 `overlay.py`。
