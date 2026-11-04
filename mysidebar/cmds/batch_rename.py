import sublime
import sublime_plugin

from .. import i18n
from ..api import SideBarSelection, ViewResolver
from ..batch import execute, plan as plan_mod, rollback
from ..batch.options import MODE_REGEX, MODE_SEQUENCE, SCOPE_NAME, SCOPE_PATH, RenameOptions
from ..ui import preview

PRESETS = (
    ("rename.preset_regex_files", MODE_REGEX, SCOPE_NAME, False, False),
    ("rename.preset_regex_files_all", MODE_REGEX, SCOPE_NAME, True, False),
    ("rename.preset_regex_path", MODE_REGEX, SCOPE_PATH, True, False),
    ("rename.preset_regex_dirs", MODE_REGEX, SCOPE_NAME, True, True),
    ("rename.preset_sequence_files", MODE_SEQUENCE, SCOPE_NAME, False, False),
    ("rename.preset_sequence_files_all", MODE_SEQUENCE, SCOPE_NAME, True, False),
    ("rename.preset_sequence_dirs", MODE_SEQUENCE, SCOPE_NAME, True, True),
)

LAST_PATTERN = "mysidebar_rename_last_pattern"
LAST_REPLACEMENT = "mysidebar_rename_last_replacement"

_undo_cache = {"entry": None}


def refresh_undo_cache():
    _undo_cache["entry"] = rollback.load_log()
    return _undo_cache["entry"]


def _status(window, key, **kwargs):
    if window is not None and window.is_valid():
        window.status_message(i18n.t(key, **kwargs))


def _report(message):
    print("[MySideBar] %s" % message)


def _settings():
    return sublime.load_settings("MySideBar.sublime-settings")


def _options_for(spec):
    key, mode, scope, recursive, include_dirs = spec
    options = RenameOptions(
        mode=mode,
        scope=scope,
        recursive=recursive,
        include_dirs=include_dirs,
    )
    if mode == MODE_SEQUENCE:
        options.prefix = _settings().get("rename_sequence_prefix", "")
        options.suffix = _settings().get("rename_sequence_suffix", "")
        options.start = 1
        options.digits = 3
    return options


def _build(window, paths, spec, pattern, replacement):
    selection = SideBarSelection(paths)
    if selection.is_empty:
        _status(window, "rename.error.no_items")
        return None
    base_options = _options_for(spec)
    options = RenameOptions(
        mode=base_options.mode,
        pattern=pattern,
        replacement=replacement,
        prefix=base_options.prefix,
        start=base_options.start,
        digits=base_options.digits,
        suffix=base_options.suffix,
        scope=base_options.scope,
        recursive=base_options.recursive,
        include_dirs=base_options.include_dirs,
    )
    targets = [item.path for item in selection.without_child_items()]
    result = plan_mod.collect(targets, options)
    if result.error:
        _status(window, result.error)
        return None
    plan_mod.compute(result, options)
    plan_mod.validate(result)
    return result


def _open_preview(window, result):
    preview.show(window, result)
    counts = result.counts()
    _status(
        window,
        "rename.preview_summary",
        total=len(result.items),
        ok=counts.get(plan_mod.STATUS_OK, 0),
        skipped=counts.get(plan_mod.STATUS_SKIPPED, 0),
        conflict=counts.get(plan_mod.STATUS_CONFLICT, 0),
        invalid=counts.get(plan_mod.STATUS_INVALID, 0),
    )


def _execute(window, result):
    if result is None:
        _status(window, "rename.nothing_to_do")
        return
    actionable = result.actionable()
    if not actionable:
        _status(window, "rename.nothing_to_do")
        return

    def on_confirm(ok):
        if not ok:
            return
        outcome = execute.execute(result, retarget=ViewResolver.retarget_pairs)
        if outcome.done():
            _status(window, "rename.execute_done", count=len(outcome.records))
        elif outcome.status == execute.RESULT_EMPTY:
            _status(window, "rename.nothing_to_do")
        else:
            _status(
                window,
                "rename.execute_aborted",
                reason=i18n.t(outcome.failure_reason, path=outcome.failure_path, error=outcome.failure_error),
            )

    window.show_ok_cancel_dialog(
        i18n.t("rename.execute_confirm", count=len(actionable)),
        i18n.t("rename.execute_all.caption"),
        on_confirm,
    )


