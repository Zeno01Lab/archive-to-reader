"""Build a source release from an explicit list of distributable files."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
FILES = (
    ".agents/skills/social-archive/SKILL.md",
    ".github/workflows/check.yml",
    ".gitignore",
    "LICENSE",
    "LICENSES/HTTP-Shortcuts-MIT.txt",
    "README.md",
    "README.zh-CN.md",
    "THIRD_PARTY_NOTICES.md",
    "THIRD_PARTY_NOTICES.zh-CN.md",
    "bridge/.gitignore",
    "bridge/README.md",
    "bridge/README.zh-CN.md",
    "bridge/configure_local.py",
    "bridge/phone/shortcuts.template.json",
    "bridge/server.py",
    "bridge/tests/test_server.py",
    "capture.py",
    "examples/vault/Inbox/data-visualization-notes.md",
    "examples/vault/Inbox/drawing-a-trail-map.md",
    "examples/vault/Inbox/learning-roadmap.md",
    "examples/vault/Inbox/one-signal-per-chart.md",
    "examples/vault/Inbox/public-library-walkthrough.md",
    "examples/vault/Inbox/reading-resource-list.md",
    "examples/vault/Summaries/trail-map-notes.md",
    "reader/app.js",
    "reader/index.html",
    "reader/references.py",
    "reader/server.py",
    "reader/styles.css",
    "reader/test_reader.py",
    "reader/topics.py",
    "scripts/build-release.py",
    "scripts/install-daily-task.ps1",
    "scripts/open-reader.ps1",
    "test_capture.py",
)


def build(output: Path) -> None:
    inputs = []
    for name in FILES:
        source = ROOT / name
        if source.resolve() != source or not source.is_file():
            raise ValueError(f"Missing file or unexpected link: {name}")
        data = source.read_bytes()
        data.decode("utf-8-sig")
        inputs.append((name, data))
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as release:
        for name, data in sorted(inputs):
            info = ZipInfo(f"archive-to-reader/{name}", (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            release.writestr(info, data, compress_type=ZIP_DEFLATED)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"{len(inputs)} source and fixture files")
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path to a new release ZIP")
    build(parser.parse_args().output)
