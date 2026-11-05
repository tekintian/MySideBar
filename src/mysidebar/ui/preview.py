import sublime

from .. import i18n
from . import preview_model

SYNTAX_FILE = "MySideBar Rename Preview.sublime-syntax"
PREVIEW_FLAG = "mysidebar_rename_preview"
_plan_cache = {}


def _remember_plan(view, plan):
    _plan_cache[view.id()] = plan


def _recall_plan(view):
    return _plan_cache.get(view.id())


def is_preview(view):
    return view is not None and bool(view.settings().get(PREVIEW_FLAG))


HEADER_BLANK_LINES = 1


def render(plan):
    lines = preview_model.lines_for(plan, i18n.t)
    summary = preview_model.summary_text(plan, i18n.t("rename.preview_summary"))
    separator = "\n" * (HEADER_BLANK_LINES + 1)
    return summary + separator + "\n".join(lines) + "\n"


def header_lines():
    return HEADER_BLANK_LINES + 1


def show(window, plan):
    view = _find_existing(window)
    if view is None:
        view = window.new_file()
        view.set_scratch(True)
        view.set_name(i18n.t("rename.preview_title"))
        view.settings().set(PREVIEW_FLAG, True)
    view.settings().set("word_wrap", False)
    view.settings().set("line_numbers", False)
    view.settings().set("gutter", False)
    view.settings().set("highlight_line", True)
    view.set_read_only(False)
    view.run_command("select_all")
    view.run_command("left_delete")
    view.run_command("append", {"characters": render(plan), "force": True})
    view.assign_syntax("Packages/MySideBar/" + SYNTAX_FILE)
    view.set_read_only(True)
    _remember_plan(view, plan)
    window.focus_view(view)
    return view


def _find_existing(window):
    for view in window.views():
        if is_preview(view):
            return view
    return None


def plan_for(view):
    return _recall_plan(view)


def selected_indexes(view):
    plan = plan_for(view)
    if plan is None:
        return []
    rows = []
    for region in view.sel():
        first = view.rowcol(region.begin())[0]
        last = view.rowcol(region.end())[0]
        for row in range(first, last + 1):
            rows.append(row)
    return preview_model.selected_indexes(plan, _data_rows(rows))


def _data_rows(rows):
    offset = header_lines()
    result = []
    for row in rows:
        index = row - offset
        if index >= 0:
            result.append(index)
    return result