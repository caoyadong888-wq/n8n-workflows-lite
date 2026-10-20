#!/usr/bin/env python3
"""Lite ticket intake helper.

Validates one ticket and appends it to a JSONL store. The full pack adds
backup freshness, git backup, and the weekly report on top of this step.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITIES = ("p1", "p2", "p3", "p4")
SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
NAME_RE = re.compile(r"^[A-Za-z0-9._ \-]{2,40}$")


def validate_ticket(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    title = str(payload.get("title") or "").strip()
    if len(title) < 4 or len(title) > 140:
        errors.append("title must be 4-140 characters")
    severity = str(payload.get("severity") or "").strip().lower()
    if severity not in SEVERITIES:
        errors.append("severity must be p1, p2, p3, or p4")
    service = str(payload.get("service") or "").strip().lower()
    if not SERVICE_RE.fullmatch(service):
        errors.append("service must be a short slug such as checkout")
    detail = str(payload.get("detail") or "").strip()
    if len(detail) < 8 or len(detail) > 4000:
        errors.append("detail must be 8-4000 characters")
    reporter = str(payload.get("reporter") or "").strip()
    if reporter and not (EMAIL_RE.fullmatch(reporter) or NAME_RE.fullmatch(reporter)):
        errors.append("reporter must be a short name or an email address")
    return errors


def remember_ticket(payload: dict[str, Any], store: Path, now: datetime | None = None) -> dict[str, Any]:
    errors = validate_ticket(payload)
    if errors:
        return {
            "ok": False,
            "status": "rejected",
            "errors": errors,
            "subject": "Ticket rejected",
            "message": "; ".join(errors),
        }
    moment = now or datetime.now(timezone.utc)
    store.parent.mkdir(parents=True, exist_ok=True)
    existing = 0
    if store.exists():
        existing = sum(1 for line in store.read_text(encoding="utf-8").splitlines() if line.strip())
    record = {
        "id": f"T-{moment.strftime('%Y%m%d')}-{existing + 1:04d}",
        "created_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "severity": str(payload["severity"]).strip().lower(),
        "service": str(payload["service"]).strip().lower(),
        "title": str(payload["title"]).strip(),
        "detail": str(payload["detail"]).strip(),
        "reporter": str(payload.get("reporter") or "ops@example.com").strip(),
    }
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "ok": True,
        "status": "stored",
        "errors": [],
        "subject": f"Ticket {record['id']} {record['severity']} {record['service']}",
        "message": f"{record['title']}\n{record['detail']}",
        **record,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lite ticket intake")
    parser.add_argument("cmd", choices=["remember"])
    parser.add_argument("--store", required=True)
    parser.add_argument("--record-b64", required=True)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(base64.b64decode(args.record_b64.encode("ascii"), validate=True).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("record-b64 is not a JSON object")
        report = remember_ticket(payload, Path(args.store))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"ok": False, "status": "error", "subject": "Ticket helper failed", "message": str(exc), "errors": [str(exc)]}
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
