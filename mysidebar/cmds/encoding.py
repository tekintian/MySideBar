import os

import sublime
import sublime_plugin

from .. import encodings
from .. import i18n
from ..api import SideBarSelection, ViewResolver
from .. import platform as plat


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
LOAD_RETRY_LIMIT = 100
LOAD_RETRY_DELAY = 50

TARGET_LIST = (
    encodings.GB18030,
    encodings.UTF8,
    encodings.UTF16LE,
    encodings.UTF16BE,
)

CAPTION_KEYS = {
    encodings.GB18030: "encoding.target.gb18030",
    encodings.UTF8: "encoding.target.utf8",
    encodings.UTF16LE: "encoding.target.utf16le",
    encodings.UTF16BE: "encoding.target.utf16be",
}


def _report(message):
    print("[MySideBar] %s" % message)


def _status(window, key, **kwargs):
    if window is not None and window.is_valid():
        window.status_message(i18n.t(key, **kwargs))


def _settings():
    return sublime.load_settings("MySideBar.sublime-settings")


def _max_bytes():
    try:
        value = int(_settings().get("encoding_max_bytes", DEFAULT_MAX_BYTES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES
    if value <= 0:
        return DEFAULT_MAX_BYTES
    return value


def _targets(paths):
    selection = SideBarSelection(paths)
    if selection.is_empty:
        return []
    items = []
    for item in selection.without_child_items():
        if not item.exists:
            continue
        items.append(item)
    return items


def _find_view(window, path):
    for candidate in window.views():
        fname = candidate.file_name()
        if not fname:
            continue
        if plat.same_path(fname, path):
            return candidate
    return None


class MySidebarConvertEncodingCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        self._items = items
        self._index = 0
        self._result = {"ok": 0, "skipped": 0, "failed": 0, "lines": []}
        labels = [i18n.t(CAPTION_KEYS[name]) for name in TARGET_LIST]
        self.window.show_quick_panel(labels, self._on_target)

    def _on_target(self, index):
        if index < 0:
            return
        self._target_encoding = TARGET_LIST[index]
        self.window.show_ok_cancel_dialog(
            i18n.t("encoding.confirm"),
            i18n.t("encoding.confirm_ok"),
            self._on_confirmed,
        )

    def _on_confirmed(self, confirmed):
        if not confirmed:
            _status(self.window, "encoding.cancelled")
            return
        self._advance()

    def _advance(self):
        items = getattr(self, "_items", [])
        index = getattr(self, "_index", 0)
        if index >= len(items):
            self._finish()
            return
        self._index = index + 1
        self._load_view(items[index])

    def _load_view(self, item):
        view = _find_view(self.window, item.path)
        if view is not None:
            self._start(item, view)
            return
        view = self.window.open_file(item.path)
        sublime.set_timeout(lambda: self._wait_loaded(item, view, 0), LOAD_RETRY_DELAY)

    def _wait_loaded(self, item, view, attempt):
        if not view.is_valid():
            self._add_failed(i18n.t("encoding.not_loaded", path=item.path))
            self._advance()
            return
        if view.is_loaded():
            self._start(item, view)
            return
        if attempt >= LOAD_RETRY_LIMIT:
            self._add_failed(i18n.t("encoding.not_loaded", path=item.path))
            self._advance()
            return
        sublime.set_timeout(
            lambda: self._wait_loaded(item, view, attempt + 1), LOAD_RETRY_DELAY
        )

    def _start(self, item, view):
        target = getattr(self, "_target_encoding", None)
        if target is None:
            self._advance()
            return
        if not self._writable(item.path):
            self._add_failed(i18n.t("encoding.readonly", path=item.path))
            self._advance()
            return
        limit = _max_bytes()
        if self._size(item.path) > limit:
            self._add_failed(
                i18n.t("encoding.too_large", path=item.path, limit=limit // (1024 * 1024))
            )
            self._advance()
            return
        source = view.encoding()
        if source == target:
            self._add_skipped(i18n.t("encoding.skipped_same", path=item.path, encoding=target))
            self._advance()
            return
        if ViewResolver.count_views_for_file(item.path, exclude_view=view) > 0:
            self._add_failed(i18n.t("encoding.multi_view", path=item.path))
            self._advance()
            return
        if view.is_dirty():
            self.window.show_ok_cancel_dialog(
                i18n.t("encoding.dirty", path=item.path),
                i18n.t("encoding.confirm_ok"),
                lambda confirmed: self._on_dirty(confirmed, item, view),
            )
            return
        self._rewrite(item, view, target)
        self._advance()

    def _on_dirty(self, confirmed, item, view):
        if not confirmed:
            self._add_skipped(i18n.t("encoding.skipped_dirty", path=item.path))
            self._advance()
            return
        view.run_command("save")
        if not view.is_valid() or view.is_dirty():
            self._add_failed(i18n.t("encoding.save_failed", path=item.path))
            self._advance()
            return
        self._rewrite(item, view, self._target_encoding)
        self._advance()

    def _rewrite(self, item, view, target):
        source = view.encoding()
        try:
            text = view.substr(sublime.Region(0, view.size()))
        except Exception as exc:
            _report("encoding read buffer failed %s: %s" % (item.path, exc))
            self._add_failed(i18n.t("encoding.read_failed", path=item.path))
            return
        view.run_command("select_all")
        view.run_command("insert", {"characters": text})
        if not ViewResolver.set_encoding_checked(view, target):
            self._add_failed(i18n.t("encoding.set_failed", path=item.path, encoding=target))
            return
        view.run_command("save")
        if view.is_dirty():
            self._add_failed(i18n.t("encoding.save_failed", path=item.path))
            return
        self._add_ok(item.path, source, target)

    def _size(self, path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def _writable(self, path):
        return os.access(path, os.W_OK)

    def _add_ok(self, path, source, target):
        self._result["ok"] += 1
        self._result["lines"].append(
            "OK    %s  %s -> %s" % (path, source, target)
        )

    def _add_skipped(self, message):
        self._result["skipped"] += 1
        self._result["lines"].append("SKIP  %s" % message)

    def _add_failed(self, message):
        self._result["failed"] += 1
        self._result["lines"].append("FAIL  %s" % message)

    def _finish(self):
        result = getattr(self, "_result", {"ok": 0, "skipped": 0, "failed": 0, "lines": []})
        self._show_result(result)
        _status(
            self.window,
            "encoding.result_summary",
            ok=result["ok"],
            skipped=result["skipped"],
            failed=result["failed"],
        )

    def _show_result(self, result):
        window = self.window
        if window is None or not window.is_valid():
            return
        panel = window.create_output_panel("my_sidebar_encoding")
        panel.set_read_only(False)
        lines = [i18n.t("encoding.result_summary", ok=result["ok"], skipped=result["skipped"], failed=result["failed"])]
        lines.append("")
        for line in result["lines"]:
            lines.append(line)
        body = "\n".join(lines) + "\n"
        panel.run_command("select_all")
        panel.run_command("insert", {"characters": body})
        panel.set_read_only(True)
        window.run_command("show_panel", {"panel": "output.my_sidebar_encoding"})

    def is_visible(self, paths=None):
        return bool(paths)

    def is_enabled(self, paths=None):
        return bool(paths)