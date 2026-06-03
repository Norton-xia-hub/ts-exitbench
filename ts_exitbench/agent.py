from __future__ import annotations

import argparse
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import load_config

CHUNK = b"0" * 65536
MAX_DURATION_SECONDS = 120


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "ts-exitbench-agent/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def authorized(self) -> bool:
        token = getattr(self.server, "token", "")
        if not token:
            return False
        return self.headers.get("Authorization") == f"Bearer {token}"

    def reject_unauthorized(self) -> None:
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.end_headers()
        self.wfile.write(b"unauthorized")

    def do_GET(self) -> None:
        if not self.authorized():
            self.reject_unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.write_json({"ok": True, "service": "ts-exitbench-agent"})
            return
        if parsed.path == "/download":
            params = parse_qs(parsed.query)
            duration = clamp_duration(params.get("duration", ["10"])[0])
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                try:
                    self.wfile.write(CHUNK)
                except (BrokenPipeError, ConnectionResetError):
                    break
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.authorized():
            self.reject_unauthorized()
            return
        parsed = urlparse(self.path)
        if parsed.path != "/upload":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        total = 0
        started = time.monotonic()
        try:
            while True:
                chunk = self.rfile.read(65536)
                if not chunk:
                    break
                total += len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            return
        elapsed = max(time.monotonic() - started, 0.001)
        self.write_json({
            "ok": True,
            "bytes": total,
            "elapsed_seconds": elapsed,
            "mbps": bytes_to_mbps(total, elapsed),
        })

    def write_json(self, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def clamp_duration(raw: str) -> int:
    try:
        value = int(float(raw))
    except ValueError:
        value = 10
    return max(1, min(value, MAX_DURATION_SECONDS))


def bytes_to_mbps(num_bytes: int, elapsed: float) -> float:
    return round((num_bytes * 8) / elapsed / 1_000_000, 2)


def run_agent(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    agent = config["agent"]
    host = args.host or agent.get("host", "0.0.0.0")
    port = int(args.port or agent.get("port", 51234))
    token = args.token or agent.get("token", "")
    if not token or token.startswith("change-me"):
        raise SystemExit("Set a strong agent.token in config before running the agent.")
    server = ThreadingHTTPServer((host, port), AgentHandler)
    server.token = token  # type: ignore[attr-defined]
    server.quiet = args.quiet  # type: ignore[attr-defined]
    print(f"ts-exitbench agent listening on {host}:{port}")
    server.serve_forever()
    return 0
