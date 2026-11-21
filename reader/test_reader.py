import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ReaderTests(unittest.TestCase):
    def test_demo_has_separate_source_and_analysis_and_all_four_uses(self):
        with patch.object(server, "VAULT", server.PROJECT / "examples" / "vault"):
            cards = server.make_catalog()["items"]
        self.assertEqual(len(cards), 6)
        self.assertEqual({item["use"] for item in cards}, set(server.USES))
        paired = [item for item in cards if item["summaryPath"]]
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0]["coverage"], "excerpt")
        self.assertEqual(paired[0]["summaryPath"], "Summaries/trail-map-notes.md")
        resource = next(item for item in cards if item["use"] == "resources")
        self.assertIn("阳台光照观察表", resource["referenceSearch"])
        self.assertNotIn("https://example.org", resource["referenceSearch"])

    def test_capture_output_can_be_indexed_with_separate_summary(self):
        import sys
        from subprocess import run

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "summary.md"
            summary.write_text("Separate invented analysis.", encoding="utf-8")
            vault = root / "local-vault"
            captured = run(
                [
                    sys.executable, "-B", str(server.PROJECT / "capture.py"), "--vault", str(vault),
                    "--title", "Demo course notes", "--url", "https://example.org/demo/notes",
                    "--coverage", "excerpt", "--stdin", "--summary-file", str(summary),
                ],
                input=b"One invented excerpt.", capture_output=True, check=True,
            )
            with patch.object(server, "VAULT", vault):
                cards = server.make_catalog()["items"]
                self.assertEqual(len(cards), 1)
                card = cards[0]
                self.assertEqual(server.read_note(server.vault_path(card["summaryPath"]))[1].strip(),
                                 "Separate invented analysis.")
            self.assertIn(b'"created"', captured.stdout)
            self.assertEqual(card["source"], "https://example.org/demo/notes")
            self.assertEqual(card["coverage"], "excerpt")

    def test_bulk_changes_are_atomic_and_preserve_reading_state(self):
        initial = {"schemaVersion": 1, "items": {
            "a": {"status": "reading", "note": "Demo note", "progress": 29},
            "b": {"status": "done", "progress": 100},
        }}
        changes = {item: {"useOverride": "materials"} for item in initial["items"]}
        updated = server.apply_changes(initial, changes, {"a", "b"})
        for item, fields in initial["items"].items():
            for key, value in fields.items():
                self.assertEqual(updated["items"][item][key], value)
            self.assertNotIn("useOverride", fields)
            self.assertEqual(updated["items"][item]["useOverride"], "materials")
        with self.assertRaises(ValueError):
            server.apply_changes(initial, {**changes, "missing": {"useOverride": "resources"}}, {"a", "b"})
        self.assertNotIn("useOverride", initial["items"]["a"])

    def test_reader_asset_paths_stay_in_visible_vault(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, "VAULT", Path(tmp)):
            for path in ("../outside.md", ".private/clip.md", "Inbox/../../outside.md"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    server.vault_path(path)


if __name__ == "__main__":
    unittest.main()
