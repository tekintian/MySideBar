import os

import sublime
import sublime_plugin

from .. import i18n
from ..api import SideBarSelection
from .. import platform as plat


def _report(message):
    print("[MySideBar] %s" % message)


def _targets(paths):
    selection = SideBarSelection(paths)
    return selection.without_child_items()


class MySidebarOpenWithDefaultCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        failed = []
        for item in _targets(paths):
            if not item.exists:
                failed.append(item.path)
                continue
            if not plat.open_with_default(item.path):
                failed.append(item.path)
        if failed:
            _report(i18n.t("open.failed", path=failed[0], reason="system open failed"))
            self._status(i18n.t("open.failed_count", count=len(failed)))

    def _status(self, message):
        if self.window is not None and self.window.is_valid():
            self.window.status_message(message)

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarOpenInNewWindowCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        placed = 0
        for item in items:
            new_window = sublime.new_window()
            if new_window is None:
                continue
            new_window.set_project_data({"folders": [{"path": item.path}]})
            placed += 1
        if placed == 0:
            _report("new window creation failed")

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarOpenInOtherGroupCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        window = self.window
        if window is None or not window.is_valid():
            return
        items = _targets(paths)
        if not items:
            return
        origin_group = window.active_group()
        target_group = self._target_group(window, origin_group)
        if target_group < 0:
            return
        touched = 0
        for item in items:
            if item.is_dir:
                continue
            if not item.exists:
                continue
            encoded = sublime.ENCODED_FILE
            view = window.open_file(item.path, flags=encoded, group=target_group)
            if view is not None:
                touched += 1
        self._restore_focus(window, origin_group)
        if touched == 0:
            _report("no file opened in the other group")

    def _target_group(self, window, origin_group):
        others = [g for g in range(window.num_groups()) if g != origin_group]
        if not others:
            return -1
        return others[0]

    def _restore_focus(self, window, origin_group):
        active = window.active_view()
        if active is not None:
            group, index = window.get_view_index(active)
            if group == origin_group:
                return
            sender = None
            for view in window.views_in_group(origin_group):
                if view.file_name():
                    sender = view
                    break
            if sender is not None:
                window.focus_view(sender)

    def is_visible(self, paths=None):
        return bool(paths)