class MySidebarRenameCommand(sublime_plugin.WindowCommand):
    def run(self, paths=None):
        self._paths = list(paths or [])
        self._spec = None
        labels = [i18n.t(spec[0]) for spec in PRESETS]
        self.window.show_quick_panel(labels, self._on_preset)

    def is_visible(self, paths=None):
        return bool(SideBarSelection(paths).without_child_items())

    def is_enabled(self, paths=None):
        return self.is_visible(paths)

    def _on_preset(self, index):
        if index < 0:
            return
        spec = PRESETS[index]
        self._spec = spec
        if spec[1] == MODE_SEQUENCE:
            result = _build(self.window, self._paths, spec, "", "")
            if result is not None:
                _open_preview(self.window, result)
            return
        initial = _settings().get(LAST_PATTERN, "")
        self.window.show_input_panel(
            i18n.t("rename.pattern_prompt"),
            initial,
            self._on_pattern,
            None,
            None,
        )

    def _on_pattern(self, text):
        self._pattern = text
        initial = _settings().get(LAST_REPLACEMENT, "")
        self.window.show_input_panel(
            i18n.t("rename.replacement_prompt"),
            initial,
            self._on_replacement,
            None,
            None,
        )

    def _on_replacement(self, text):
        settings = _settings()
        settings.set(LAST_PATTERN, self._pattern)
        settings.set(LAST_REPLACEMENT, text)
        sublime.save_settings("MySideBar.sublime-settings")
        result = _build(self.window, self._paths, self._spec, self._pattern, text)
        if result is not None:
            _open_preview(self.window, result)


class MySidebarRenameExecuteAllCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        if not preview.is_preview(view):
            _status(self.window, "rename.nothing_to_do")
            return
        _execute(self.window, preview.plan_for(view))

    def is_visible(self):
        return preview.is_preview(self.window.active_view())

    def is_enabled(self):
        return self.is_visible()


class MySidebarRenameExecuteSelectedCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        if not preview.is_preview(view):
            _status(self.window, "rename.nothing_to_do")
            return
        plan = preview.plan_for(view)
        if plan is None:
            _status(self.window, "rename.nothing_to_do")
            return
        indexes = preview.selected_indexes(view)
        if not indexes:
            _status(self.window, "rename.nothing_to_do")
            return
        from ..ui.preview_model import subset_plan
        _execute(self.window, subset_plan(plan, indexes))

    def is_visible(self):
        return preview.is_preview(self.window.active_view())

    def is_enabled(self):
        return self.is_visible()


class MySidebarRenameUndoCommand(sublime_plugin.WindowCommand):
    def run(self):
        entry = rollback.load_log()
        _undo_cache["entry"] = entry
        if entry is None:
            _status(self.window, "rename.undo_none")
            return
        ops = entry.get("ops") or []

        def on_confirm(ok):
            if not ok:
                return
            outcome = rollback.undo_last(retarget=ViewResolver.retarget_pairs)
            _undo_cache["entry"] = rollback.load_log()
            if outcome.status == rollback.UNDO_OK:
                _status(self.window, "rename.undo_done", count=outcome.reverted)
            elif outcome.status == rollback.UNDO_EMPTY:
                _status(self.window, "rename.undo_none")
            else:
                _status(self.window, "rename.undo_conflict", path=outcome.blocked_path)

        self.window.show_ok_cancel_dialog(
            i18n.t("rename.undo_confirm", count=len(ops)),
            i18n.t("rename.undo.caption"),
            on_confirm,
        )

    def is_visible(self):
        return True

    def is_enabled(self):
        return _undo_cache["entry"] is not None