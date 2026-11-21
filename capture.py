"""Capture user-provided text and source links in a local Markdown vault."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_VAULT = Path(__file__).resolve().parent / "workspace" / "vault"
URL = re.compile(r"https?://[^\s<>\[\]\"'）】]+", re.I)
TRACKING_KEYS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid"}
COVERAGES = ("url-only", "excerpt", "full")


def canonical_url(value: str) -> str:
    """Validate a URL and provide a stable identity without retrieving it."""
    if any(char.isspace() or char == "\\" or ord(char) < 32 for char in value):
        raise ValueError("source URL contains whitespace or invalid characters")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("source URL must not contain credentials")
    if any(char in parsed.hostname for char in '<>"\''):
        raise ValueError("source URL contains an invalid hostname")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    host = f"[{hostname}]" if ":" in hostname else hostname.encode("idna").decode("ascii")
    port = parsed.port
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        host = f"{host}:{port}"
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_KEYS
    ]
    return urlunsplit((scheme, host, parsed.path or "/", urlencode(query), parsed.fragment))


def inferred_url(body: str) -> str:
    """Adopt a URL only when all recognized URLs resolve to one identity."""
    found: dict[str, str] = {}
    for match in URL.finditer(body):
        value = match.group().rstrip(".,;!?，。；！？")
        while value.endswith(")") and value.count(")") > value.count("("):
            value = value[:-1]
        try:
            found.setdefault(canonical_url(value), value)
        except ValueError:
            continue
    return next(iter(found.values())) if len(found) == 1 else ""


def fingerprint(value: str | dict) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def archive_directory(vault: Path, folder: str) -> Path:
    directory = vault / folder
    directory.mkdir(parents=True, exist_ok=True)
    if directory.resolve() != directory:
        raise ValueError(f"capture directory must not be redirected: {folder}")
    return directory


def markdown(fields: dict, body: str) -> str:
    metadata = "\n".join(
        f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()
    )
    return f"---\n{metadata}\n---\n\n{body}"


def write_once(target: Path, text: str) -> bool:
    """Publish a complete file once, without replacing even edited snapshots."""
    if target.is_symlink():
        raise ValueError(f"refusing to use a symbolic link as a snapshot: {target.name}")
    if target.exists():
        if not target.is_file():
            raise ValueError(f"snapshot path is not a file: {target.name}")
        return False
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".capture-", delete=False) as handle:
        staging = Path(handle.name)
        try:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            staging.unlink(missing_ok=True)
            raise
    try:
        if os.name == "nt":
            os.rename(staging, target)  # Windows rename fails if the target exists.
        else:
            os.link(staging, target)
        return True
    except FileExistsError:
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"snapshot path is not a regular file: {target.name}") from None
        return False
    finally:
        staging.unlink(missing_ok=True)


def capture(
    vault: Path, title: str, body: str, source: str | None, coverage: str | None,
    tags: list[str], summary: str | None = None,
) -> dict:
    title = title.strip()
    if not title or len(title.splitlines()) != 1 or "\x00" in title:
        raise ValueError("provide a nonempty single-line title")
    source = source.strip() if source is not None else inferred_url(body)
    source_id = canonical_url(source) if source else ""
    if not source_id and not body.strip():
        raise ValueError("provide source text or one explicit --url")

    if coverage is None:
        coverage = "excerpt" if body.strip() else "url-only"
    if coverage not in COVERAGES:
        raise ValueError("unsupported source coverage")
    if coverage == "url-only" and (body.strip() or not source_id):
        raise ValueError("url-only coverage requires a source link and no source text")
    if coverage != "url-only" and not body.strip():
        raise ValueError("excerpt and full coverage require source text")
    if summary is not None and not summary.strip():
        raise ValueError("summary file must contain some text")

    labels: dict[str, str] = {}
    for label in tags:
        label = label.strip()
        if not label or len(label.splitlines()) != 1 or "\x00" in label:
            raise ValueError("each tag must be a nonempty single line")
        labels.setdefault(label.casefold(), label)
    tags = list(labels.values())
    capture_id = fingerprint(("url:" + source_id) if source_id else ("text:" + body))[:20]
    revision = fingerprint({
        "title": title, "source": source_id, "body": body,
        "coverage": coverage, "tags": tags, "summary": summary,
    })[:20]
    slug = re.sub(r"[\W_]+", "-", unicodedata.normalize("NFKC", title).casefold()).strip("-")[:40]
    name = f"{slug or 'capture'}-{capture_id}-{revision}.md"
    vault = vault.expanduser().resolve()
    inbox = archive_directory(vault, "Inbox")
    snapshot = inbox / name
    relative = f"Inbox/{name}"
    summary_path = f"Summaries/{name}" if summary is not None else None
    prior_version = any(
        path.name != name for path in inbox.glob(f"*-{capture_id}-*.md")
    )
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    fields = {
        "title": title, "date": timestamp, "type": "source-archive",
        "source_coverage": coverage, "capture_id": capture_id, "capture_revision": revision,
        "tags": tags,
    }
    if source:
        fields["source"] = source
    if summary is not None:
        fields["summary_path"] = summary_path
        summary_folder = archive_directory(vault, "Summaries")
        write_once(summary_folder / name, markdown({
            "title": f"Notes on {title}", "date": timestamp, "type": "analysis",
            "source_path": relative,
        }, summary))
    content = body if coverage != "url-only" else "Source link only. No source text was captured.\n"
    written = write_once(snapshot, markdown(fields, content))
    return {
        "status": "new-version" if written and prior_version else ("created" if written else "unchanged"),
        "path": relative, "summary_path": summary_path, "coverage": coverage, "capture_id": capture_id,
    }


def read_utf8(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help="local vault root")
    parser.add_argument("--title", required=True, help="source title or a descriptive title")
    parser.add_argument("--url", help="explicit source link")
    source_text = parser.add_mutually_exclusive_group()
    source_text.add_argument("--file", type=Path, help="read user-provided UTF-8 text from a file")
    source_text.add_argument("--stdin", action="store_true", help="read user-provided UTF-8 text from standard input")
    parser.add_argument("--coverage", choices=COVERAGES, help="coverage of captured source text")
    parser.add_argument("--summary-file", type=Path, help="write separately prepared analysis as a linked note")
    parser.add_argument("--tag", action="append", default=[], help="repeat for each tag")
    args = parser.parse_args()

    try:
        body = read_utf8(args.file) if args.file else ""
        if args.stdin:
            body = sys.stdin.buffer.read().decode("utf-8-sig")
        summary = read_utf8(args.summary_file) if args.summary_file else None
        result = capture(args.vault, args.title, body, args.url, args.coverage, args.tag, summary)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Capture failed: {error}\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
