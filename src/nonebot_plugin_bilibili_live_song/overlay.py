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
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>B站点歌队列</title>
  <style>
    body {
      margin: 0;
      font-family: \"Microsoft YaHei\", sans-serif;
      background: rgba(0,0,0,0);
      color: #fff;
    }
    .panel {
      width: 460px;
      margin: 16px;
      padding: 16px;
      background: rgba(14, 18, 30, 0.72);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 16px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
      backdrop-filter: blur(10px);
    }
    .title {
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 12px;
    }
    .current {
      margin-bottom: 16px;
      padding: 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.08);
    }
    .current-label, .queue-label {
      font-size: 12px;
      opacity: 0.75;
      margin-bottom: 6px;
    }
    .song-name {
      font-size: 20px;
      font-weight: 700;
      line-height: 1.3;
    }
    .song-meta {
      margin-top: 4px;
      font-size: 14px;
      opacity: 0.88;
    }
    audio {
      width: 100%;
      margin-top: 10px;
      filter: drop-shadow(0 4px 12px rgba(0,0,0,0.25));
    }
    .queue-item {
      display: flex;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .queue-item:last-child { border-bottom: none; }
    .index {
      width: 24px;
      font-weight: 700;
      color: #7fd0ff;
    }
    .badge {
      display: inline-block;
      margin-left: 6px;
      padding: 1px 6px;
      border-radius: 999px;
      background: #ff6699;
      font-size: 11px;
      vertical-align: middle;
    }
    .vip {
      background: #ffb020;
      color: #222;
    }
  </style>
</head>
<body>
  <div class=\"panel\">
    <div class=\"title\">点歌队列</div>
    <div class=\"current\">
      <div class=\"current-label\">当前播放</div>
      <div id=\"current\"></div>
      <audio id=\"player\" controls autoplay preload=\"auto\"></audio>
    </div>
    <div class=\"queue-label\">排队中（最多显示3首）</div>
    <div id=\"queue\"></div>
  </div>
  <script>
    let currentUrl = '';
    let currentRoomId = 0;
    const player = document.getElementById('player');
    async function refresh() {
      const resp = await fetch('./queue.json?_=' + Date.now());
      const data = await resp.json();
      const current = document.getElementById('current');
      const queue = document.getElementById('queue');
      if (data.current) {
        currentRoomId = data.current.room_id || 0;
        current.innerHTML = '<div class="song-name">' + escapeHtml(data.current.song_name) +
          (data.current.is_superchat ? '<span class="badge">SC</span>' : '') +
          (data.current.fee ? '<span class="badge vip">VIP/试听</span>' : '') +
          '</div><div class="song-meta">' + escapeHtml(data.current.artist) + ' · 点歌人 ' +
          escapeHtml(data.current.user_name) + '</div>';
        current.appendChild(player);
        if (data.current.play_url && data.current.play_url !== currentUrl) {
          currentUrl = data.current.play_url;
          player.src = currentUrl;
          try { await player.play(); } catch (err) { console.warn('autoplay blocked', err); }
        }
      } else {
        currentRoomId = 0;
        current.innerHTML = '<div class="song-meta">暂无播放</div>';
        current.appendChild(player);
        currentUrl = '';
        player.removeAttribute('src');
        player.load();
      }
      queue.innerHTML = '';
      for (const [index, item] of data.queue.entries()) {
        const node = document.createElement('div');
        node.className = 'queue-item';
        node.innerHTML = '<div class="index">' + (index + 1) + '</div>' +
          '<div><div>' + escapeHtml(item.song_name) +
          (item.is_superchat ? '<span class="badge">SC</span>' : '') +
          (item.fee ? '<span class="badge vip">VIP/试听</span>' : '') +
          '</div><div class="song-meta">' + escapeHtml(item.artist) + ' · ' +
          escapeHtml(item.user_name) + '</div></div>';
        queue.appendChild(node);
      }
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
    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }
    player.addEventListener('ended', async () => {
      currentUrl = '';
      await notifyEnded();
      setTimeout(refresh, 500);
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
                    (directory / f"next-{room_id}.flag").write_text("next", encoding="utf-8")
                self.send_response(204)
                self.end_headers()

        return Handler
