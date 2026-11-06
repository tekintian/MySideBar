import os

import sublime
import sublime_plugin

from .. import i18n
from ..api import SideBarProject
from .. import platform as plat


DEFAULT_LIMIT = 5000
LINES_KEY = "my_sidebar_search_lines"
FLAG_KEY = "my_sidebar_search_result"

DEFAULT_EXCLUDE_FILES = (".DS_Store", "Thumbs.db", "desktop.ini", "._")


def _status(window, key, **kwargs):
    if window is not None and window.is_valid():
        window.status_message(i18n.t(key, **kwargs))


def _settings():
    return sublime.load_settings("MySideBar.sublime-settings")


def _limit():
    try:
        value = int(_settings().get("search_result_limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if value <= 0:
        return DEFAULT_LIMIT
    return value


def _excludes():
    raw = _settings().get("exclude_dirs_for_search", [])
    if not isinstance(raw, list):
        return set()
    result = set()
    for name in raw:
        if not isinstance(name, str):
            continue
        text = name.strip().lower()
        if text:
            result.add(text)
    return result


def _exclude_files():
    raw = _settings().get("exclude_files_for_search", None)
    if not isinstance(raw, list):
        raw = list(DEFAULT_EXCLUDE_FILES)
    exact = set()
    prefixes = set()
    for name in raw:
        if not isinstance(name, str):
            continue
        text = name.strip().lower()
        if not text:
            continue
        if text.startswith("*"):
            prefixes.add(text[1:])
        elif text.endswith("*"):
            prefixes.add(text[:-1])
        else:
            exact.add(text)
    return exact, prefixes


def _is_excluded_file(name, exact, prefixes):
    lowered = name.lower()
    if lowered in exact:
        return True
    for prefix in prefixes:
        if prefix and lowered.startswith(prefix):
            return True
    return False


def _source_view(window):
    for view in window.views():
        if view.settings().get(FLAG_KEY):
            return view
    return None


def _line_map(view):
    if view is None or not view.is_valid():
        return {}
    raw = view.settings().get(LINES_KEY)
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key, path in raw.items():
        if isinstance(key, str) and isinstance(path, str):
            result[key] = path
    return result


def _selected_lines(view):
    if view is None or not view.is_valid():
        return []
    lines = []
    for region in view.sel():
        if region.empty():
            continue
        for line in view.substr(region).splitlines():
            text = line.strip()
            if text:
                lines.append(text)
    return lines


def _selected_paths(window):
    view = _source_view(window)
    if view is None:
        return []
    mapping = _line_map(view)
    paths = []
    seen = set()
    for line in _selected_lines(view):
        path = mapping.get(line)
        if path is None:
            continue
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


class MySidebarSearchFilesCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        roots = self._roots(paths)
        if not roots:
            _status(self.window, "search.no_root")
            return
        self._root_dirs = roots
        self._excludes = _excludes()
        self._exclude_exact, self._exclude_prefixes = _exclude_files()
        self._limit = _limit()
        self._truncated = False
        self._total = 0
        self._entries = []
        self._view = self._prepare_view(roots)
        self.window.focus_view(self._view)
        sublime.set_timeout_async(self._walk_all, 0)

    def _roots(self, paths):
        result = []
        if paths:
            for path in paths:
                normalized = plat.normalize(path)
                if os.path.isdir(normalized):
                    result.append(normalized)
            return result
        project = SideBarProject(self.window)
        return project.folders()

    def _prepare_view(self, roots):
        view = _source_view(self.window)
        if view is None:
            view = self.window.new_file()
            view.set_scratch(True)
            view.settings().set(FLAG_KEY, True)
            view.set_name(i18n.t("search.result_title"))
        view.set_read_only(False)
        view.run_command("select_all")
        view.run_command("right_delete")
        header = self._header_lines(roots)
        view.run_command("append", {"characters": "\n".join(header) + "\n"})
        view.set_read_only(True)
        view.settings().set(LINES_KEY, {})
        view.settings().erase("result_file_regex")
        view.settings().erase("result_base_dir")
        return view

    def _header_lines(self, roots):
        lines = [i18n.t("search.header_path")]
        for root in roots:
            lines.append("  %s" % root)
        lines.append("")
        lines.append(i18n.t("search.header_list"))
        return lines

    def _walk_all(self):
        for root in self._root_dirs:
            if self._truncated:
                break
            self._walk_root(root)
        sublime.set_timeout(lambda: self._done(), 0)

    def _walk_root(self, root):
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if self._truncated:
                break
            dirnames[:] = sorted(
                d for d in dirnames if d.lower() not in self._excludes
            )
            for name in sorted(filenames):
                if _is_excluded_file(name, self._exclude_exact, self._exclude_prefixes):
                    continue
                path = os.path.join(dirpath, name)
                rel = plat.rel_path(path, root)
                if rel is None:
                    continue
                self._entries.append((rel, path))
                self._total += 1
                if self._total >= self._limit:
                    self._truncated = True
                    return

    def _flush(self):
        if not self._entries:
            return
        view = self._view
        if view is None or not view.is_valid():
            self._entries = []
            return
        mapping = view.settings().get(LINES_KEY, {})
        if not isinstance(mapping, dict):
            mapping = {}
        batch = sorted(self._entries, key=lambda entry: entry[0].lower())
        self._entries = []
        keys = []
        for rel, path in batch:
            unique = rel
            suffix = 2
            while unique in mapping:
                unique = "%s  (%d)" % (rel, suffix)
                suffix += 1
            mapping[unique] = path
            keys.append(unique)
        view.set_read_only(False)
        view.run_command("append", {"characters": "\n".join(keys) + "\n"})
        view.set_read_only(True)
        view.settings().set(LINES_KEY, mapping)

    def _done(self):
        self._flush()
        _status(self.window, "search.done", count=self._total)
        if self._truncated:
            _status(self.window, "search.truncated", limit=self._limit)

    def is_visible(self, paths=None):
        return True


class MySidebarSearchOpenCommand(sublime_plugin.WindowCommand):
    def run(self):
        window = self.window
        view = _source_view(window)
        if view is None or not view.is_valid():
            return
        mapping = _line_map(view)
        for line in _selected_lines(view):
            path = mapping.get(line)
            if path is None:
                continue
            window.open_file(path)
            return
        _status(window, "search.no_selection")

    def is_visible(self):
        return self.is_enabled()

    def is_enabled(self):
        view = _source_view(self.window)
        if view is None or not view.is_valid():
            return False
        mapping = _line_map(view)
        if not mapping:
            return False
        for line in _selected_lines(view):
            if line in mapping:
                return True
        return False


class MySidebarSearchBase(sublime_plugin.WindowCommand):
    def _paths(self):
        return _selected_paths(self.window)

    def is_visible(self):
        return self.is_enabled()

    def is_enabled(self):
        view = _source_view(self.window)
        if view is None or not view.is_valid():
            return False
        return bool(_line_map(view))


class MySidebarSearchTrashCommand(MySidebarSearchBase):
    def run(self):
        paths = self._paths()
        if not paths:
            _status(self.window, "search.no_selection")
            return
        self.window.run_command("my_sidebar_move_to_trash", {"paths": paths})


class MySidebarSearchCopyCommand(MySidebarSearchBase):
    def run(self):
        paths = self._paths()
        if not paths:
            _status(self.window, "search.no_selection")
            return
        sublime.set_clipboard("\n".join(paths))
        _status(self.window, "search.copied", count=len(paths))