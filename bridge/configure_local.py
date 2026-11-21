"""Generate local bridge configuration and an optional Android import ZIP."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import zipfile

from server import DEFAULT_CONFIG, ROOT, canonical_id, network_settings


def write_private(path: Path, data: bytes, *, replace=False):
    flags = os.O_CREAT | os.O_WRONLY | (os.O_TRUNC if replace else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def android_import(host: str, port: int, token: str, output: Path):
    template = ROOT / "phone" / "shortcuts.template.json"
    data = json.loads(template.read_text(encoding="utf-8"))
    replacements = {"pb_endpoint": f"http://{host}:{port}", "pb_token": token}
    for variable in data["variables"]:
        if variable["key"] in replacements:
            variable["value"] = replacements[variable["key"]]
    # The export includes the token. Set owner-only permissions where supported.
    fd = os.open(output, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("shortcuts.json", json.dumps(data, ensure_ascii=False, indent=2))


def configure(args):
    host, port, _ = network_settings(args.host, args.port, args.trusted_lan)
    wants_dispatch = args.thread_id is not None or args.codex_executable is not None
    if wants_dispatch and not (args.thread_id and args.codex_executable):
        raise ValueError("provide both --thread-id and --codex-executable for a dispatch configuration")
    config = {
        "host": host,
        "port": port,
        "token_file": "bridge-token.txt",
        "db_path": "inbox.sqlite3",
        "demo_db_path": "demo-inbox.sqlite3",
        "workspace": str(args.workspace.resolve()),
    }
    if wants_dispatch:
        config["thread_id"] = canonical_id(args.thread_id)
        config["codex_executable"] = str(args.codex_executable.resolve(strict=True))
    if args.trusted_lan:
        config["trusted_lan"] = args.trusted_lan
    target = args.config.resolve()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists() and not args.replace_config:
        raise ValueError("config exists; use --replace-config to update it and keep the token")
    token_file = target.parent / config["token_file"]
    if not token_file.exists():
        write_private(token_file, secrets.token_urlsafe(32).encode("ascii"))
    token = token_file.read_text(encoding="ascii").strip()
    write_private(target, (json.dumps(config, indent=2) + "\n").encode(), replace=args.replace_config)
    if args.trusted_lan:
        android_import(host, port, token, target.parent / "android-import.zip")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workspace", type=Path, default=ROOT.parent)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--trusted-lan", metavar="PRIVATE_CIDR")
    parser.add_argument("--thread-id", metavar="UUID")
    parser.add_argument("--codex-executable", type=Path)
    parser.add_argument("--replace-config", action="store_true")
    args = parser.parse_args()
    try:
        target = configure(args)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Cannot configure bridge: {error}\n")
    print(f"Local config ready at {target}.")
    if args.trusted_lan:
        print("Android import generated in the private config directory.")
    print("Start server.py for dry run, or use --dispatch after configuring a dedicated Codex thread.")


if __name__ == "__main__":
    main()
