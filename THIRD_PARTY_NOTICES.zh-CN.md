# 第三方来源与许可证

[English](THIRD_PARTY_NOTICES.md)

[根目录 MIT 许可证](LICENSE)适用于本项目编写并发布的源码、文档、配置和虚构示例。链接所指的第三方软件、服务和内容由各自的权利人授权。本页记录公开源码包使用的接口、外部工具和设计参考。

## 手机分享模板

[HTTP Shortcuts](https://github.com/Waboodoo/HTTP-Shortcuts) 由 Roland Meyer 开发，采用 MIT 许可证。随包的 [shortcuts.template.json](bridge/phone/shortcuts.template.json) 是本项目编写的导入配置，使用 HTTP Shortcuts 的字段和变量格式，定义两个将分享文字或剪贴板文字发送到桥接器的操作。

- 参考 [官方导入文档](https://http-shortcuts.rmy.ch/import-export)与[上游模型及默认值](https://github.com/Waboodoo/HTTP-Shortcuts/tree/dcd9f69bbae9dc7abc03346e6f2d1bb02811690c/HTTPShortcuts/app/src/main/kotlin/ch/rmy/android/http_shortcuts/import_export)。兼容版本依据 [v4.9.0](https://github.com/Waboodoo/HTTP-Shortcuts/releases/tag/v4.9.0) 的[导入代码](https://github.com/Waboodoo/HTTP-Shortcuts/blob/bfe1bb7c576d1de838039d67c719088945d3cb83/HTTPShortcuts/app/src/main/kotlin/ch/rmy/android/http_shortcuts/import_export/ImportExport.kt)核对，使用格式 92，兼容版本为 90。
- 随包附上 [HTTP Shortcuts 的完整 MIT 许可证和原版权声明](LICENSES/HTTP-Shortcuts-MIT.txt)，原件见 [v4.9.0 对应提交的 LICENCE](https://github.com/Waboodoo/HTTP-Shortcuts/blob/bfe1bb7c576d1de838039d67c719088945d3cb83/LICENCE)。安卓 App 需要另行安装。发布包仅分发本项目的兼容配置，未分发上游 APK、Kotlin 实现或图标。

## 外部运行与测试工具

下表所列工具在用户设备或 CI 运行机上另行提供，源码包没有附带它们的源码、二进制、运行时或字体文件。

| 工具 | 本项目如何使用 | 上游许可 |
| --- | --- | --- |
| Python 3.10+ 与标准库 | 运行导入命令、阅读台和可选桥接器。源码无第三方 Python 包依赖。 | Python Software Foundation 许可证及随发行版提供的其他声明。[Python 3.10](https://docs.python.org/3.10/license.html) · [Python 3.13](https://docs.python.org/3.13/license.html) |
| SQLite | 桥接器经 Python 标准库的 `sqlite3` 接口保存收件记录。 | SQLite 核心由作者贡献至公有领域。[SQLite 版权说明](https://sqlite.org/copyright.html) |
| Codex CLI | 可选桥接调用已安装且支持相应命令的客户端。GitHub 上的开源 CLI 许可与 ChatGPT 桌面端、Remote 和模型服务的使用条款各自独立。 | 开源 CLI 仓库采用 Apache-2.0。[Codex CLI 许可证](https://github.com/openai/codex/blob/main/LICENSE) |
| GitHub Actions | CI 通过 `uses:` 引用 `actions/checkout@v6`、`actions/setup-python@v6`、`actions/setup-node@v5`。 | 三个 Action 均为 MIT。[checkout](https://github.com/actions/checkout/blob/v6/LICENSE) · [setup-python](https://github.com/actions/setup-python/blob/v6/LICENSE) · [setup-node](https://github.com/actions/setup-node/blob/v5/LICENSE) |
| Node.js 22 | CI 用 `node --check` 检查浏览器脚本。使用阅读台本身无需安装 Node.js。 | Node.js 核心的 MIT 许可及附带组件的声明。[Node.js 22 许可证](https://github.com/nodejs/node/blob/v22.x/LICENSE) |
| Windows PowerShell、任务计划程序和浏览器 | 启动脚本调用用户系统已有的工具，界面使用浏览器原生 HTML、CSS 和 JavaScript。 | 随各系统或应用发行。 |
| 可选本机字体 | CSS 只声明字体回退名称，浏览器使用设备已有字体。 | 列出的开源字体采用 SIL Open Font License 1.1。[Source Han Serif](https://github.com/adobe-fonts/source-han-serif/blob/release/LICENSE.txt) · [Noto Serif CJK](https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE) · [Cascadia Code](https://github.com/microsoft/cascadia-code/blob/main/LICENSE) |

## 阅读流程设计参考

- **Cubox** 的收藏夹、标签与智能列表，启发了主主题和跨主题标签的组织方式。[官方指南](https://help.cubox.pro/manage/organize/)
- **Readwise Reader** 的筛选视图和自动标签，启发了按主题或标签组成阅读队列。[筛选视图](https://docs.readwise.io/reader/docs/faqs/filtered-views) · [Ghostreader](https://docs.readwise.io/reader/docs/faqs/ghostreader)
- **Raindrop.io** 的建议与人工纠正，启发了逐篇修改和恢复自动分类的入口。[官方说明](https://blog.raindrop.io/ai-suggestions-5a85762ae176/)
- **wallabag** 的打标规则，启发了按照标题、标签和正文线索在本机生成分类。[规则文档](https://doc.wallabag.org/user/configuration/tagging_rules/) · [wallabag 源码的 MIT 许可证](https://github.com/wallabag/wallabag/blob/master/COPYING.md)

这些产品用于讨论工作流程。发布包中的阅读台自行实现，未分发上述产品的代码、界面资源或商标素材。示例内容为项目虚构，链接使用 [IANA 保留域名](https://www.iana.org/help/example-domains)。使用者实际归档的文章、图片和其他材料仍适用原来源的权利及条款。

## 后续分发

发布本项目的复制件时保留 [LICENSE](LICENSE)、本页和随附的第三方许可。将来若把其他项目的代码、字体、图标或二进制放进分发包，先核对所用版本的许可证并保留该版本要求的版权、许可及其他声明，再更新[打包清单](scripts/build-release.py)。
