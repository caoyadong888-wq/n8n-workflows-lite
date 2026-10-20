#!/usr/bin/env python3
"""Disk-only probe. The full pack adds TLS, HTTP, and the daily summary."""

from __future__ import annotations

import argparse
import json
import shutil
import sys


def classify_percent(percent: float, warn: float, crit: float) -> str:
    if percent >= crit:
        return "crit"
    if percent >= warn:
        return "warn"
    return "ok"


def probe_disk(paths: list[str], warn: float, crit: float) -> dict:
    if not (0 <= warn <= crit <= 100):
        raise SystemExit("need 0 <= warn <= crit <= 100")
    items = []
    for path in paths:
        usage = shutil.disk_usage(path)
        percent = (usage.used / usage.total * 100.0) if usage.total else 0.0
        status = classify_percent(percent, warn, crit)
        items.append(
            {
                "path": path,
                "used_percent": round(percent, 2),
                "status": status,
            }
        )
    rank = {"ok": 0, "warn": 1, "crit": 2}
    status = max((item["status"] for item in items), key=lambda item: rank[item])
    lines = [f"{item['path']} {item['used_percent']}% {item['status']}" for item in items]
    return {
        "check": "disk",
        "status": status,
        "subject": f"Disk {status}",
        "message": f"Disk check is {status} (warn {warn:g}%, crit {crit:g}%).\n" + "\n".join(lines),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe.py")
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--warn", type=float, default=80)
    parser.add_argument("--crit", type=float, default=90)
    args = parser.parse_args(argv)
    json.dump(probe_disk(args.path, args.warn, args.crit), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
