# MySideBar

A sidebar enhancement plugin for Sublime Text 4.

It fills in the file-operation capabilities that ST lacks natively, available from the sidebar context menu and the tab context menu: automatic Chinese encoding detection and mojibake repair, cross-platform trash deletion, in-session cut/copy/paste, batch encoding conversion, recursive file listing, and more.

English | [简体中文](./README_CN.md)

---

## Highlights

### 1. Automatic mojibake repair — files open correctly the first time

Chinese files encoded in GB18030 / Big5 often appear as garbled boxes when opened in ST. This plugin detects the real encoding when a file loads and silently reopens it, so **you never have to switch encodings file by file**.

The hard part is that Chinese encodings are extremely easy to confuse with each other — the same byte sequence can "successfully" decode under both GB18030 and Big5, yet only one is correct. The plugin's approach:

- **Single-candidate detection only**: `locale` determines the one and only candidate encoding (`zh_CN`→GB18030, `zh_TW`→Big5, `ja_JP`→Shift JIS). When multiple candidates exist it simply gives up, eliminating misdetection by design instead of guessing by "confidence score".
- **Credibility validation**: the decoded result must still pass three gates — the PUA (Private Use Area) character ratio must stay below 2%, the half-width katakana ratio for Shift JIS must stay below 30% (this catches the large runs of half-width katakana produced by wrong decoding), and the script family must match the encoding.
- **Binary and pure-ASCII checked first**: binary files are never misdetected, and pure-ASCII files are skipped outright — no pointless encoding fiddling.
- **Reopen result verified twice**: it does not just fire a reopen and walk away. It polls with a delay (120 ms interval, up to 30 attempts) to confirm the encoding really switched; on failure it explicitly gives up and logs it, never leaving a half-processed state.

### 2. No dump files, no package pollution, no lost settings on upgrade

Many plugins rewrite files inside their own package or drop temporary files all over the place when localizing menus — leaving junk like `xxx.bak`, `xxx.orig`, or having their strings corrupted after a `Package Control` upgrade overwrites the package. This plugin is strict about this:

- **Package files are never rewritten**: files such as `Side Bar.sublime-menu` always stay in plain English, so a plugin upgrade overwriting the package can never break anything.
- **Translations land only in ST's official override layer**: translations are written to `<Packages>/User/MySideBar/`, a mechanism ST itself supports — no extra files are created.
- **Switching cleans up — no residue**: switching back to English deletes the override files directly, so the English originals inside the package take effect again; uninstalling the plugin cleans up both the overrides and the marker files.
- **The only persistent artifact is a meaningful backup**: just one directory, `<Packages>/tmp/menu_backup/`, used to reuse the originals when toggling between minor languages. An idempotency check runs before writing — if the source file has changed, the backup is refused, preventing dirty data from poisoning every later switch.

### 3. Real system trash on all three platforms, with zero third-party dependencies

Deleting a file should not be irreversible. The plugin never uses `os.remove`; it actually invokes the system's trash capability, and it **depends on no third-party package**:

| Platform | Implementation |
|---|---|
| macOS | Calls the Objective-C runtime and `NSFileManager` directly via `ctypes` — no PyObjC needed |
| Windows | Calls `SHFileOperationW` (`FOF_ALLOWUNDO`), so files go to the Recycle Bin instead of vanishing |
| Linux | Calls `gio trash` |

When the capability is unavailable (e.g. `gio` not installed on Linux, or no objc runtime in some environments), it reports a clear failure reason instead of failing silently or degrading to a permanent delete.

### 4. Batch operations don't freeze the UI, and don't wipe out your unsaved changes

- **Batch operations in the list view**: the recursive walk runs on an async thread and writes to the view in batches, so the UI never blocks. Large directories are protected by a result-count cap (default 5000, configurable); on reaching the cap, traversal stops and a truncation notice is shown.
- **Batch encoding conversion runs serially**: files are processed one at a time, so it never opens dozens of files at once and chokes the editor.
- **Dirty files are skipped outright**: a file that is open with **unsaved modifications** is never overwritten by encoding conversion — better to skip than to swallow your edits.
- **Large-file protection**: files over `encoding_max_bytes` (default 20 MB) are skipped automatically with the reason recorded.
- **Traceable results**: every file's success/skip/failure plus the reason is summarized in a result panel — even when it doesn't work, you know why.

