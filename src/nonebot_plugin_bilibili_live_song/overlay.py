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
            "queue": [self._serialize(item) for item in queue[:10]],
        }
        self.json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_html(self) -> None:
        if self.html_path.exists():
            return
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
      font-family: "Microsoft YaHei", sans-serif;
      background: transparent;
      color: #fff;
    }
    .panel {
      width: 420px;
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
  </style>
</head>
<body>
  <div class=\"panel\">
    <div class=\"title\">点歌队列</div>
    <div class=\"current\">
      <div class=\"current-label\">当前播放</div>
      <div id=\"current\"></div>
    </div>
    <div class=\"queue-label\">排队中</div>
    <div id=\"queue\"></div>
  </div>
  <script>
    async function refresh() {
      const resp = await fetch('./queue.json?_=' + Date.now());
      const data = await resp.json();
      const current = document.getElementById('current');
      const queue = document.getElementById('queue');
      if (data.current) {
        current.innerHTML = '<div class="song-name">' + escapeHtml(data.current.song_name) +
          (data.current.is_superchat ? '<span class="badge">SC</span>' : '') +
          '</div><div class="song-meta">' + escapeHtml(data.current.artist) + ' · 点歌人 ' +
          escapeHtml(data.current.user_name) + '</div>';
      } else {
        current.innerHTML = '<div class="song-meta">暂无播放</div>';
      }
      queue.innerHTML = '';
      for (const [index, item] of data.queue.entries()) {
        const node = document.createElement('div');
        node.className = 'queue-item';
        node.innerHTML = '<div class="index">' + (index + 1) + '</div>' +
          '<div><div>' + escapeHtml(item.song_name) +
          (item.is_superchat ? '<span class="badge">SC</span>' : '') +
          '</div><div class="song-meta">' + escapeHtml(item.artist) + ' · ' +
          escapeHtml(item.user_name) + '</div></div>';
        queue.appendChild(node);
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
            "song_name": item.song_name,
            "artist": item.artist,
            "user_name": item.user_name,
            "is_superchat": item.is_superchat,
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

    @staticmethod
    def _build_handler(directory: Path):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(directory), **kwargs)

        return Handler
