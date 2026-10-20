#!/usr/bin/env python3
"""Dedupe, robots.txt, and polite preview helper for the public-page digest.

The n8n workflow fetches pages. This module decides whether a row is new,
changed, or already sent, and it refuses private paths and non-public schemes.
Standard library only. It does not crawl a site on its own.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


USER_AGENT = "PageDigestBot/1.0 (+https://example.com/bot)"
CSV_COLUMNS = ["fetched_at", "classification", "url", "title", "excerpt", "content_hash"]
DENY_SEGMENTS = {
    "login",
    "signin",
    "sign-in",
    "account",
    "admin",
    "users",
    "profile",
    "wp-admin",
    "private",
    "oauth",
    "checkout",
    "register",
}
MAX_EXCERPT = 280
MAX_BODY = 1_000_000


def normalize_text(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host
    if port and not (
        (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def content_hash(title: str, excerpt: str) -> str:
    blob = normalize_text(title) + "\n" + normalize_text(excerpt)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def path_segments(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def assess_url(url: str) -> dict[str, Any]:
    parts = urlsplit((url or "").strip())
    reasons: list[str] = []
    if parts.scheme not in {"http", "https"}:
        reasons.append("scheme")
    if parts.username or parts.password:
        reasons.append("userinfo")
    host = (parts.hostname or "").lower()
    if not host or " " in host:
        reasons.append("host")
    blocked = [seg for seg in path_segments(parts.path or "/") if seg.lower() in DENY_SEGMENTS]
    if blocked:
        reasons.append("path:" + blocked[0].lower())
    canonical = ""
    if not reasons:
        canonical = canonical_url(url)
    return {"ok": not reasons, "reasons": reasons, "canonical": canonical}


def _rule_matches(path: str, rule: str) -> bool:
    pattern = rule.strip()
    if not pattern:
        return False
    anchor_end = pattern.endswith("$")
    if anchor_end:
        pattern = pattern[:-1]
    # A single trailing star means "this prefix". Other stars match across a segment.
    if pattern.endswith("*") and pattern.count("*") == 1:
        return path.startswith(pattern[:-1])
    if "*" in pattern:
        import re

        escaped = re.escape(pattern).replace(r"\*", ".*")
        if anchor_end:
            return re.fullmatch(escaped, path) is not None
        return re.match(escaped, path) is not None
    if anchor_end:
        return path == pattern
    return path.startswith(pattern)


def path_allowed(path: str, rules: dict[str, Any]) -> bool:
    """Longest matching Allow or Disallow wins. Allow wins a length tie."""
    path = path or "/"
    best_len = -1
    best_allow: bool | None = None
    for kind, allow in (("disallow", False), ("allow", True)):
        for rule in rules.get(kind) or []:
            if not _rule_matches(path, rule):
                continue
            length = len(rule.rstrip("*$"))
            if length > best_len or (length == best_len and allow):
                best_len = length
                best_allow = allow
    if best_allow is None:
        return True
    return best_allow


def parse_robots(text: str, user_agent: str = "PageDigestBot") -> dict[str, Any]:
    """Pick the group whose user-agent token matches, else the star group."""
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def start() -> dict[str, Any]:
        return {"agents": [], "allow": [], "disallow": [], "crawl_delay": None}

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            if not line and current and current["agents"]:
                groups.append(current)
                current = None
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if current is None or (current["allow"] or current["disallow"] or current["crawl_delay"] is not None):
                if current and current["agents"]:
                    groups.append(current)
                current = start()
            current["agents"].append(value)
            continue
        if current is None:
            continue
        if key == "allow":
            current["allow"].append(value)
        elif key == "disallow":
            current["disallow"].append(value)
        elif key == "crawl-delay":
            try:
                current["crawl_delay"] = float(value.split()[0])
            except (ValueError, IndexError):
                current["crawl_delay"] = None
    if current and current["agents"]:
        groups.append(current)

    product = user_agent.split("/", 1)[0].strip().lower() or "pagedigestbot"
    specific = [
        g
        for g in groups
        if any(a.lower() not in {"", "*"} and product.startswith(a.lower()) for a in g["agents"])
    ]
    if specific:
        specific.sort(key=lambda g: max(len(a) for a in g["agents"]), reverse=True)
        chosen = specific[0]
        matched = "agent"
    else:
        stars = [g for g in groups if any(a.strip() == "*" for a in g["agents"])]
        chosen = stars[0] if stars else {"allow": [], "disallow": [], "crawl_delay": None}
        matched = "star" if stars else "none"
    return {
        "allow": list(chosen.get("allow") or []),
        "disallow": [item for item in (chosen.get("disallow") or []) if item != ""],
        "crawl_delay": chosen.get("crawl_delay"),
        "matched": matched,
    }


def polite_delay(rules: dict[str, Any], default: float = 2.0) -> float:
    raw = rules.get("crawl_delay")
    delay = default if raw is None else float(raw)
    return max(1.0, min(delay, 30.0))


def decide_fetch(url: str, robots_text: str, user_agent: str = "PageDigestBot") -> dict[str, Any]:
    policy = assess_url(url)
    rules = parse_robots(robots_text, user_agent=user_agent)
    path = urlsplit(url).path or "/"
    robots_ok = path_allowed(path, rules) if policy["ok"] else False
    reason = ""
    if not policy["ok"]:
        reason = "policy"
        robots_ok = False
    elif not robots_ok:
        reason = "robots"
    return {
        "allowed": bool(policy["ok"] and robots_ok),
        "reason": reason,
        "delay_seconds": polite_delay(rules),
        "matched": rules["matched"],
        "canonical": policy.get("canonical") or "",
        "policy_reasons": policy["reasons"],
    }


def empty_state() -> dict[str, Any]:
    return {"seen": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(payload, dict) or not isinstance(payload.get("seen"), dict):
        return empty_state()
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def classify_record(state: dict[str, Any], record: dict[str, str]) -> dict[str, Any]:
    policy = assess_url(record.get("url", ""))
    title = " ".join((record.get("title") or "").split())[:180]
    excerpt = " ".join((record.get("excerpt") or "").split())[:MAX_EXCERPT]
    fetched_at = record.get("fetched_at") or ""
    if not policy["ok"]:
        return {
            "ok": True,
            "classification": "skipped",
            "url": record.get("url") or "",
            "title": title,
            "excerpt": excerpt,
            "fetched_at": fetched_at,
            "content_hash": "",
            "reasons": policy["reasons"],
        }
    url = policy["canonical"]
    digest = content_hash(title, excerpt)
    previous = state["seen"].get(url)
    if previous is None:
        classification = "new"
    elif previous.get("content_hash") != digest:
        classification = "changed"
    else:
        classification = "seen"
    return {
        "ok": True,
        "classification": classification,
        "url": url,
        "title": title,
        "excerpt": excerpt,
        "fetched_at": fetched_at,
        "content_hash": digest,
        "reasons": [],
    }


def remember(state: dict[str, Any], row: dict[str, Any]) -> None:
    if row.get("classification") not in {"new", "changed", "seen"}:
        return
    url = row["url"]
    slot = state["seen"].setdefault(url, {"first_seen": row.get("fetched_at") or ""})
    slot["url"] = url
    slot["title"] = row.get("title") or ""
    slot["content_hash"] = row.get("content_hash") or ""
    slot["last_seen"] = row.get("fetched_at") or slot.get("last_seen") or ""
    if row.get("classification") == "new" and not slot.get("first_seen"):
        slot["first_seen"] = row.get("fetched_at") or ""


def append_outbox(path: Path, row: dict[str, Any]) -> None:
    if row.get("classification") not in {"new", "changed"}:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in CSV_COLUMNS})


def load_pages(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("pages file must be a non-empty JSON list")
    rows = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or "url" not in item:
            raise ValueError(f"page {index} needs a url")
        policy = assess_url(str(item["url"]))
        rows.append(
            {
                "url": policy["canonical"] or str(item["url"]).strip(),
                "note": str(item.get("note") or ""),
                "allowed_by_policy": policy["ok"],
                "reasons": policy["reasons"],
            }
        )
    return rows


def render_digest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    interesting = [row for row in rows if row.get("classification") in {"new", "changed"}]
    lines = []
    for row in interesting:
        lines.append(f"- {row.get('title') or row.get('url')}")
        lines.append(f"  {row.get('url')}")
        if row.get("excerpt"):
            lines.append(f"  {row.get('excerpt')}")
    count = len(interesting)
    subject = f"Public page digest ({count})"
    body = "\n".join(lines) if lines else "No public page changes."
    return {"ok": True, "count": count, "subject": subject, "message": body, "rows": interesting}


def decode_record(encoded: str) -> dict[str, str]:
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("record-b64 is not a JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("record-b64 is not a JSON object")
    return {key: "" if payload.get(key) is None else str(payload.get(key)) for key in ("url", "title", "excerpt", "fetched_at")}


class _TextPull(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.paragraph_parts: list[str] = []
        self._in_title = False
        self._in_paragraph = False
        self._got_paragraph = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "title":
            self._in_title = True
        elif tag == "p" and not self._got_paragraph:
            self._in_paragraph = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
            return
        if tag == "title":
            self._in_title = False
        elif tag == "p" and self._in_paragraph:
            self._in_paragraph = False
            self._got_paragraph = True

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
        elif self._in_paragraph:
            self.paragraph_parts.append(data)


def extract_public_text(html: str) -> dict[str, str]:
    parser = _TextPull()
    parser.feed(html)
    parser.close()
    title = " ".join("".join(parser.title_parts).split())
    excerpt = " ".join("".join(parser.paragraph_parts).split())[:MAX_EXCERPT]
    return {"title": title, "excerpt": excerpt}


def _read_limited(response: Any) -> str:
    raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError("response is larger than 1 MB")
    charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def fetch_text(url: str, timeout: float = 15.0) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final = response.geturl()
        if not assess_url(final)["ok"]:
            raise ValueError("redirect target is not a public http(s) page")
        return _read_limited(response)


def preview_page(
    url: str,
    robots_text: str,
    state: dict[str, Any],
    fetched_at: str,
    html: str | None = None,
) -> dict[str, Any]:
    decision = decide_fetch(url, robots_text)
    if not decision["allowed"]:
        return {"ok": True, "classification": "skipped", "decision": decision, "url": url}
    if html is None:
        html = fetch_text(decision["canonical"] or url)
    extracted = extract_public_text(html)
    row = classify_record(
        state,
        {
            "url": url,
            "title": extracted["title"],
            "excerpt": extracted["excerpt"],
            "fetched_at": fetched_at,
        },
    )
    row["decision"] = decision
    return row


def _print_json(payload: dict[str, Any] | list[Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_load_pages(args: argparse.Namespace) -> int:
    try:
        rows = load_pages(Path(args.file))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    blocked = [row for row in rows if not row["allowed_by_policy"]]
    if blocked:
        _print_json({"ok": False, "error": "page list failed the public-url policy", "pages": rows})
        return 2
    _print_json(rows)
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    try:
        record = decode_record(args.record_b64)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    state_path = Path(args.state)
    state = load_state(state_path)
    row = classify_record(state, record)
    if not args.dry_run and row["classification"] in {"new", "changed", "seen"}:
        remember(state, row)
        save_state(state_path, state)
    if args.outbox and row["classification"] in {"new", "changed"} and not args.dry_run:
        append_outbox(Path(args.outbox), row)
    _print_json(row)
    return 0


def cmd_robots(args: argparse.Namespace) -> int:
    text = Path(args.robots_file).read_text(encoding="utf-8")
    _print_json(decide_fetch(args.url, text, user_agent=args.agent))
    return 0


def cmd_append_csv(args: argparse.Namespace) -> int:
    try:
        record = decode_record(args.record_b64)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    # The classify JSON is a superset. Extra keys survive decode_record only for the four fields,
    # so callers that need classification pass a record that already includes those four plus
    # we accept an optional classification via a second decode of the full object.
    full = json.loads(base64.b64decode(args.record_b64.encode("ascii")).decode("utf-8"))
    row = {
        "fetched_at": record.get("fetched_at", ""),
        "classification": str(full.get("classification") or ""),
        "url": record.get("url", ""),
        "title": record.get("title", ""),
        "excerpt": record.get("excerpt", ""),
        "content_hash": str(full.get("content_hash") or ""),
    }
    append_csv(Path(args.file), row)
    _print_json({"ok": True, "file": args.file, "url": row["url"]})
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    path = Path(args.outbox)
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    report = render_digest(rows)
    if not args.keep and path.exists():
        log_path = path.with_name("digest-log.jsonl")
        with log_path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        path.write_text("", encoding="utf-8")
    _print_json({key: report[key] for key in ("ok", "count", "subject", "message")})
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    robots_text = ""
    if args.robots_file:
        robots_text = Path(args.robots_file).read_text(encoding="utf-8")
    elif args.robots_url:
        robots_text = fetch_text(args.robots_url, timeout=args.timeout)
    decision = decide_fetch(args.url, robots_text, user_agent="PageDigestBot")
    if not decision["allowed"]:
        _print_json({"ok": True, "classification": "skipped", "decision": decision})
        return 0
    if not args.no_wait:
        time.sleep(min(decision["delay_seconds"], args.max_wait))
    state_path = Path(args.state)
    state = load_state(state_path)
    html = Path(args.html_file).read_text(encoding="utf-8") if args.html_file else None
    if html is None:
        html = fetch_text(decision["canonical"] or args.url, timeout=args.timeout)
    row = preview_page(args.url, robots_text, state, args.fetched_at or _iso_now(), html=html)
    if row.get("classification") in {"new", "changed", "seen"} and not args.dry_run:
        remember(state, row)
        save_state(state_path, state)
    _print_json(row)
    return 0


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Public-page digest dedupe helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    load = sub.add_parser("load-pages")
    load.add_argument("--file", required=True)
    load.set_defaults(func=cmd_load_pages)

    classify = sub.add_parser("classify")
    classify.add_argument("--state", required=True)
    classify.add_argument("--record-b64", required=True)
    classify.add_argument("--outbox", default="")
    classify.add_argument("--dry-run", action="store_true")
    classify.set_defaults(func=cmd_classify)

    robots = sub.add_parser("robots-check")
    robots.add_argument("--robots-file", required=True)
    robots.add_argument("--url", required=True)
    robots.add_argument("--agent", default="PageDigestBot")
    robots.set_defaults(func=cmd_robots)

    csv_cmd = sub.add_parser("append-csv")
    csv_cmd.add_argument("--file", required=True)
    csv_cmd.add_argument("--record-b64", required=True)
    csv_cmd.set_defaults(func=cmd_append_csv)

    render = sub.add_parser("render-digest")
    render.add_argument("--outbox", required=True)
    render.add_argument("--keep", action="store_true")
    render.set_defaults(func=cmd_render)

    preview = sub.add_parser("preview")
    preview.add_argument("--url", required=True)
    preview.add_argument("--robots-file", default="")
    preview.add_argument("--robots-url", default="")
    preview.add_argument("--html-file", default="")
    preview.add_argument("--state", default="")
    preview.add_argument("--fetched-at", default="")
    preview.add_argument("--no-wait", action="store_true")
    preview.add_argument("--max-wait", type=float, default=2.0)
    preview.add_argument("--timeout", type=float, default=15.0)
    preview.add_argument("--dry-run", action="store_true")
    preview.set_defaults(func=cmd_preview)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "preview" and not args.state:
        print("preview requires --state", file=sys.stderr)
        return 2
    try:
        return int(args.func(args))
    except urllib.error.URLError as exc:
        print(f"fetch failed: {exc.reason}", file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
