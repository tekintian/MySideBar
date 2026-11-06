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
        targets = [item for item in items if item.exists]
        if not targets:
            return
        before = set(id(w) for w in sublime.windows())
        sublime.run_command("new_window")
        for item in targets:
            sublime.set_timeout(lambda it=item: self._populate(before, it), 100)

    def _populate(self, before, item):
        created = [w for w in sublime.windows() if id(w) not in before]
        new_window = created[-1] if created else sublime.active_window()
        if new_window is None or not new_window.is_valid():
            _report("new window creation failed")
            return
        if item.is_dir:
            new_window.set_project_data({"folders": [{"path": item.path}]})
            return
        new_window.open_file(item.path, sublime.NewFileFlags.NONE)

    def is_visible(self, paths=None):
        return bool(paths)