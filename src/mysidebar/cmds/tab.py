import os

import sublime
import sublime_plugin

from .. import i18n
from .. import platform as plat
from ..api import ViewResolver


def _status(window, key, **kwargs):
    if window is not None and window.is_valid():
        window.status_message(i18n.t(key, **kwargs))


def _target_view(window, group, index):
    return ViewResolver.resolve_tab_view(window, group, index)


def _target_path(window, group, index):
    view = _target_view(window, group, index)
    if view is None:
        return None
    return plat.normalize(view.file_name())


def _exists(window, group, index):
    path = _target_path(window, group, index)
    return bool(path and os.path.exists(path))


def _inner_root(window, path):
    best = None
    for folder in window.folders():
        normalized = plat.normalize(folder)
        if not plat.is_within(path, normalized):
            continue
        if best is None or len(normalized) > len(best):
            best = normalized
    return best


class MySidebarTabRevealCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if path is None:
            _status(self.window, "tab.no_target")
            return
        if not plat.reveal(path, dir_only=False):
            _status(self.window, "tab.reveal_failed")

    def is_visible(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))

    def is_enabled(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))


class MySidebarTabCopyRelativePathCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if path is None:
            _status(self.window, "tab.no_target")
            return
        root = _inner_root(self.window, path)
        if root is None:
            _status(self.window, "tab.no_root")
            return
        try:
            relative = plat.normalize(os.path.relpath(path, root))
        except (OSError, ValueError):
            _status(self.window, "tab.no_root")
            return
        sublime.set_clipboard(relative)
        _status(self.window, "tab.copied_relative")

    def _available(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if not path:
            return False
        return _inner_root(self.window, path) is not None

    def is_visible(self, group=-1, index=-1):
        return bool(self._available(group, index))

    def is_enabled(self, group=-1, index=-1):
        return bool(self._available(group, index))


class MySidebarTabOpenDirCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if path is None:
            _status(self.window, "tab.no_target")
            return
        if not plat.reveal(path, dir_only=True):
            _status(self.window, "tab.reveal_failed")

    def is_visible(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))

    def is_enabled(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))