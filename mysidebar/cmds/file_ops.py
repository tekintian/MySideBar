import os
import shutil

import sublime
import sublime_plugin

from .. import i18n
from ..api import SideBarItem, SideBarSelection, ViewResolver
from .. import platform as plat


def _report(message):
    print("[MySideBar] %s" % message)


def _refresh(window):
    if window is not None and window.is_valid():
        window.run_command("refresh_folder_list")


def _status(window, key, **kwargs):
    if window is not None and window.is_valid():
        window.status_message(i18n.t(key, **kwargs))


class MySidebarDuplicateCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        selection = SideBarSelection(paths)
        items = selection.without_child_items()
        if not items:
            return
        created = []
        failed = 0
        for item in items:
            if not item.exists:
                failed += 1
                continue
            target = plat.duplicate_target(item.path)
            try:
                if item.is_dir:
                    shutil.copytree(item.path, target, symlinks=True)
                else:
                    shutil.copy2(item.path, target)
                created.append(target)
            except (OSError, shutil.Error) as exc:
                _report("duplicate failed %s: %s" % (item.path, exc))
                failed += 1
        _refresh(self.window)
        if created:
            _status(self.window, "fileops.duplicate.done", count=len(created))
        if failed:
            _status(self.window, "fileops.failed_count", count=failed)

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarMoveCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        selection = SideBarSelection(paths)
        items = selection.without_child_items()
        if not items:
            return
        self._items = items
        self._suggested = selection.common_base() or ""
        self.window.show_input_panel(
            i18n.t("fileops.move.prompt"),
            self._suggested,
            self._on_done,
            None,
            None,
        )

    def _on_done(self, value):
        dest = (value or "").strip()
        if not dest:
            return
        dest = plat.normalize(os.path.expanduser(dest))
        if not os.path.isdir(dest):
            _status(self.window, "fileops.move.bad_dest", path=dest)
            return
        items = getattr(self, "_items", [])
        mappings = {}
        moved = 0
        failed = 0
        for item in items:
            target = os.path.join(dest, item.name)
            if plat.same_path(item.path, target):
                continue
            if os.path.exists(target):
                _report(i18n.t("fileops.move.conflict", path=target))
                failed += 1
                continue
            if item.is_dir and plat.is_within(dest, item.path):
                _report(i18n.t("fileops.move.into_self", path=item.path))
                failed += 1
                continue
            try:
                shutil.move(item.path, target)
                mappings[os.path.normcase(item.path)] = plat.normalize(target)
                moved += 1
            except (OSError, shutil.Error) as exc:
                _report("move failed %s: %s" % (item.path, exc))
                failed += 1
        ViewResolver.retarget_views(mappings)
        _refresh(self.window)
        if moved:
            _status(self.window, "fileops.move.done", count=moved)
        if failed:
            _status(self.window, "fileops.failed_count", count=failed)

    def is_visible(self, paths=None):
        return bool(paths)