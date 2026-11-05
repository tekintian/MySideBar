import sublime
import sublime_plugin

from .. import i18n
from .. import trash
from .. import platform as plat
from ..api import SideBarSelection, ViewResolver


def _report(message):
    print("[MySideBar] %s" % message)


def _status(window, message):
    if window is not None and window.is_valid():
        window.status_message(message)


def _refresh(window):
    if window is not None and window.is_valid():
        window.run_command("refresh_folder_list")


def _targets(paths):
    return SideBarSelection(paths).without_child_items()


class MySidebarRevealInFileManagerCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        failed = 0
        for item in items:
            if not plat.reveal(item.path, dir_only=item.is_dir):
                _report(i18n.t("reveal.failed", path=item.path))
                failed += 1
        if failed:
            _status(self.window, i18n.t("reveal.failed_count", count=failed))

    def is_visible(self, paths=None):
        return bool(paths)


class MySidebarMoveToTrashCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        items = _targets(paths)
        if not items:
            return
        settings = sublime.load_settings("MySideBar.sublime-settings")
        if not settings.get("confirm_before_trash", True):
            self._trash(items)
            return
        confirmed = sublime.ok_cancel_dialog(
            i18n.t("delete.confirm", count=len(items)),
            i18n.t("delete.confirm_ok"),
        )
        self._on_confirmed(confirmed, items)

    def _on_confirmed(self, confirmed, items):
        if not confirmed:
            _status(self.window, i18n.t("delete.cancelled", count=len(items)))
            return
        self._trash(items)

    def _trash(self, items):
        if not trash.is_available():
            confirmed = sublime.ok_cancel_dialog(
                i18n.t("delete.permanent_confirm", count=len(items)),
                i18n.t("delete.permanent_ok"),
            )
            self._permanent(confirmed, items)
            return
        leftovers = []
        failures = []
        for item in items:
            ok, reason = trash.send(item.path)
            if ok:
                continue
            leftovers.append(item)
            failures.append((item.path, reason))
        if leftovers:
            confirmed = sublime.ok_cancel_dialog(
                i18n.t("delete.permanent_confirm", count=len(leftovers)),
                i18n.t("delete.permanent_ok"),
            )
            self._permanent(confirmed, leftovers, failures)
            return
        self._finish(items, failures)

    def _permanent(self, confirmed, items, failures=None):
        failures = list(failures or [])
        if not confirmed:
            _status(self.window, i18n.t("delete.cancelled", count=len(items)))
            self._finish([], failures)
            return
        for item in items:
            ok, reason = trash.permanent_delete(item.path)
            if not ok:
                failures.append((item.path, reason))
                continue
        self._finish(items, failures)

    def _finish(self, deleted, failures):
        for path, reason in failures:
            _report(i18n.t("delete.failed", path=path, reason=reason))
        removed = [i.path for i in deleted if not i.exists]
        if removed:
            ViewResolver.close_views_for_paths(removed)
        _refresh(self.window)
        if removed:
            _status(self.window, i18n.t("delete.done", count=len(removed)))
        if failures:
            _status(self.window, i18n.t("delete.failed_count", count=len(failures)))

    def is_visible(self, paths=None):
        return bool(paths)