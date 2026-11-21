# Clipping Cabinet

*Archive to Reader*

[简体中文 · 剪报夹](README.zh-CN.md)

Save the good things you find online, sort them into a library, and come back when you have time to read. Set aside 30 minutes for a reading queue, or file study plans, course materials, and resource lists for the next time you need them. Your archive is Markdown and the reader runs in your computer's browser.

## Try it

Use Python 3.10 or later. From the project root, run the command below and open the [local reader](http://127.0.0.1:8772/).

```sh
python reader/server.py --demo --port 8772
```

The demo uses fictional Markdown and saves reading progress separately. Stop the demo with Ctrl+C before opening your own library on the same port.

```sh
python reader/server.py --port 8772
```

By default, your vault is at `workspace/vault/`. The reader stores progress, notes, and manual categorization in `workspace/.reader/`. To run more than one vault at a time, give each one its own state directory and port.

```sh
python reader/server.py --vault ../my-vault --data-dir ../my-reader-state --port 8773
```

## Send something from your phone

| Method | How it works |
| --- | --- |
| Android share menu | Install [HTTP Shortcuts](https://http-shortcuts.rmy.ch/) and configure the optional bridge. Shared text or links go into a SQLite inbox on your computer. With Codex delivery enabled, the bridge sends them to one Codex thread you configure locally. Try simulation first. [Android bridge and phone template](bridge/README.md) |
| Remote in the ChatGPT mobile app | If your device, account, and workspace support Remote, connect your computer through the official settings. Paste a link or some text into your archive thread and invoke `$social-archive`. Your computer needs to be online with access to the local project. This route works independently of the bridge. [Mobile walkthrough](https://developers.openai.com/training/walkthroughs/working-on-your-phone) · [Help Center](https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex) |
| Share, copy, or import manually | Send yourself text or a link from another app. On the computer, paste it into Codex or use the Python capture command below. The Python command works without Codex. |

A bridge response of `202` means the computer received the submission. A status of `queued` means Codex acknowledged the queue request. To confirm that archiving finished, look for the Markdown file in the Codex thread output and in `workspace/vault/Inbox/`, then refresh the reader.

## Save an archive card

Open this project in Codex and invoke `$social-archive` in a thread you use for archiving. You can supply links from Xiaohongshu, Zhihu, Bilibili, public WeChat articles, X, or Reddit, or paste text directly. Codex works with material it can access with permission and records the source and what it could inspect. For a link, a source behind a login, or an excerpt, the card records that limit. [Archive skill](.agents/skills/social-archive/SKILL.md)

To save a link using Python alone:

```sh
python capture.py --title "Example lecture notes" --url https://example.org/lecture --coverage url-only
```

Refresh the reader and look in the reference library for the example.

If you already have an excerpt, save it as a UTF-8 text file and import it. Use `--summary-file` to link a separate Markdown note containing your own summary or analysis.

```sh
python capture.py --title "Example course resources" --url https://example.org/resources --file excerpt.md --coverage excerpt --tag courses
```

Source cards go in `Inbox/`. Linked analysis goes in `Summaries/`. Importing the same content returns the existing card. When the content changes, the importer keeps both versions. For a share that includes multiple links, `--url` identifies the primary source. You can pass `--vault` to both the capture command and the reader to use your own Markdown directory.

## Read and organize

The reader opens in English on first use. Switch between English and 简体中文 in the language menu. Your saved titles, tags, and source text retain their original wording.

- **Daily Reading** builds a queue of about 30 minutes using topics, tags, and reading status. You can pick a new set, resume reading, leave a note, or mark a card complete.
- **Reference Library** organizes learning paths, resource lists, and study materials. Cards here skip the daily queue by default. You can look them up whether or not you've read them.
- The reader suggests topics and tags from titles, existing tags, and source text. Use **Edit categories and tags** to correct a card's labels. On the archive shelf, choose **Select multiple** and then **Move to reference library** to file several cards at once. Cards keep their reading status when moved.

### Open the reader daily on Windows

From the project root, you can open the reader and install a daily task for the current Windows user.

```powershell
powershell -File scripts/open-reader.ps1
powershell -File scripts/install-daily-task.ps1
```

The task opens the reader at **8:00 p.m. system local time** by default. Pass `-At 20:30` to choose another time. The timer starts when you start the reading session. The task opens the page in the signed-in user's session, so a sleeping or powered-off computer cannot open it at the scheduled time. On other platforms, use the Python start command above.

## Privacy and local storage

The reader listens on the computer's loopback address. Markdown import, categorization, search, and reading state are handled locally. When you ask Codex to browse or analyze a source, your Codex client, account, and workspace permissions and terms apply. The bridge accepts text or links that you explicitly submit.

The release contains a fictional sample vault. Keep your actual archive, browser and reading state, SQLite inbox, bridge credentials, and private phone import file on your own computer when publishing or sharing this project.

## License and credits

The project is released under the [MIT License](LICENSE). The Android template uses the HTTP Shortcuts import format, and several existing tools informed the workflow. [Third-party notices](THIRD_PARTY_NOTICES.md)
