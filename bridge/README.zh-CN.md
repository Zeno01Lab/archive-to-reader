# 从 Android 分享到剪报夹

[English](README.md) · [剪报夹项目说明](../README.zh-CN.md)

桥接器可选。它接收 Android HTTP Shortcuts 的分享文字或前台剪贴板文字，将请求写入电脑上的 SQLite 收件箱。开启投递后，桥接器仅向配置的一个 Codex 聊天入队，交由项目内的 `$social-archive` 保存归档卡。

## 在电脑上试跑

使用 Python 3.10 或以上版本。PowerShell 进入项目的 `bridge` 目录后执行。

```
python configure_local.py
python server.py
```

默认监听 `127.0.0.1:18765`，以模拟模式运行。另开 PowerShell，在同一个目录发送一条虚构文字。

```powershell
$bridgeToken = (Get-Content -Raw .private/bridge-token.txt).Trim()
$bridgeID = [guid]::NewGuid().ToString()
$bridgeHeaders = @{ Authorization = "Bearer $bridgeToken"; 'X-Request-ID' = $bridgeID }
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18765/inbox' -Headers $bridgeHeaders -ContentType 'text/plain; charset=utf-8' -Body 'Demo reading material: https://example.com/'
Invoke-RestMethod -Uri "http://127.0.0.1:18765/status/$bridgeID" -Headers $bridgeHeaders
```

第一次 `POST` 返回 202 表示电脑收件。查询状态最终应显示 `simulated`。演示数据保存在独立数据库里。按 Ctrl+C 停止桥接器。

## Android 接入

电脑和手机应在你信任的同一私有网络。此方式使用明文 HTTP，Bearer 凭据及分享文字不适合在共享、校园或公共 Wi-Fi 传输。避免端口映射与互联网暴露。桥接器只绑定一个明确的私有 IPv4 地址，并限制来源 CIDR。Windows 防火墙如果已允许该入口，则可直连。程序不会改变防火墙或路由器配置。

1. 查明电脑在该网络上的私有 IPv4 和对应 CIDR。停止正在运行的桥接器，再执行下面的命令，将占位值替换为自己的值。

   ```powershell
   python configure_local.py --replace-config --host '<电脑的私有IPv4>' --trusted-lan '<信任的私有IPv4网段/CIDR>'
   python server.py
   ```

2. 从 [HTTP Shortcuts 官方项目](https://http-shortcuts.rmy.ch/) 安装应用。通过可信的本地文件传输方式，将 `.private/android-import.zip` 拷到手机。在 HTTP Shortcuts 使用“导入/导出 → 从文件导入”，选择合并导入。
3. 帖子 App 分享文字时选择 HTTP Shortcuts，再选择「Share to Codex / 分享给 Codex」。也可以先复制帖子文字，在 HTTP Shortcuts 中点击「Send copied text / 复制后发给 Codex」。先用虚构文字验收。

私有 ZIP 内含凭据。不要把它、`.private` 目录或实际收件记录放入公开仓库。电脑地址变化时，停止服务并重新生成该电脑的 ZIP。再次配置会沿用本地 token。若 token 泄露，停止服务并另建私有配置目录生成新 token，再配对手机。SQLite 收件包含完整分享原文，按个人资料保护。

## 启用 Codex 投递

需要支持 `codex queue --thread … --message …` 的原生 Codex 客户端。在项目工作区内打开一个专门的归档聊天，从客户端确认它的 UUID，并在该聊天里允许使用本项目的 `$social-archive`。不同 Codex 发行版本可能没有 `queue` 子命令。启动时会检查原生可执行文件响应的版本及 `queue --help`。检查失败时可继续使用模拟模式。

停止演示服务，按自己的网络与 CLI 安装信息重新配置。

```powershell
python configure_local.py --replace-config --host '<电脑的私有IPv4>' --trusted-lan '<私有网段/CIDR>' --thread-id '<归档聊天UUID>' --codex-executable '<原生Codex可执行文件绝对路径>'
python server.py --dispatch
```

默认 Codex 工作区为 `bridge` 的父目录。配置中的目标聊天固定，手机请求没有目标字段。投递数据库一旦绑定聊天，就拒绝在另一个聊天下继续使用。想换聊天时可在项目内用新私有目录指定 `--config`。真实分享原文以 UUID 命名存入同目录的 `inbox`，交给 `$social-archive` 作为数据读取。桥接器以参数数组调用 CLI。

`queued` 表示收到指定聊天的 Codex 入队回执。要确认归档，核对目标聊天输出以及 `workspace/vault/Inbox` 中生成的归档卡。`uncertain` 表示缺少可靠投递回执，处理时先核对目标聊天。相同请求 ID 与相同原文可安全查询或重试。手机手动重新点执行会生成新 ID。手机端需要电脑在线。入口接受 64 KiB 以内的 UTF-8 文字与链接。

## 模板与测试

公开的 [手机模板](phone/shortcuts.template.json) 使用 HTTP Shortcuts v4.9.0 的导入格式 92，兼容版本为 90，提供两种文字入口。HTTP Shortcuts 由 Roland Meyer 开发，采用 MIT 许可证，需要单独安装。项目随包提供兼容配置、[上游原版权与许可全文](../LICENSES/HTTP-Shortcuts-MIT.txt)和[导入格式的参考出处](../THIRD_PARTY_NOTICES.zh-CN.md#手机分享模板)。

在 `bridge` 中运行 `python -B -m unittest discover -s tests -v` 可验证本机收件、权限、去重、模拟与固定聊天投递。测试使用虚构内容和模拟的 CLI 回执。
