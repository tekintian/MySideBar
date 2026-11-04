import os
import shutil

import sublime
import sublime_plugin

from .. import clipboard
from .. import i18n
from ..api import SideBarProject, SideBarSelection, ViewResolver
from .. import platform as plat


def _report(message):
    print("[MySideBar] %s" % message)


def _status(window, message):
    if window is not None and window.is_valid():
        window.status_message(message)


def _refresh(window):
    if window is not None and window.is_valid():
        window.run_command("refresh_folder_list")


def _targets(paths):
    selection = SideBarSelection(paths)
    return selection.without_child_items()


def _dedupe(paths):
    seen = set()
    result = []
    for path in paths:
        key = os.path.normcase(plat.normalize(path))
        if key in seen:
            continue
        seen.add(key)
        result.append(plat.normalize(path))
    return result


class MySidebarCutCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        targets = _targets(paths)
        if not targets:
            return
        clipboard.set_cut([item.path for item in targets])
        _status(self.window, i18n.t("clipboard.cut.done", count=len(targets)))

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarCopyCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        targets = _targets(paths)
        if not targets:
            return
        clipboard.set_copy([item.path for item in targets])
        _status(self.window, i18n.t("clipboard.copy.done", count=len(targets)))

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarPasteCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        if not clipboard.has_clipboard():
            _status(self.window, i18n.t("clipboard.nothing_to_paste"))
            return
        mode, sources = clipboard.consume()
        targets = self._target_dirs(paths)
        if not targets:
            _status(self.window, i18n.t("clipboard.paste.no_target"))
            return
        result = {"copied": 0, "moved": 0, "failed": 0, "mappings": {}}
        for source in sources:
            if not os.path.exists(source):
                _report(i18n.t("clipboard.paste.missing", path=source))
                result["failed"] += 1
                continue
            if not self._precheck(source, targets, result, mode == clipboard.CUT):
                continue
            if mode == clipboard.CUT:
                self._move(source, targets, result)
            else:
                for dest_dir in targets:
                    self._copy_stage(source, dest_dir, result)
        self._apply_mappings(result["mappings"])
        _refresh(self.window)
        if result["copied"]:
            _status(self.window, i18n.t("clipboard.paste.copied", count=result["copied"]))
        if result["moved"]:
            _status(self.window, i18n.t("clipboard.paste.moved", count=result["moved"]))
        if result["failed"]:
            _status(self.window, i18n.t("clipboard.paste.failed", count=result["failed"]))

    def _target_dirs(self, paths):
        selection = SideBarSelection(paths)
        if selection.is_empty:
            return []
        dirs = []
        for item in selection.without_child_items():
            dirs.append(item.path if item.is_dir else item.dirname)
        return _dedupe(dirs)

    def _copy_targets(self, source, targets):
        source_dir = os.path.dirname(source)
        result = []
        for dest_dir in targets:
            if not plat.same_path(dest_dir, source_dir):
                result.append(dest_dir)
        return result

    def _conflict(self, path):
        _report(i18n.t("clipboard.paste_conflict", path=path))

    def _precheck(self, source, targets, result, moving):
        source_dir = os.path.dirname(source)
        checked = self._copy_targets(source, targets) if moving else list(targets)
        for dest_dir in checked:
            if os.path.isdir(source) and plat.is_within(dest_dir, source):
                _report(i18n.t("clipboard.paste.into_self", path=source))
                result["failed"] += 1
                return False
            if plat.same_path(dest_dir, source_dir):
                continue
            target = os.path.join(dest_dir, os.path.basename(source))
            if os.path.exists(target):
                self._conflict(target)
                result["failed"] += 1
                return False
        return True

    def _move(self, source, targets, result):
        source_dir = os.path.dirname(source)
        candidates = self._copy_targets(source, targets)
        if not candidates:
            _report(i18n.t("clipboard.paste.no_target"))
            result["failed"] += 1
            return
        dest_dir = candidates[0]
        target = os.path.join(dest_dir, os.path.basename(source))
        if os.path.isdir(source) and os.path.exists(target):
            self._conflict(target)
            result["failed"] += 1
            return
        try:
            shutil.move(source, target)
        except (OSError, shutil.Error) as exc:
            _report("paste move failed %s: %s" % (source, exc))
            result["failed"] += 1
            return
        result["moved"] += 1
        result["mappings"][os.path.normcase(source)] = plat.normalize(target)

    def _copy_stage(self, source, dest_dir, result):
        if plat.same_path(dest_dir, os.path.dirname(source)):
            return
        target = os.path.join(dest_dir, os.path.basename(source))
        try:
            self._copy(source, target)
        except (OSError, shutil.Error) as exc:
            _report("paste copy failed %s: %s" % (source, exc))
            result["failed"] += 1
            return
        result["copied"] += 1

    def _copy(self, source, target):
        if os.path.isdir(source):
            if os.path.exists(target):
                shutil.copytree(source, target, dirs_exist_ok=True, symlinks=True)
            else:
                shutil.copytree(source, target, symlinks=True)
            return
        shutil.copy2(source, target)

    def _apply_mappings(self, mappings):
        if not mappings:
            return
        ViewResolver.retarget_views(mappings)

    def is_visible(self, paths=None):
        return bool(paths) and clipboard.has_clipboard()


class MySidebarCopyRelativePathCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        project = SideBarProject(self.window)
        lines = []
        missing = 0
        for item in items:
            rel = project.relative_path(item.path)
            if rel is None:
                _report(i18n.t("clipboard.relative_path.no_root", path=item.path))
                missing += 1
                continue
            lines.append(rel)
        if lines:
            clipboard.set_clipboard_text("\n".join(lines))
        if missing:
            _status(self.window, i18n.t("clipboard.relative_path.skipped", count=missing))

    def is_visible(self, paths=None):
        if not paths:
            return False
        project = SideBarProject(self.window)
        return any(project.find_root(p) is not None for p in paths)


class MySidebarCopyFileNameCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        names = [item.name for item in items if item.name]
        if names:
            clipboard.set_clipboard_text("\n".join(names))

    def is_visible(self, paths=None):
        return bool(paths)