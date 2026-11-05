import os

import sublime
import sublime_plugin

from .. import encoding_detect
from .. import encodings
from .. import i18n
from ..api import SideBarSelection, ViewResolver
from .. import platform as plat


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
LOAD_RETRY_LIMIT = 100
LOAD_RETRY_DELAY = 50

TARGET_LIST = encodings.convertible()

CAPTION_KEYS = dict((spec.name, spec.i18n_key) for spec in encodings.specs())


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


AUTO_DETECT = "auto-detect"

GROUP_KEYS = {
    encodings.FAMILY_UNICODE: "encoding.group.unicode",
    encodings.FAMILY_ZH: "encoding.group.zh",
    encodings.FAMILY_JA: "encoding.group.ja",
    encodings.FAMILY_KO: "encoding.group.ko",
    encodings.FAMILY_WESTERN: "encoding.group.western",
}


def _caption(name):
    spec = encodings.spec_for(name)
    group = GROUP_KEYS.get(spec.family) if spec else None
    text = i18n.t(spec.i18n_key) if spec else name
    if group is None:
        return text
    return "%s  %s" % (i18n.t(group), text)


def _source_options():
    names = (AUTO_DETECT,) + TARGET_LIST
    return list(names), [_caption(AUTO_DETECT)] + [_caption(name) for name in TARGET_LIST]


def _encode_target(text, target, codec):
    payload = text.encode(codec)
    marker = encodings.bom(target)
    if marker and not payload.startswith(marker):
        payload = marker + payload
    return payload


class MySidebarConvertEncodingCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        self._items = items
        self._index = 0
        self._result = {"ok": 0, "skipped": 0, "failed": 0, "lines": []}
        self._source_encoding = None
        _status(self.window, "encoding.pick_source")
        self._source_names, labels = _source_options()
        self.window.show_quick_panel(labels, self._on_source)

    def _on_source(self, index):
        if index < 0:
            return
        self._source_encoding = self._source_names[index]
        _status(self.window, "encoding.pick_target")
        labels = [_caption(name) for name in TARGET_LIST]
        self.window.show_quick_panel(labels, self._on_target)

    def _on_target(self, index):
        if index < 0:
            return
        self._target_encoding = TARGET_LIST[index]
        if self._source_encoding == self._target_encoding:
            _status(self.window, "encoding.cancelled")
            return
        confirmed = sublime.ok_cancel_dialog(
            i18n.t("encoding.confirm"),
            i18n.t("encoding.confirm_ok"),
        )
        self._on_confirmed(confirmed)

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
        source = getattr(self, "_source_encoding", None)
        if source != AUTO_DETECT and source == target:
            self._add_skipped(i18n.t("encoding.skipped_same", path=item.path, encoding=target))
            self._advance()
            return
        if ViewResolver.count_views_for_file(item.path, exclude_view=view) > 0:
            self._add_failed(i18n.t("encoding.multi_view", path=item.path))
            self._advance()
            return
        if view.is_dirty():
            confirmed = sublime.ok_cancel_dialog(
                i18n.t("encoding.dirty", path=item.path),
                i18n.t("encoding.confirm_ok"),
            )
            self._on_dirty(confirmed, item, view)
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
        source = getattr(self, "_source_encoding", None)
        if source == AUTO_DETECT:
            source = encoding_detect.detect(item.path)
            if source is None:
                _report("encoding auto detect failed %s" % item.path)
                self._add_failed(i18n.t("encoding.auto_failed", path=item.path))
                return
        source_codec = encodings.py_codec(source)
        target_codec = encodings.py_codec(target)
        if not source_codec or not target_codec:
            self._add_failed(i18n.t("encoding.set_failed", path=item.path, encoding=target))
            return
        try:
            raw = self._read_bytes(item.path)
        except Exception as exc:
            _report("encoding read failed %s: %s" % (item.path, exc))
            self._add_failed(i18n.t("encoding.read_failed", path=item.path))
            return
        try:
            text = raw.decode(source_codec)
        except Exception as exc:
            _report("encoding decode failed %s as %s: %s" % (item.path, source, exc))
            self._add_failed(i18n.t("encoding.decode_failed", path=item.path, encoding=source))
            return
        try:
            payload = _encode_target(text, target, target_codec)
        except Exception as exc:
            _report("encoding encode failed %s as %s: %s" % (item.path, target, exc))
            self._add_failed(i18n.t("encoding.encode_failed", path=item.path, encoding=target))
            return
        if not self._write_bytes(item.path, payload):
            self._add_failed(i18n.t("encoding.save_failed", path=item.path))
            return
        encoding_detect.forget(item.path)
        self._reload_view(view, target)
        self._add_ok(item.path, source, target)

    def _reload_view(self, view, target):
        if view is None or not view.is_valid():
            return
        encodings.reopen_view(view, target)

    def _read_bytes(self, path):
        with open(path, "rb") as fp:
            return fp.read()

    def _write_bytes(self, path, payload):
        try:
            with open(path, "wb") as fp:
                fp.write(payload)
        except Exception as exc:
            _report("encoding write failed %s: %s" % (path, exc))
            return False
        return True

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