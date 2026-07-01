from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .models import SongRequest


class OverlayRenderer:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.html_path = self.output_dir / "index.html"
        self.json_path = self.output_dir / "queue.json"
        self._ensure_html()

    def render(self, current: SongRequest | None, queue: list[SongRequest]) -> None:
        payload = {
            "current": self._serialize(current) if current else None,
            "queue": [self._serialize(item) for item in queue[:3]],
        }
        self.json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_html(self) -> None:
        self.html_path.write_text(
            """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>B站点歌队列</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    }
    body {
      margin: 0;
      background: rgba(0, 0, 0, 0);
      color: #f8fbff;
    }
    .panel {
      width: min(420px, calc(100vw - 32px));
      margin: 16px;
      padding: 14px;
      background: rgba(12, 16, 22, 0.78);
      border: 1px solid rgba(255, 255, 255, 0.14);
      border-radius: 8px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.32);
      backdrop-filter: blur(12px);
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .title {
      font-size: 16px;
      font-weight: 700;
    }
    .status {
      min-width: 72px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(76, 195, 255, 0.16);
      color: #9fe2ff;
      font-size: 12px;
      text-align: center;
    }
    .current {
      padding: 12px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .label {
      color: rgba(248, 251, 255, 0.68);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .song-name {
      font-size: 20px;
      font-weight: 700;
      line-height: 1.28;
      overflow-wrap: anywhere;
    }
    .song-meta {
      margin-top: 5px;
      color: rgba(248, 251, 255, 0.78);
      font-size: 13px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .badges {
      display: inline-flex;
      gap: 5px;
      margin-left: 7px;
      vertical-align: 2px;
    }
    .badge {
      padding: 1px 6px;
      border-radius: 999px;
      background: rgba(255, 92, 141, 0.92);
      color: #fff;
      font-size: 11px;
      font-weight: 700;
    }
    .badge.trial {
      background: rgba(255, 191, 87, 0.96);
      color: #1c1304;
    }
    .player-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 12px;
    }
    .meter {
      flex: 1;
      height: 7px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.14);
    }
    .meter span {
      display: block;
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #57d3ff, #86f3b5);
      transition: width 0.25s linear;
    }
    .time {
      min-width: 74px;
      color: rgba(248, 251, 255, 0.72);
      font-variant-numeric: tabular-nums;
      font-size: 12px;
      text-align: right;
    }
    .queue {
      margin-top: 12px;
    }
    .queue-item {
      display: grid;
      grid-template-columns: 24px 1fr;
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .queue-item:last-child {
      border-bottom: none;
    }
    .index {
      color: #9fe2ff;
      font-size: 13px;
      font-weight: 700;
    }
    audio {
      display: none;
    }
  </style>
</head>
<body>
  <div class="panel">
    <div class="header">
      <div class="title">点歌队列</div>
      <div id="status" class="status">待机</div>
    </div>
    <div class="current">
      <div class="label">当前播放</div>
      <div id="current"></div>
      <div class="player-row">
        <div class="meter"><span id="progress"></span></div>
        <div id="time" class="time">00:00 / 00:00</div>
      </div>
      <audio id="player" autoplay preload="auto"></audio>
    </div>
    <div class="queue">
      <div class="label">排队中</div>
      <div id="queue"></div>
    </div>
  </div>
  <script>
    let currentUrl = '';
    let currentRoomId = 0;
    let nextInFlight = false;
    const player = document.getElementById('player');
    const status = document.getElementById('status');
    const progress = document.getElementById('progress');
    const time = document.getElementById('time');

    async function refresh() {
      const resp = await fetch('./queue.json?_=' + Date.now());
      const data = await resp.json();
      renderCurrent(data.current);
      renderQueue(data.queue || []);
    }

    async function renderCurrent(item) {
      const current = document.getElementById('current');
      if (!item) {
        currentRoomId = 0;
        currentUrl = '';
        current.innerHTML = '<div class="song-meta">暂无播放</div>';
        status.textContent = '待机';
        player.removeAttribute('src');
        player.load();
        updateProgress();
        return;
      }

      currentRoomId = item.room_id || 0;
      current.innerHTML =
        '<div class="song-name">' + escapeHtml(item.song_name) +
        badges(item) + '</div>' +
        '<div class="song-meta">' + escapeHtml(item.artist) + ' · 点歌人 ' +
        escapeHtml(item.user_name) + '</div>';

      if (!item.play_url) {
        currentUrl = '';
        status.textContent = '无音源';
        player.removeAttribute('src');
        player.load();
        updateProgress();
        await requestNext('无音源，切下一首');
        return;
      }

      if (item.play_url !== currentUrl) {
        currentUrl = item.play_url;
        player.src = currentUrl;
        player.load();
      }
      await playQuietly();
    }

    function renderQueue(items) {
      const queue = document.getElementById('queue');
      queue.innerHTML = '';
      if (!items.length) {
        queue.innerHTML = '<div class="song-meta">暂无排队</div>';
        return;
      }
      for (const [index, item] of items.entries()) {
        const node = document.createElement('div');
        node.className = 'queue-item';
        node.innerHTML =
          '<div class="index">' + (index + 1) + '</div>' +
          '<div><div>' + escapeHtml(item.song_name) + badges(item) + '</div>' +
          '<div class="song-meta">' + escapeHtml(item.artist) + ' · ' +
          escapeHtml(item.user_name) + '</div></div>';
        queue.appendChild(node);
      }
    }

    async function playQuietly() {
      try {
        await player.play();
        status.textContent = '播放中';
      } catch (err) {
        status.textContent = '待授权';
        console.warn('autoplay blocked', err);
      }
    }

    async function requestNext(label) {
      if (!currentRoomId || nextInFlight) return;
      nextInFlight = true;
      status.textContent = label;
      currentUrl = '';
      await notifyEnded();
      setTimeout(async () => {
        nextInFlight = false;
        await refresh();
      }, 500);
    }

    async function notifyEnded() {
      if (!currentRoomId) return;
      try {
        await fetch('/api/next', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ room_id: currentRoomId }),
        });
      } catch (err) {
        console.warn('notify ended failed', err);
      }
    }

    function badges(item) {
      const values = [];
      if (item.is_superchat) values.push('<span class="badge">SC</span>');
      if (item.is_trial) values.push('<span class="badge trial">试听</span>');
      return values.length ? '<span class="badges">' + values.join('') + '</span>' : '';
    }

    function updateProgress() {
      const duration = Number.isFinite(player.duration) ? player.duration : 0;
      const current = Number.isFinite(player.currentTime) ? player.currentTime : 0;
      progress.style.width = duration
        ? Math.min(100, (current / duration) * 100) + '%'
        : '0%';
      time.textContent = formatTime(current) + ' / ' + formatTime(duration);
    }

    function formatTime(seconds) {
      const value = Math.max(0, Math.floor(seconds || 0));
      const min = String(Math.floor(value / 60)).padStart(2, '0');
      const sec = String(value % 60).padStart(2, '0');
      return min + ':' + sec;
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    player.addEventListener('playing', () => { status.textContent = '播放中'; });
    player.addEventListener('pause', () => {
      if (currentUrl && !player.ended) status.textContent = '已暂停';
    });
    player.addEventListener('error', async () => {
      await requestNext('播放失败，切下一首');
    });
    player.addEventListener('timeupdate', updateProgress);
    player.addEventListener('loadedmetadata', updateProgress);
    player.addEventListener('ended', async () => {
      await requestNext('切下一首');
    });
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>
""",
            encoding="utf-8",
        )

    @staticmethod
    def _serialize(item: SongRequest) -> dict[str, object]:
        return {
            "room_id": item.room_id,
            "song_name": item.song_name,
            "artist": item.artist,
            "user_name": item.user_name,
            "is_superchat": item.is_superchat,
            "play_url": item.play_url,
            "fee": item.fee,
            "is_trial": item.is_trial,
            "play_url_source": item.play_url_source,
        }


class OverlayServer:
    def __init__(self, directory: Path, host: str, port: int):
        self.directory = directory
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.server is not None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        handler = self._build_handler(self.directory)
        self.server = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def consume_next_room_ids(self) -> list[int]:
        room_ids: list[int] = []
        for path in self.directory.glob("next-*.flag"):
            stem = path.stem.removeprefix("next-")
            if stem.isdigit():
                room_ids.append(int(stem))
            path.unlink(missing_ok=True)
        return room_ids

    @staticmethod
    def _build_handler(directory: Path):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(directory), **kwargs)

            def do_POST(self):
                if self.path != "/api/next":
                    self.send_error(404)
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length) if content_length else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                    room_id = int(payload.get("room_id", 0))
                except Exception:
                    room_id = 0
                if room_id > 0:
                    (directory / f"next-{room_id}.flag").write_text(
                        "next",
                        encoding="utf-8",
                    )
                self.send_response(204)
                self.end_headers()

        return Handler
