#!/usr/bin/env python3
"""Lite status agent: uptime, load, and disk only.

The full pack adds service checks, /v1/disk, /v1/ack, and the ack file.
This file is the free subset. Bearer auth still protects /v1/status.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


VERSION = "1.0.0"


class LiteHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def read_uptime_seconds() -> float:
    path = Path("/proc/uptime")
    try:
        return float(path.read_text(encoding="utf-8").split()[0])
    except (OSError, IndexError, ValueError):
        return 0.0


def read_load() -> dict[str, float | None]:
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:
        return {"1": None, "5": None, "15": None}
    return {"1": round(one, 2), "5": round(five, 2), "15": round(fifteen, 2)}


def disk_row(path: str) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"path": path, "used_percent": None, "status": "unknown", "error": exc.__class__.__name__}
    used = usage.total - usage.free
    percent = round((used / usage.total) * 100, 2) if usage.total else 0.0
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": used,
        "free_bytes": usage.free,
        "used_percent": percent,
        "status": "ok",
        "error": "",
    }


def same_secret(presented: str, expected: str) -> bool:
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def build_snapshot(host_label: str, disk_paths: list[str]) -> dict[str, Any]:
    uptime = read_uptime_seconds()
    return {
        "ok": True,
        "version": VERSION,
        "edition": "lite",
        "host_label": host_label,
        "collected_at": utc_now(),
        "uptime_seconds": round(uptime, 2),
        "uptime_human": format_uptime(uptime),
        "load": read_load(),
        "disk": [disk_row(path) for path in disk_paths],
    }


def make_handler(secret: str, host_label: str, disk_paths: list[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "StatusAgentLite/" + VERSION

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/health":
                self._send(200, {"ok": True, "service": "status-agent-lite", "version": VERSION})
                return
            raw = self.headers.get("Authorization") or ""
            scheme, _, value = raw.partition(" ")
            presented = value.strip() if scheme.lower() == "bearer" else ""
            if not same_secret(presented, secret):
                self._send(401, {"ok": False, "error": "unauthorized"})
                return
            if path == "/v1/status":
                self._send(200, build_snapshot(host_label, disk_paths))
                return
            self._send(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            self._send(404, {"ok": False, "error": "not found"})

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lite on-call status agent")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host-label", default="app-01.example.com")
    parser.add_argument("--disk", action="append")
    parser.add_argument("--secret-file", default="")
    args = parser.parse_args(argv)
    if args.secret_file:
        secret = Path(args.secret_file).read_text(encoding="utf-8").strip()
    else:
        secret = os.environ.get("STATUS_AGENT_TOKEN", "").strip()
    if not secret:
        print("Set STATUS_AGENT_TOKEN or pass --secret-file.", file=sys.stderr)
        return 2
    disks = list(args.disk or ["/"])
    server = LiteHTTPServer((args.bind, args.port), make_handler(secret, args.host_label, disks))
    print(f"status-agent-lite listening on {args.bind}:{server.server_address[1]}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