### 5. Instant UI language switching, no restart required

Three languages: `English` / `简体中文` / `繁體中文`. The menus update immediately after switching — no Sublime Text restart and no reinstall needed. The string tables are fully aligned across all three languages (111 keys each); on a missing key it falls back level by level to the English original, so you never see blanks or literal `key` names.

### 6. Pure Python · zero dependencies · consistent across three platforms

It uses only the Python runtime built into ST4 and its standard library. No external dependencies, no pip installs, and identical behavior on macOS / Windows / Linux.

---

## Features

### Sidebar context menu

| Menu item | Description |
|---|---|
| Open In New Window | Open the selected file/directory in a new Sublime Text window |
| Open With Default Application | Open with the system default application |
| Cut / Copy / Paste | In-session cut, copy, paste (pastes entire directory trees across directories) |
| Copy Relative Path | Copy the path relative to the project root |
| Copy File Name | Copy the file name |
| Duplicate | Create a duplicate (automatically avoiding name collisions) |
| Move To | Move to a specified directory |
| Move To Trash | Move to the system trash (not a permanent delete) |
| List Files | Recursively list all files under a directory into a read-only view |
| Convert Encoding | Batch convert file encodings |

### Tab context menu

| Menu item | Description |
|---|---|
| Reveal In File Manager | Reveal the file in the file manager |
| Copy Path | Copy the full path of the tab |
| Convert Encoding | Convert the encoding of the current tab's file |

### File list view

The read-only list view produced by `List Files` supports:

- Selecting a row and pressing `Enter` to open the corresponding file
- Running `MySideBar: Copy Listed Paths` from the command palette to copy paths in bulk
- Running `MySideBar: Move Listed To Trash` from the command palette to trash items in bulk
- Excluding directories/files, a result-count cap, and relative-path display format

### Encoding handling

- Supports UTF-8, UTF-16 LE/BE, GB18030, Big5, Shift JIS, EUC-KR, Windows 1252
- Detects and silently fixes mojibake when a file is opened (can be disabled)
- Auto-detection only applies when there is a single candidate encoding, preventing GB18030 and Big5 from misjudging each other
- Batch conversion runs asynchronously and serially without blocking the UI; open files with unsaved modifications are skipped
- Provides an `Encoding Doctor` diagnostic report for troubleshooting mojibake

---

## Installation

> **Note**: the plugin package root is the `src/` directory — entry files such as `MySideBar.py` sit directly at the `src/` top level. The repo root also holds `packages.json` (the Package Control manifest), `tools/` (build and release scripts), `tests/` (validation scripts) and `docs/`; none of these are part of the running plugin.

The recommended install method is Package Control (`Add Repository` + `Install Package`), or use one of the manual methods below.

### Option 1: Install via Package Control

1. `Ctrl+Shift+P` → `Package Control: Add Repository`, then enter the manifest URL below (the `packages.json` file, not the repository URL)
2. `Ctrl+Shift+P` → `Package Control: Install Package`, search for and select `MySideBar`

```
https://raw.githubusercontent.com/tekintian/MySideBar/main/packages.json
```

Each published version points at the Release archive for that tag; the archive root *is* the plugin root, so no nesting level is introduced.

### Option 2: Manual installation

Copy the contents of `src/` into `Packages/MySideBar/` (`tests/`, `docs/` and `tools/` are not needed):

```bash
# macOS / Linux example — adjust the paths to your actual setup
rsync -av --exclude=__pycache__ \
  src/ "<Packages>/MySideBar"
```

After installation the directory structure must be:

```
<Packages>/MySideBar/
├── MySideBar.py                  ← must be at the MySideBar/ top level
├── MySideBar.sublime-settings
├── Commands.sublime-commands
├── Side Bar.sublime-menu
├── Tab Context.sublime-menu
├── Tab Sidebar Context.sublime-menu
├── Main.sublime-menu
├── Default.sublime-keymap
├── meta.py
├── messages.json
├── .no-sublime-package           ← required, otherwise the menu overlay mechanism breaks
├── .python-version               ← must contain 3.8
├── messages/
│   └── install.txt
└── mysidebar/
    ├── api.py
    ├── i18n.py
    ├── cmds/
    └── ...
```

