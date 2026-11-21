"""Offline tests only: no installed Codex process is ever executed."""
import ipaddress
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
import zipfile

import server as bridge
from configure_local import android_import

# All network addresses below are loopback or invented fixtures. Tests do not
# connect anywhere except the ephemeral loopback listener.
TOKEN = "test-only-pairing-token-" + "x" * 32
THREAD = str(uuid.uuid4())


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).resolve().parent
        self.tmp = tempfile.TemporaryDirectory(dir=self.test_root)
        self.store = bridge.Store(Path(self.tmp.name) / "inbox.sqlite")
        self.calls = []

        def runner(command, **kwargs):
            self.calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0,
                f"Queued message {uuid.uuid4()} for thread {THREAD}.\n", "")

        self.app = bridge.App(self.store, TOKEN, Path("mock-codex.exe"), THREAD, dry_run=False,
                              workspace=Path(self.tmp.name), runner=runner)
        self.server = bridge.Server(("127.0.0.1", 0), self.app, ipaddress.ip_network("127.0.0.1/32"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.assertTrue(Path(self.tmp.name).resolve().is_relative_to(self.test_root))
        self.tmp.cleanup()

    def request(self, text="hello", request_id=None, auth=TOKEN, origin=None, path="/inbox"):
        headers = {"Content-Type": "text/plain; charset=utf-8",
                   "X-Request-ID": request_id or str(uuid.uuid4())}
        if auth is not None:
            headers["Authorization"] = "Bearer " + auth
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path, data=text.encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_auth_and_browser_origin_do_not_enqueue(self):
        self.assertEqual(self.request(auth=None)[0], 401)
        self.assertEqual(self.request(auth="incorrect")[0], 401)
        self.assertEqual(self.request(origin="http://untrusted.example")[0], 403)
        self.assertIsNone(self.store.claim())

    def test_unicode_body_is_preserved_and_command_uses_argument_array(self):
        text = "整理：芯片测试 https://example.com/?a=1&b=2\n`$() & literal"
        code, job = self.request(text)
        self.assertEqual(code, 202)
        self.assertEqual(job["state"], "received")
        self.assertNotIn("text", job)
        self.assertTrue(self.app.process_one())
        command, kwargs = self.calls[0]
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(command[:5], ["mock-codex.exe", "queue", "--thread",
                                      THREAD, "--message"])
        self.assertNotIn(text, command[5])
        self.assertIn("$social-archive", command[5])
        source = Path(self.tmp.name) / "inbox" / (job["id"] + ".txt")
        self.assertEqual(source.read_text(encoding="utf-8"), text)
        self.assertEqual(kwargs["cwd"], Path(self.tmp.name))
        self.assertEqual(self.store.status(job["id"])["state"], "queued")
        self.assertFalse(self.app.process_one())

    def test_same_id_is_idempotent_and_changed_content_conflicts(self):
        request_id = str(uuid.uuid4())
        self.assertEqual(self.request("one", request_id)[0], 202)
        code, duplicate = self.request("one", request_id)
        self.assertEqual(code, 200)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.request("two", request_id)[0], 409)
        self.app.process_one()
        self.app.process_one()
        self.assertEqual(len(self.calls), 1)

    def test_invalid_and_oversized_bodies(self):
        self.assertEqual(self.request(" ")[0], 400)
        self.assertEqual(self.request("nul\x00text")[0], 400)
        self.assertEqual(self.request(request_id="../../arbitrary")[0], 400)
        self.assertEqual(self.request("x" * (bridge.MAX_BODY + 1))[0], 413)
        self.assertIsNone(self.store.claim())

    def test_timeout_stays_uncertain_and_is_not_automatically_retried(self):
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        self.app.runner = timeout
        _, job = self.request()
        self.app.process_one()
        self.assertEqual(self.store.status(job["id"])["error"], "queue_timeout")
        self.assertEqual(self.store.status(job["id"])["state"], "uncertain")
        self.assertFalse(self.app.process_one())

    def test_exit_zero_without_correct_receipt_is_uncertain(self):
        self.app.runner = lambda *a, **k: subprocess.CompletedProcess(a, 0, "OK", "")
        _, job = self.request()
        self.app.process_one()
        self.assertEqual(self.store.status(job["id"])["state"], "uncertain")

    def test_restart_recovers_received_but_does_not_repeat_inflight(self):
        one, two = str(uuid.uuid4()), str(uuid.uuid4())
        self.store.submit(one, "claimed")
        self.assertEqual(self.store.claim()["id"], one)
        self.store.submit(two, "still waiting")
        recovered = bridge.Store(self.store.path)
        self.assertEqual(recovered.status(one)["state"], "uncertain")
        self.assertEqual(recovered.claim()["id"], two)
        self.assertIsNone(recovered.claim())

    def test_dry_run_never_calls_codex(self):
        self.app.dry_run = True
        _, job = self.request()
        self.app.process_one()
        self.assertEqual(self.store.status(job["id"])["state"], "simulated")
        self.assertEqual(self.calls, [])

    def test_long_text_uses_a_saved_source_not_an_oversized_command(self):
        text = "测" * 7000
        _, job = self.request(text)
        self.app.process_one()
        source = Path(self.tmp.name) / "inbox" / (job["id"] + ".txt")
        self.assertEqual(source.read_text(encoding="utf-8"), text)
        self.assertLess(len(self.calls[0][0][5]), 1000)

    def test_dispatch_database_is_bound_to_fixed_chat(self):
        bridge.Store(self.store.path, THREAD)
        bridge.Store(self.store.path, THREAD)
        with self.assertRaises(ValueError):
            bridge.Store(self.store.path, str(uuid.uuid4()))

    def test_loopback_or_explicit_private_subnet_only(self):
        self.assertEqual(bridge.network_settings("127.0.0.1", 18765)[0], "127.0.0.1")
        self.assertEqual(bridge.network_settings("10.51.44.7", 18765, "10.51.44.0/24")[2].prefixlen, 24)
        for host, cidr in (("0.0.0.0", None), ("192.168.77.4", None), ("203.0.113.7", "203.0.113.0/24"),
                           ("10.51.44.7", "10.51.43.0/24")):
            with self.subTest(host=host, cidr=cidr), self.assertRaises(ValueError):
                bridge.network_settings(host, 18765, cidr)

    def test_android_import_contains_only_configured_endpoint_and_token(self):
        path = Path(self.tmp.name) / "fixture.zip"
        android_import("10.55.44.3", 18765, TOKEN, path)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.namelist(), ["shortcuts.json"])
            block = json.loads(archive.read("shortcuts.json"))
        variables = {variable["key"]: variable for variable in block["variables"]}
        self.assertEqual(variables["pb_endpoint"]["value"], "http://10.55.44.3:18765")
        self.assertEqual(variables["pb_token"]["value"], TOKEN)
        self.assertTrue(variables["pb_token"]["isExcludeValueFromExport"])
        self.assertEqual(len(block["categories"][0]["shortcuts"]), 2)

    def test_verify_native_queue_support_without_dispatch(self):
        path = Path(self.tmp.name) / "fixture.exe"
        path.touch()
        executed = []
        def runner(command, **kwargs):
            executed.append(command)
            output = "codex-cli 1.0" if command[1] == "--version" else "Usage: queue --thread --message"
            return subprocess.CompletedProcess(command, 0, output, "")
        self.assertEqual(bridge.verified_codex(path.resolve(), self.tmp.name, runner), path.resolve())
        self.assertEqual([command[1:] for command in executed], [["--version"], ["queue", "--help"]])

    def test_health_and_authenticated_status(self):
        _, job = self.request("private body")
        with urllib.request.urlopen(self.base + "/health", timeout=5) as response:
            self.assertNotIn(TOKEN, response.read().decode())
        request = urllib.request.Request(self.base + "/status/" + job["id"],
                                        headers={"Authorization": "Bearer " + TOKEN})
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
        self.assertEqual(result["id"], job["id"])
        self.assertNotIn("text", result)

    def test_pairing_is_never_served(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(self.base + "/pair/fixture", timeout=5)
        self.assertEqual(denied.exception.code, 401)
        request = urllib.request.Request(self.base + "/pair/fixture",
                                         headers={"Authorization": "Bearer " + TOKEN})
        with self.assertRaises(urllib.error.HTTPError) as disabled:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(disabled.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
