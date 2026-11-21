from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from capture import capture


class CaptureTests(unittest.TestCase):
    def test_url_deduplication_preserves_user_edits_and_changed_capture(self):
        with TemporaryDirectory() as root:
            vault = Path(root)
            first = capture(
                vault, "Example topic", "First excerpt.\r\n", "https://EXAMPLE.org/notes?utm_source=demo",
                "excerpt", ["Example"],
            )
            self.assertEqual(first["status"], "created")
            snapshot = vault / first["path"]
            raw = snapshot.read_bytes()
            self.assertTrue(raw.endswith(b"First excerpt.\r\n"))
            snapshot.write_bytes(raw + b"Local correction\n")

            same = capture(
                vault, "Example topic", "First excerpt.\r\n", "https://example.org/notes",
                "excerpt", ["Example"],
            )
            self.assertEqual(same["status"], "unchanged")
            self.assertEqual(same["path"], first["path"])
            self.assertTrue(snapshot.read_bytes().endswith(b"Local correction\n"))

            revision = capture(
                vault, "Example topic", "Expanded synthetic text.", "https://example.org/notes",
                "full", ["Example"], "Example analysis.",
            )
            self.assertEqual(revision["status"], "new-version")
            self.assertEqual(revision["capture_id"], first["capture_id"])
            self.assertNotEqual(revision["path"], first["path"])
            self.assertEqual(
                (vault / revision["summary_path"]).read_bytes().split(b"\n---\n\n")[1],
                b"Example analysis.",
            )
            new_snapshot = (vault / revision["path"]).read_bytes()
            expected_pair = f'summary_path: "{revision["summary_path"]}"'.encode()
            self.assertIn(expected_pair, new_snapshot)

    def test_ambiguous_urls_keep_stable_payload_identity_and_text(self):
        with TemporaryDirectory() as root:
            vault = Path(root)
            clip = "See https://example.com/first and https://example.org/second."
            first = capture(vault, "Two links", clip, None, None, [])
            second = capture(vault, "Two links", clip, None, None, [])
            raw = (vault / first["path"]).read_bytes()
            self.assertEqual(first["path"], second["path"])
            self.assertNotIn(b"\nsource:", raw)
            self.assertTrue(raw.endswith(clip.encode()))

    def test_url_only_cannot_claim_full_coverage(self):
        with TemporaryDirectory() as root:
            vault = Path(root)
            with self.assertRaises(ValueError):
                capture(vault, "Example", "", "https://example.org/post", "full", [])
            result = capture(vault, "Example", "", "https://example.org/post", None, [])
            self.assertEqual(result["coverage"], "url-only")
            self.assertTrue((vault / result["path"]).exists())


if __name__ == "__main__":
    unittest.main()