The test for a correct install: `<Packages>/MySideBar/MySideBar.py` must exist directly. If it ends up as `<Packages>/MySideBar/src/MySideBar.py`, the nesting level is wrong and the plugin will not load.

You can locate the `Packages` directory via `Preferences` → `Browse Packages...`.

### Option 3: Development setup (symlink to `src/`)

Ideal when you want to keep up with code changes in this repository — symlink `src/` as the plugin directory:

```bash
ln -s "/path/to/MySideBar/src" "<Packages>/MySideBar"
```

After modifying code, run `Ctrl+Shift+P` → `Sublime Text: Reload Plugin Host` in Sublime Text (or execute `sublime_plugin.reload_plugin("MySideBar.MySideBar")` directly in the console) for the changes to take effect.

Restart Sublime Text after installation; on first run a language selection panel appears automatically.

---

## Usage

### Switching language

Three ways, all equivalent and effective immediately:

1. `Preferences` → `Settings`, set `ui_language` to `en` / `zh_CN` / `zh_TW`
2. `Preferences` → `Package Settings` → `MySideBar` → `Language` submenu
3. Run `MySideBar: UI Language - ...` from the command palette

If the menus don't update in time, run `Preferences` → `Package Settings` → `MySideBar` → `Reapply Menus` to force a reapply.

### Configuration

Open the user configuration via `Preferences` → `Package Settings` → `MySideBar` → `Settings`:

| Setting | Default | Description |
|---|---|---|
| `ui_language` | `null` | UI language; `null` means not chosen yet (prompted on first run) |
| `encoding_max_bytes` | `20971520` | Per-file size limit (bytes) for participating in batch encoding conversion |
| `auto_detect_encoding` | `true` | Whether to auto-detect the encoding when a file is opened |
| `encoding_auto_locales` | `"zh_CN"` | Locale used for auto-detection, which determines the single candidate encoding: `zh_CN`→GB18030, `zh_TW`→Big5, `ja_JP`→Shift JIS |
| `encoding_status_bar` | `true` | Whether to show encoding processing results in the status bar |
| `list_files_result_limit` | `5000` | Maximum lines in the file list; anything beyond is truncated |
| `list_files_exclude_dirs` | `[".git", "node_modules", "vendor", "dist", "build"]` | Directory names to skip when listing |
| `list_files_exclude_files` | `[".DS_Store", "Thumbs.db", "desktop.ini", "._*"]` | File names to skip when listing; prefix wildcards supported |
| `list_files_result_format` | `"relative"` | List display format; `relative` shows paths relative to the project root |
| `confirm_before_trash` | `true` | Whether to confirm before moving to the trash |

### Command palette

| Command | Description |
|---|---|
| `MySideBar: List Files` | Recursively list files |
| `MySideBar: Move Listed To Trash` | Move the selected items in the list to the trash |
| `MySideBar: Copy Listed Paths` | Copy full paths of the selected items in the list |
| `MySideBar: Open Listed File` | Open the selected file in the list |
| `MySideBar: Convert Encoding` | Batch convert encodings |
| `MySideBar: UI Language - ...` | Switch the UI language |

---

## Platform notes

| Platform | Trash implementation |
|---|---|
| macOS | `NSFileManager.trashItemAtURL:` invoked via `ctypes` — no PyObjC needed |
| Windows | `SHFileOperationW` (`FO_DELETE` + `FOF_ALLOWUNDO`) |
| Linux | `gio trash`; unavailable when `gio` is not installed |

The clipboard (`Cut` / `Copy` / `Paste`) is an in-plugin-session queue — it does not write to the system clipboard and does not persist across sessions. This is intentional, for safely moving files or directories within a project.

---

## Key bindings

| Key | Scope |
|---|---|
| `Enter` | Only in the list view produced by `List Files` — opens the file on the current row |

---

## License

See [LICENSE](./LICENSE).