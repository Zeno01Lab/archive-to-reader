# Third-party notices

[简体中文](THIRD_PARTY_NOTICES.zh-CN.md)

The [root MIT license](LICENSE) covers the source code, documentation, configuration, and fictional examples written and released for this project. The respective rights holders license the third-party software, services, and content linked below.

## Phone share template

[HTTP Shortcuts](https://github.com/Waboodoo/HTTP-Shortcuts) is developed by Roland Meyer and licensed under MIT. This project's [shortcuts.template.json](bridge/phone/shortcuts.template.json) uses its import fields and variable format to define two actions that send shared or clipboard text to the bridge.

- The template was checked against the [official import documentation](https://http-shortcuts.rmy.ch/import-export), [upstream import models and defaults](https://github.com/Waboodoo/HTTP-Shortcuts/tree/dcd9f69bbae9dc7abc03346e6f2d1bb02811690c/HTTPShortcuts/app/src/main/kotlin/ch/rmy/android/http_shortcuts/import_export), and [import code for v4.9.0](https://github.com/Waboodoo/HTTP-Shortcuts/blob/bfe1bb7c576d1de838039d67c719088945d3cb83/HTTPShortcuts/app/src/main/kotlin/ch/rmy/android/http_shortcuts/import_export/ImportExport.kt). It uses import format 92 and compatibility version 90. [HTTP Shortcuts v4.9.0 release](https://github.com/Waboodoo/HTTP-Shortcuts/releases/tag/v4.9.0)
- Install the Android app separately. The package distributes the project's compatible configuration and the [full upstream MIT license and original copyright notice](LICENSES/HTTP-Shortcuts-MIT.txt). It does not distribute the upstream APK, Kotlin implementation, or icons. [Original license at the v4.9.0 commit](https://github.com/Waboodoo/HTTP-Shortcuts/blob/bfe1bb7c576d1de838039d67c719088945d3cb83/LICENCE)

## External runtime and testing tools

Users or CI runners provide these tools separately. The source release contains none of their source code, binaries, runtimes, or fonts.

| Tool | Role in this project | Upstream terms |
| --- | --- | --- |
| Python 3.10+ and standard library | Runs capture, the reader, and the optional bridge. The project requires no third-party Python packages. | Python Software Foundation License and notices accompanying the distribution. [Python 3.10](https://docs.python.org/3.10/license.html) · [Python 3.13](https://docs.python.org/3.13/license.html) |
| SQLite | Stores bridge inbox entries through Python's standard `sqlite3` module. | The authors have dedicated the SQLite core to the public domain. [SQLite copyright](https://sqlite.org/copyright.html) |
| Codex CLI | Optional bridge delivery uses an installed client with the required command. ChatGPT desktop, Remote, and model services have separate terms from the open-source CLI repository. | The open-source CLI repository uses Apache-2.0. [Codex CLI license](https://github.com/openai/codex/blob/main/LICENSE) |
| GitHub Actions | CI references `actions/checkout@v6`, `actions/setup-python@v6`, and `actions/setup-node@v5` through `uses:`. | All three use MIT. [checkout](https://github.com/actions/checkout/blob/v6/LICENSE) · [setup-python](https://github.com/actions/setup-python/blob/v6/LICENSE) · [setup-node](https://github.com/actions/setup-node/blob/v5/LICENSE) |
| Node.js 22 | CI runs `node --check` on the browser script. The reader does not require Node.js. | MIT for Node.js core, with separate notices for included components. [Node.js 22 license](https://github.com/nodejs/node/blob/v22.x/LICENSE) |
| Windows PowerShell, Task Scheduler, and web browser | Launch and scheduling scripts use system tools. The interface uses native HTML, CSS, and JavaScript. | Provided under the respective system or application terms. |
| Optional local fonts | CSS declares fallback font names. The browser uses fonts installed on the device. | The named open-source fonts use SIL Open Font License 1.1. [Source Han Serif](https://github.com/adobe-fonts/source-han-serif/blob/release/LICENSE.txt) · [Noto Serif CJK](https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE) · [Cascadia Code](https://github.com/microsoft/cascadia-code/blob/main/LICENSE) |

## Reading workflow references

- **Cubox** folders, tags, and smart lists informed the use of a primary topic and tags that can span topics. [Official organization guide](https://help.cubox.pro/manage/organize/)
- **Readwise Reader** filtered views and automatic tagging informed the topic and tag filters for the reading queue. [Filtered views](https://docs.readwise.io/reader/docs/faqs/filtered-views) · [Ghostreader](https://docs.readwise.io/reader/docs/faqs/ghostreader)
- **Raindrop.io** suggestions and manual corrections informed the controls for editing or restoring a card's automatically assigned labels. [Official introduction](https://blog.raindrop.io/ai-suggestions-5a85762ae176/)
- **wallabag** tagging rules informed local categorization based on titles, tags, and source text. [Tagging rules](https://doc.wallabag.org/user/configuration/tagging_rules/) · [wallabag MIT license](https://github.com/wallabag/wallabag/blob/master/COPYING.md)

The reader in this release has its own implementation. The release contains no code, interface assets, or brand assets from these reference products. The examples are fictional and use [IANA reserved domains](https://www.iana.org/help/example-domains). Real articles, images, and other materials that users archive remain subject to the rights and terms of their original sources.

## Redistribution

When redistributing this project, retain [LICENSE](LICENSE), this notice, and the included third-party license. If you add code, fonts, icons, or binaries from another project, check the license for the exact version, retain the required notices, and update the [release manifest](scripts/build-release.py).
