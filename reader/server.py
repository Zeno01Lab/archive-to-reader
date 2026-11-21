"""Local daily reader for the Markdown knowledge vault.

The vault is read-only here. Personal reading state lives in data/state.json.
No third-party packages, network calls, or Markdown execution are used.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs

from references import HEADING, USES, classify_use, reference_search
from topics import TOPICS, classify, frontmatter_tags, validate_manual_tags


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
VAULT = PROJECT / "workspace" / "vault"
DATA = PROJECT / "workspace" / ".reader"
STATE = DATA / "state.json"
HISTORY = DATA / "history"
PORT = 8772
MAX_BODY = 1_000_000
SCAN_TTL_SECONDS = 900
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".md"}
SKIP_DIRS = {"__pycache__", "node_modules", "history", "backup", "backups", "snapshots"}
COMPANION_TYPE = {"summary", "analysis", "research-migration", "总结", "分析", "研究迁移构想"}
FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
STATUS = {"unread", "reading", "done", "later"}
state_lock = threading.RLock()
catalog_lock = threading.RLock()
catalog_cache: dict | None = None
catalog_at = 0.0


def inside_vault(path: Path) -> bool:
    try:
        path.resolve().relative_to(VAULT.resolve())
        return True
    except ValueError:
        return False


def vault_path(rel: str) -> Path:
    if not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/") or "\x00" in rel:
        raise ValueError("无效的知识库路径")
    path = (VAULT / rel).resolve()
    if not inside_vault(path):
        raise ValueError("路径超出知识库")
    if any(part.startswith(".") for part in path.relative_to(VAULT.resolve()).parts):
        raise ValueError("隐藏文件不可通过阅读台访问")
    return path


def split_note(raw: str) -> tuple[dict, str]:
    match = FRONT_RE.match(raw)
    if not match:
        return {}, raw
    fields: dict = {"tags": frontmatter_tags(match.group(1))}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key in {"title", "date", "type", "status", "source", "source_url", "url", "coverage", "source_coverage", "summary_path", "use"}:
            value = value.strip()
            if value.startswith('"'):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    parsed = value.strip('"')
                if isinstance(parsed, str):
                    fields[key] = parsed
            else:
                fields[key] = value.strip("'")
    return fields, raw[match.end():]


def read_note(path: Path) -> tuple[dict, str]:
    return split_note(path.read_text(encoding="utf-8-sig", errors="replace"))


def note_id(rel: str) -> str:
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()[:20]


def note_title(path: Path, meta: dict, body: str) -> str:
    if meta.get("title"):
        return meta["title"]
    heading = HEADING.search(body)
    return heading.group(1).strip() if heading else path.stem


def should_include(path: Path, meta: dict) -> bool:
    if path.name.lower() in {"readme.md", "home.md", "index.md", "agents.md"}:
        return False
    rel = path.relative_to(VAULT)
    return meta.get("type", "").lower() not in COMPANION_TYPE and rel.parts[0].lower() != "summaries"


def scan_notes() -> dict[str, dict]:
    notes: dict[str, dict] = {}
    for current, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in files:
            if filename.startswith(".") or not filename.lower().endswith(".md"):
                continue
            path = Path(current) / filename
            if not inside_vault(path):
                continue
            rel = path.relative_to(VAULT).as_posix()
            try:
                with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
                    head = handle.read(24_000)
                meta, body = split_note(head)
                size = path.stat().st_size
            except (OSError, UnicodeError):
                continue
            notes[rel] = {
                "path": path, "meta": meta, "body": body, "size": size,
                "eligible": should_include(path, meta),
            }
    return notes


def index_pairs(notes: dict[str, dict]) -> dict[str, str]:
    pairs = {}
    for rel, entry in notes.items():
        companion = entry["meta"].get("summary_path")
        if not entry["eligible"] or not companion:
            continue
        try:
            candidate = vault_path(companion).relative_to(VAULT.resolve()).as_posix()
        except ValueError:
            continue
        if candidate in notes and not notes[candidate]["eligible"] and candidate != rel:
            pairs[rel] = candidate
    return pairs


def estimate_minutes(*sizes: int) -> int:
    # A rough Markdown reading estimate; source files are commonly mixed Chinese
    # and English. 1.4 KB/min keeps long source collections from looking short.
    return max(1, min(120, math.ceil(sum(sizes) / 1400)))


def make_catalog() -> dict:
    notes = scan_notes()
    pairs = index_pairs(notes)
    paired_summaries = set(pairs.values())
    items = []
    bodies = {}
    for rel, entry in notes.items():
        if not entry["eligible"] or rel in paired_summaries:
            continue
        meta = entry["meta"]
        body = entry["body"]
        companion_rel = pairs.get(rel, "")
        companion = notes.get(companion_rel)
        source = meta.get("source") or meta.get("source_url") or meta.get("url") or ""
        if not source.lower().startswith(("https://", "http://")):
            source = ""
        title = note_title(entry["path"], meta, body)
        date = meta.get("date") or re.match(r"\d{4}-\d{2}-\d{2}", entry["path"].name)
        if isinstance(date, re.Match):
            date = date.group(0)
        date = str(date or "")[:10]
        label_text = " ".join((meta.get("type", ""), meta.get("status", ""), entry["path"].name))
        source_gap = re.search(r"待补读|仅线索|只存链接", label_text) or re.search(r"原帖.{0,30}待补|原文.{0,30}待补|未取得.{0,20}(?:全文|正文|原文)|仅读到.{0,30}(?:标题|预览)|仅.{0,12}(?:标题|链接|预览)|跳转.{0,15}登录页", body[:1400])
        coverage = meta.get("source_coverage") or meta.get("coverage", "")
        if coverage in {"url-only", "excerpt"} or source_gap:
            readability = "仅保存链接" if coverage == "url-only" else "仅有节选或归档笔记"
        else:
            readability = "归档材料可读"
        kind = meta.get("type", "来源资料")
        use, use_evidence = classify_use(title, kind, body)
        if meta.get("use") in USES:
            use, use_evidence = meta["use"], "归档标注的阅读用途"
        item = {
            "id": note_id(rel), "path": rel, "title": title, "date": date,
            "type": kind, "source": source,
            "summaryPath": companion_rel,
            "summaryTitle": (companion["meta"].get("title") or companion["path"].stem) if companion else "",
            "minutes": estimate_minutes(entry["size"], companion["size"] if companion else 0),
            "readability": readability,
            "coverage": coverage,
            "use": use, "useEvidence": use_evidence,
            **classify(title, meta.get("tags", []), body, rel),
        }
        if use != "daily":
            item["referenceSearch"] = reference_search(body)
        items.append(item)
        bodies[item["id"]] = {"item": item, "bodyPath": rel, "summaryPath": companion_rel}
    items.sort(key=lambda x: (x["date"], x["path"]), reverse=True)
    return {"items": items, "count": len(items), "topics": TOPICS, "_bodies": bodies}


def get_catalog(refresh: bool = False) -> dict:
    global catalog_cache, catalog_at
    with catalog_lock:
        now = dt.datetime.now().timestamp()
        if refresh or catalog_cache is None or now - catalog_at > SCAN_TTL_SECONDS:
            catalog_cache = make_catalog()
            catalog_at = now
        return catalog_cache


def default_state() -> dict:
    return {"schemaVersion": 1, "items": {}}


def canonical(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def revision(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_state() -> tuple[dict, str]:
    if STATE.exists():
        raw = STATE.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    else:
        data = default_state()
        raw = canonical(data)
    if not isinstance(data, dict) or data.get("schemaVersion") != 1 or not isinstance(data.get("items"), dict):
        raise ValueError("阅读状态文件格式无效")
    return data, revision(raw)


@contextlib.contextmanager
def file_lock():
    DATA.mkdir(parents=True, exist_ok=True)
    lock_path = DATA / ".state.lock"
    with open(lock_path, "a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def apply_changes(data: dict, changes: dict, known_ids: set[str]) -> dict:
    if not isinstance(changes, dict) or len(changes) > 1000:
        raise ValueError("变更记录无效")
    updated = json.loads(json.dumps(data))
    for item_id, change in changes.items():
        allowed = {"status", "note", "progress", "topicOverride", "tagsOverride", "useOverride"}
        if item_id not in known_ids or not isinstance(change, dict) or not change or set(change) - allowed:
            raise ValueError("条目或字段无效")
        current = updated["items"].get(item_id, {})
        if "status" in change:
            if change["status"] not in STATUS:
                raise ValueError("阅读状态无效")
            current["status"] = change["status"]
        if "note" in change:
            if not isinstance(change["note"], str) or len(change["note"]) > 20000:
                raise ValueError("笔记过长或格式无效")
            current["note"] = change["note"]
        if "progress" in change:
            val = change["progress"]
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not 0 <= val <= 100:
                raise ValueError("阅读进度无效")
            current["progress"] = round(float(val), 1)
        if "topicOverride" in change:
            value = change["topicOverride"]
            if value is None:
                current.pop("topicOverride", None)
            elif value in TOPICS:
                current["topicOverride"] = value
            else:
                raise ValueError("主题无效")
        if "tagsOverride" in change:
            value = change["tagsOverride"]
            if value is None:
                current.pop("tagsOverride", None)
            else:
                current["tagsOverride"] = validate_manual_tags(value)
        if "useOverride" in change:
            value = change["useOverride"]
            if value is None:
                current.pop("useOverride", None)
            elif value in USES:
                current["useOverride"] = value
            else:
                raise ValueError("阅读用途无效")
        current["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        updated["items"][item_id] = current
    return updated


def write_state(data: dict, old_raw: bytes | None) -> tuple[dict, str]:
    DATA.mkdir(parents=True, exist_ok=True)
    if old_raw is not None:
        HISTORY.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (HISTORY / f"state-{stamp}.json").write_bytes(old_raw)
    raw = canonical(data)
    fd, name = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=DATA)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, STATE)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return data, revision(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "ArchiveToReader/0.1"

    def log_message(self, fmt: str, *args) -> None:
        pass

    def headers_common(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'")

    def send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.headers_common(content_type, len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status: int, data: dict) -> None:
        self.send_bytes(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def error_json(self, status: int, message: str, **extra) -> None:
        self.send_json(status, {"error": message, **extra})

    def local_request(self) -> bool:
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "").lower()
        if host not in allowed:
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin.lower() not in {f"http://{value}" for value in allowed}:
            return False
        return True

    def do_GET(self) -> None:
        if not self.local_request():
            return self.error_json(403, "仅允许本机阅读")
        split = urlsplit(self.path)
        path = split.path
        try:
            if path == "/api/health":
                return self.send_json(200, {"app": "archive-to-reader", "vault": str(VAULT), "dataDir": str(DATA)})
            if path == "/api/catalog":
                data = get_catalog(refresh=parse_qs(split.query).get("refresh") == ["1"])
                return self.send_json(200, {"items": data["items"], "count": data["count"], "topics": data["topics"]})
            if path == "/api/item":
                item_id = parse_qs(split.query).get("id", [""])[0]
                result = get_catalog()["_bodies"].get(item_id)
                if not result:
                    return self.error_json(404, "未找到阅读条目")
                body = read_note(vault_path(result["bodyPath"]))[1]
                summary = read_note(vault_path(result["summaryPath"]))[1] if result["summaryPath"] else ""
                return self.send_json(200, {"item": result["item"], "body": body, "summaryBody": summary})
            if path == "/api/state":
                data, rev = read_state()
                return self.send_json(200, {"revision": rev, "state": data})
            if path.startswith("/asset/"):
                rel = unquote(path[len("/asset/"):])
                file = vault_path(rel)
                if file.suffix.lower() not in ASSET_EXTENSIONS or not file.is_file():
                    return self.error_json(404, "附件不存在或格式不支持")
                mime = "text/plain; charset=utf-8" if file.suffix.lower() == ".md" else (mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                return self.send_bytes(200, file.read_bytes(), mime)
            if path in STATIC:
                file = ROOT / STATIC[path]
                if not file.is_file():
                    return self.error_json(404, "页面文件尚未建立")
                mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}[file.suffix]
                return self.send_bytes(200, file.read_bytes(), mime + "; charset=utf-8")
            return self.error_json(404, "页面不存在")
        except ValueError as exc:
            return self.error_json(400, str(exc))
        except (OSError, json.JSONDecodeError) as exc:
            return self.error_json(500, str(exc))

    def do_POST(self) -> None:
        if not self.local_request():
            return self.error_json(403, "仅允许本机阅读")
        if urlsplit(self.path).path != "/api/state":
            return self.error_json(404, "接口不存在")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            return self.error_json(415, "只接受 JSON 阅读进度")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.error_json(413, "请求过大或为空")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("revision"), str):
                raise ValueError("请求结构无效")
            with state_lock, file_lock():
                data, rev = read_state()
                if rev != payload["revision"]:
                    return self.error_json(409, "阅读进度已由另一窗口更新，请刷新后重试", revision=rev, state=data)
                known = set(get_catalog()["_bodies"])
                updated = apply_changes(data, payload.get("changes"), known)
                old_raw = STATE.read_bytes() if STATE.exists() else None
                updated, new_rev = write_state(updated, old_raw)
            return self.send_json(200, {"revision": new_rev, "state": updated})
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            return self.error_json(400, str(exc))


def main() -> None:
    global VAULT, DATA, STATE, HISTORY
    parser = argparse.ArgumentParser(description="本地归档阅读台")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--catalog-stats", action="store_true")
    parser.add_argument("--vault", type=Path, help="Markdown 资料目录")
    parser.add_argument("--data-dir", type=Path, help="阅读记录和备份目录")
    parser.add_argument("--demo", action="store_true", help="使用内置示例和独立阅读记录")
    args = parser.parse_args()
    if args.demo and (args.vault or args.data_dir):
        parser.error("--demo 使用预设的资料及数据目录")
    VAULT = (PROJECT / "examples" / "vault" if args.demo else (args.vault or VAULT)).resolve()
    DATA = (PROJECT / "workspace" / ".reader-demo" if args.demo else (args.data_dir or DATA)).resolve()
    if DATA.is_relative_to(VAULT) or VAULT.is_relative_to(DATA):
        parser.error("资料目录与阅读记录目录应相互独立")
    if not VAULT.is_dir():
        if args.vault or args.demo:
            parser.error("指定的资料目录不存在")
        VAULT.mkdir(parents=True)
    STATE = DATA / "state.json"
    HISTORY = DATA / "history"
    if args.catalog_stats:
        catalog = get_catalog(refresh=True)
        from collections import Counter
        counts = Counter(x["path"].split("/", 1)[0] for x in catalog["items"])
        print(json.dumps({
            "count": catalog["count"], "roots": counts,
            "paired": sum(bool(x["summaryPath"]) for x in catalog["items"]),
            "uses": Counter(x["use"] for x in catalog["items"]),
        }, ensure_ascii=False, indent=2))
        return
    if not 1 <= args.port <= 65535:
        parser.error("port 必须在 1..65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Daily reader: http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
