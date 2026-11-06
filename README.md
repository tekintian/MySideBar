> **This is the release copy.**
>
> You are reading the `main` branch. It is generated automatically: on every release, CI mirrors this plugin's source directory (`src/` on the `dev` branch) into `main`, flattening it to the repository root and **overwriting the entire branch**. Any change committed directly here will be silently lost on the next release.
>
> To change the plugin, edit the `dev` branch. To report an issue or suggest a change, use [Issues](https://github.com/tekintian/MySideBar/issues).

---

# MySideBar

A sidebar enhancement plugin for Sublime Text 4.

It adds the file operations Sublime Text lacks natively, available from the sidebar context menu and the tab context menu: automatic Chinese encoding detection and mojibake repair, cross-platform trash deletion, in-session cut/copy/paste, batch encoding conversion, and recursive file listing.

[中文说明](./README_CN.md)

---

## Install

Requires Sublime Text 4 (build 4000 or newer). No external dependencies, nothing to `pip install`.

### Package Control

1. `Ctrl+Shift+P` → `Package Control: Add Repository`, then paste:

```
https://raw.githubusercontent.com/tekintian/MySideBar/main/packages.json
```

2. `Ctrl+Shift+P` → `Package Control: Install Package`, search for `MySideBar` and select it.

### Manual

Download the latest `MySideBar-<version>.zip` from [Releases](https://github.com/tekintian/MySideBar/releases) and unzip it into `Packages/MySideBar/`. The zip root **is** the plugin root, so `MySideBar.py` must end up directly at `Packages/MySideBar/MySideBar.py`.

Locate `Packages` via `Preferences` → `Browse Packages...`.

Restart Sublime Text after installing. On the first run a language picker appears automatically.

---

## Menu items

### Sidebar context menu

| Menu item | What it does |
|---|---|
| Open In New Window | Open the selected file/directory in a new window |
| Open With Default Application | Open with the system default application |
| Cut / Copy / Paste | In-session cut, copy, paste (pastes whole directory trees across directories) |
| Copy Relative Path | Copy the path relative to the project root |
| Copy File Name | Copy the file name |
| Duplicate | Create a duplicate, avoiding name collisions |
| Move To | Move to a chosen directory |
| Move To Trash | Move to the system trash — never a permanent delete |
| List Files | Recursively list all files under a directory into a read-only view |
| Convert Encoding | Batch convert file encodings |

### Tab context menu

| Menu item | What it does |
|---|---|
| Reveal In File Manager | Reveal the file in the file manager |
| Copy Path | Copy the full path of the tab |
| Convert Encoding | Convert the encoding of the current file |

---

## Command palette

| Command | What it does |
|---|---|
| `MySideBar: List Files` | Recursively list files |
| `MySideBar: Open Listed File` | Open the file on the selected row |
| `MySideBar: Copy Listed Paths` | Copy the full paths of the selected rows |
| `MySideBar: Move Listed To Trash` | Trash the selected rows |
| `MySideBar: Convert Encoding` | Batch convert encodings |
| `MySideBar: UI Language - ...` | Switch the UI language |
| `MySideBar: Encoding Doctor` | Diagnose why a file shows mojibake |

In the list view, selecting a row and pressing `Enter` opens that file.

---

## Encoding repair

Files saved as GB18030, Big5, Shift JIS, EUC-KR or Windows 1252 can show up as garbled boxes in Sublime Text. MySideBar detects the real encoding when a file loads and reopens it silently, so you never switch encodings file by file.

- Auto-detection only runs when there is a single plausible candidate — decided by your locale — so GB18030 and Big5 are never guessed against each other. When it is ambiguous, the plugin does nothing instead of gambling.
- Binary files and pure-ASCII files are skipped outright.
- The reopen is polled and verified; a failed attempt is logged and abandoned, never left half-done.
- Open files with unsaved edits are never touched by batch conversion.
- Files larger than `encoding_max_bytes` (default 20 MB) are skipped and the reason is recorded.

Turn the whole feature off with `"auto_detect_encoding": false`.

---

## Language

`English` / `简体中文` / `繁體中文`. Switching takes effect immediately — no restart, no reinstall.

Three equivalent ways:

1. `Preferences` → `Settings`, set `ui_language` to `en` / `zh_CN` / `zh_TW`
2. `Preferences` → `Package Settings` → `MySideBar` → `Language`
3. Command palette: `MySideBar: UI Language - ...`

If the menus don't refresh, run `Preferences` → `Package Settings` → `MySideBar` → `Reapply Menus`.

Translations never rewrite files inside the package — they live in Sublime Text's own override layer under `<Packages>/User/MySideBar/`, and switching back to English removes them cleanly. Package upgrades therefore can't corrupt anything, and your settings are never overwritten.

---

## Settings

Open `Preferences` → `Package Settings` → `MySideBar` → `Settings`:

| Setting | Default | Description |
|---|---|---|
| `ui_language` | `null` | UI language; `null` means not chosen yet (prompted on first run) |
| `auto_detect_encoding` | `true` | Auto-detect and repair the encoding when a file is opened |
| `encoding_auto_locales` | `"zh_CN"` | The locale that selects the single candidate encoding: `zh_CN`→GB18030, `zh_TW`→Big5, `ja_JP`→Shift JIS |
| `encoding_max_bytes` | `20971520` | Per-file size limit for participating in conversion |
| `encoding_status_bar` | `true` | Show encoding results in the status bar |
| `confirm_before_trash` | `true` | Ask before moving files to the trash |
| `list_files_result_limit` | `5000` | Maximum rows in the file list; the rest is truncated |
| `list_files_exclude_dirs` | `[".git", "node_modules", "vendor", "dist", "build"]` | Directory names skipped when listing |
| `list_files_exclude_files` | `[".DS_Store", "Thumbs.db", "desktop.ini", "._*"]` | File names skipped when listing; prefix wildcards supported |
| `list_files_result_format` | `"relative"` | List display; `relative` shows paths relative to the project root |

The list view is capped on purpose: on hitting the limit, traversal stops and says so, rather than freezing the editor on a huge tree.

---

## Platform notes

| Platform | Trash implementation |
|---|---|
| macOS | `NSFileManager.trashItemAtURL:` via `ctypes` — no PyObjC needed |
| Windows | `SHFileOperationW` (`FO_DELETE` + `FOF_ALLOWUNDO`) |
| Linux | `gio trash`; unavailable if `gio` is not installed |

When the trash capability is missing, you get a clear failure reason — never a silent permanent delete.

`Cut` / `Copy` / `Paste` is an in-plugin session queue: it does not touch the system clipboard and does not persist across sessions. That is deliberate, so moving files and directories inside a project is always safe and reversible.

---

## License

MIT. See [LICENSE](./LICENSE).