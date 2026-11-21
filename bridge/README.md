# Android share bridge

[Clipping Cabinet](../README.md) · [简体中文](README.zh-CN.md)

The optional bridge receives Android share text or clipboard text obtained when you run an HTTP Shortcuts action. It stores each request in a SQLite inbox on your computer. With delivery enabled, it queues submissions in one configured Codex thread, where the project's `$social-archive` skill can write archive cards.

## Try it on your computer

Use Python 3.10 or later. In PowerShell, run these commands from the project's `bridge` directory.

```powershell
python configure_local.py
python server.py
```

By default, the bridge listens on `127.0.0.1:18765` and simulates delivery. Open a second PowerShell window in the same directory and submit fictional text.

```powershell
$bridgeToken = (Get-Content -Raw .private/bridge-token.txt).Trim()
$bridgeID = [guid]::NewGuid().ToString()
$bridgeHeaders = @{ Authorization = "Bearer $bridgeToken"; 'X-Request-ID' = $bridgeID }
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18765/inbox' -Headers $bridgeHeaders -ContentType 'text/plain; charset=utf-8' -Body 'Demo reading material: https://example.com/'
Invoke-RestMethod -Uri "http://127.0.0.1:18765/status/$bridgeID" -Headers $bridgeHeaders
```

The first `POST` returns `202` when the computer receives it. The status should eventually be `simulated`. The demo saves its data in a separate database. Press Ctrl+C to stop the bridge.

## Connect an Android phone

Put your computer and phone on the same private network that you trust. The bridge uses plain HTTP. Keep the bearer credential and shared text off shared, public, and campus Wi-Fi. Avoid internet exposure and port forwarding. The bridge binds to a specific private IPv4 address and accepts requests only from the configured source CIDR. On Windows it can accept phone requests when the firewall already allows them. The program does not modify your firewall or router.

1. Find the computer's private IPv4 address and the corresponding network CIDR. Stop the bridge if it is running, then replace the placeholders and run:

   ```powershell
   python configure_local.py --replace-config --host '<computer-private-ipv4>' --trusted-lan '<trusted-private-ipv4-cidr>'
   python server.py
   ```

2. Install [HTTP Shortcuts](https://http-shortcuts.rmy.ch/) on Android. Use a trusted local transfer method to copy `.private/android-import.zip` to the phone. In HTTP Shortcuts, use **Import / Export → Import from file** and merge the import.
3. In another app's Android share menu, select HTTP Shortcuts and choose **Share to Codex / 分享给 Codex**. Or copy the share text and run **Send copied text / 复制后发给 Codex** from HTTP Shortcuts. Try fictional text first.

The private ZIP contains credentials. Keep it, the `.private` directory, and real inbox entries out of public repositories. If the computer's address changes, stop the bridge and regenerate the ZIP for the new address. Reconfiguring the same private directory reuses its token. If the token is exposed, stop the bridge, create a new private configuration directory with a new token, and pair the phone again. The SQLite inbox stores the full submitted text, so protect it as you would your other personal files.

## Enable Codex delivery

Use a native Codex client that supports `codex queue --thread … --message …`. Open a dedicated thread in the project workspace, find its UUID in your client, and allow that thread to use this project's `$social-archive` skill. Some Codex distributions may not have a `queue` subcommand. On startup, the bridge checks the native executable's version and `queue --help`. You can still use simulation if either check fails.

Stop the demo bridge and configure it with your network and CLI details.

```powershell
python configure_local.py --replace-config --host '<computer-private-ipv4>' --trusted-lan '<trusted-private-ipv4-cidr>' --thread-id '<archive-thread-uuid>' --codex-executable '<absolute-path-to-native-codex>'
python server.py --dispatch
```

By default, the Codex workspace is the parent directory of `bridge`. The configured target thread is fixed, and phone requests cannot specify a destination. After a delivery database is bound to a thread, the bridge refuses to reuse it for another thread. To change threads, specify a new private configuration location within the project with `--config`. The bridge saves real submissions as UUID-named files in the adjacent `inbox` for `$social-archive` to read as source material. It invokes the CLI with an argument array.

- `queued` means the bridge received an acknowledgment that Codex queued the submission in the configured thread. Confirm archiving by checking the thread output and the Markdown card in `workspace/vault/Inbox`.
- `uncertain` means the bridge could not confirm delivery. Check the target thread first. You can safely query or retry a request with the same request ID and body. Manually running a shortcut again creates a new request ID.
- The computer must be online when the phone submits. The bridge accepts UTF-8 text or links up to 64 KiB.

## Template and tests

The [phone template](phone/shortcuts.template.json) uses HTTP Shortcuts v4.9.0 import format 92, with compatibility version 90. It defines two text actions. HTTP Shortcuts is a separate MIT-licensed Android app by Roland Meyer. [Upstream copyright and license](../LICENSES/HTTP-Shortcuts-MIT.txt) · [Import format references](../THIRD_PARTY_NOTICES.md#phone-share-template)

Run `python -B -m unittest discover -s tests -v` from `bridge` to check local receipt, access controls, deduplication, simulation, and fixed-thread delivery. The tests use fictional text and mock CLI responses.
