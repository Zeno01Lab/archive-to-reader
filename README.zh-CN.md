# 剪报夹

Clipping Cabinet · *Archive to Reader*

[English](README.md)

把刷到的有用内容存下来，留到真正有时间时读。文章可以进今晚的 30 分钟队列，学习路线、课件和资源清单则收进按需资料库。归档用 Markdown 保存，浏览器阅读台在电脑本机运行。

## 先试试

准备 Python 3.10 或更新版本。在项目根目录运行，然后打开 [本机阅读台](http://127.0.0.1:8772/)。

```sh
python reader/server.py --demo --port 8772
```

演示使用虚构的 Markdown 内容，阅读进度保存在单独的演示目录。停掉演示服务后，使用自己的资料库。

```sh
python reader/server.py --port 8772
```

正式资料默认放在 `workspace/vault/`。阅读进度、笔记和手动分类保存在 `workspace/.reader/`。如果要并行使用多个资料库，每个库可以指定独立的数据目录和端口。

```sh
python reader/server.py --vault ../my-vault --data-dir ../my-reader-state --port 8773
```

## 手机看到一篇材料，怎么收到电脑

| 入口 | 做法 |
| --- | --- |
| Android 分享菜单 | 安装 [HTTP Shortcuts](https://http-shortcuts.rmy.ch/)，按桥接说明配置自己的收件端。分享文字或链接后，电脑会先把内容写入 SQLite 收件箱。可选的 Codex 投递只指向你在本机配置的固定归档聊天。先试模拟模式。[Android 桥接与手机模板](bridge/README.zh-CN.md) |
| ChatGPT 手机端 Remote | 在支持的设备、账户和工作区中，通过官方设置连接电脑。打开归档聊天，粘贴链接或文字，调用 `$social-archive`。电脑需要在线并可访问本地项目。这个入口可单独使用。[官方手机端演练](https://developers.openai.com/training/walkthroughs/working-on-your-phone) · [帮助中心](https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex) |
| 普通分享、剪贴板或手工导入 | 从任何能分享文字或链接的 App 把内容发给自己。在电脑端复制到 Codex，或者直接用后面的归档命令。用命令记录链接和正文时无需安装 Codex。 |

桥接器显示 `202` 表示电脑收到分享，`queued` 表示 Codex 接收入队请求。归档完成时，应能在目标聊天的输出和 `workspace/vault/Inbox/` 里找到对应 Markdown 文件，并在阅读台刷新后看到卡片。

## 保存一张归档卡

在 Codex 中打开本项目根目录，在归档聊天里调用 `$social-archive`。可指定用户分享的小红书、知乎、B 站、微信公众号文章、X 或 Reddit 链接，也可直接提供文字。Codex 根据当前能合法访问的内容工作，保留来源和阅读范围。只有链接、存在登录限制或只能读取节选时，卡片会保留材料入口及覆盖边界。[归档技能](.agents/skills/social-archive/SKILL.md)

不使用 Codex 时，命令行可保存一个链接：

```sh
python capture.py --title "示例课件" --url https://example.org/lecture --coverage url-only
```

在阅读台点「刷新」，切到「按需查阅」即可找到这张链接卡。

已有正文节选时，把它保存为 UTF-8 文本文件，再导入。可选的 `--summary-file` 将自己写的总结或分析作为另一份 Markdown，与来源卡配对。

```sh
python capture.py --title "示例课程资源" --url https://example.org/resources --file excerpt.md --coverage excerpt --tag 课程
```

来源卡写入 `Inbox/`，配套总结写入 `Summaries/`。重复导入相同内容会返回既有卡片，内容变化会保留新旧快照。分享中有多个链接时，可以用 `--url` 指明主来源。已有独立资料库时，导入和启动阅读台都可用 `--vault` 指向它。

## 集中阅读和整理

阅读台首次打开默认显示英文。在语言菜单选择「简体中文」即可切换；标题、标签和来源正文保留原文。

- **今日阅读**根据主题、标签和阅读状态，从日读候选中选出约 30 分钟的归档。可换一组、继续上次位置，或记录笔记并标记完成。
- **按需查阅**有学习路线、资源清单、学习与参考资料三类。它默认查找所有状态，适合临时找一本书、一门课程或一份讲义。它的资料默认跳过每日队列。
- 标题、已有标签和正文线索用于生成主题和标签。想纠正单篇可点「编辑分类与标签」。同时整理多篇时，在归档书架点击「多选」，勾选材料，选择目标分类，再点「移到按需查阅」。阅读状态随原卡片保留。

### Windows 每日打开

在项目根目录运行以下命令。第一条打开阅读台，第二条为当前 Windows 用户安装每日计划任务，默认使用**系统本地时间 20:00**。可用 `-At 20:30` 改时间。到点打开浏览器，计时在你点「开始阅读」后启动。

```powershell
powershell -File scripts/open-reader.ps1
powershell -File scripts/install-daily-task.ps1
```

计划任务在已登录的用户会话中打开页面。电脑睡眠或关机时无法即时弹出。其他系统可运行上面的 Python 启动命令。

## 本地文件和服务边界

阅读台只监听本机回环地址。纯 Markdown 导入、主题分类、检索和阅读状态均在本机处理。使用 Codex 阅读网页或生成分析时，适用你的 Codex 客户端、账户和组织提供的访问权限及服务条款。原始链接也受平台权限和内容是否可用影响。输入由你主动分享或贴入，桥接器只接收显式提交的文字和链接。

公开项目随附的是纯虚构的演示库。实际归档、浏览器和阅读状态、SQLite 收件记录、桥接凭据和手机的私有导入文件均由使用者本机生成，发布修改时请保留在本地。

## 许可证与致谢

本项目源码采用 MIT 许可证。手机分享模板使用 HTTP Shortcuts 的导入格式，阅读流程参考了几款现有工具，各自的用途、许可证和致谢详见 [第三方来源与许可证](THIRD_PARTY_NOTICES.zh-CN.md)。

[MIT License](LICENSE)
