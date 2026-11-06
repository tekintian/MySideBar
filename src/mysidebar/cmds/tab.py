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


def _convertible(window, group, index):
    view = _target_view(window, group, index)
    if view is None or not view.is_valid():
        return False
    if view.is_scratch():
        return False
    path = plat.normalize(view.file_name())
    return bool(path and os.path.exists(path))


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


class MySidebarTabCopyPathCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if path is None:
            _status(self.window, "tab.no_target")
            return
        sublime.set_clipboard(path)
        _status(self.window, "tab.copied_path")

    def is_visible(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))

    def is_enabled(self, group=-1, index=-1):
        return bool(_exists(self.window, group, index))


class MySidebarTabConvertEncodingCommand(sublime_plugin.WindowCommand):
    def run(self, group=-1, index=-1):
        path = _target_path(self.window, group, index)
        if path is None:
            _status(self.window, "tab.no_target")
            return
        self.window.run_command("my_sidebar_convert_encoding", {"paths": [path]})

    def is_visible(self, group=-1, index=-1):
        return bool(_convertible(self.window, group, index))

    def is_enabled(self, group=-1, index=-1):
        return bool(_convertible(self.window, group, index))