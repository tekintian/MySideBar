import importlib
import pkgutil

import sublime

from . import i18n


def on_plugin_loaded():
    _load_commands()
    _refresh_rename_undo()
    settings = sublime.load_settings("MySideBar.sublime-settings")
    language = settings.get("ui_language")
    if language not in i18n.languages():
        language = None

    i18n.set_language(language, persist=False)
    i18n.apply_menu()

    if language is None:
        window = sublime.active_window()
        if window is not None:
            sublime.set_timeout(lambda: _prompt_language(window), 100)


def on_plugin_unloaded():
    i18n.clear_applied_menu()


def _load_commands():
    from . import cmds
    for info in pkgutil.iter_modules(cmds.__path__):
        if info.ispkg:
            continue
        try:
            importlib.import_module("%s.cmds.%s" % (__name__, info.name))
        except Exception:
            _report_import_failure(info.name)


def _report_import_failure(name):
    import traceback
    print("[MySideBar] FAILED to load command module: %s" % name)
    traceback.print_exc()


def _refresh_rename_undo():
    try:
        from .cmds import batch_rename
        batch_rename.refresh_undo_cache()
    except Exception:
        _report_import_failure("batch_rename.refresh_undo_cache")


def _prompt_language(window):
    items = [i18n.t("lang.english"), i18n.t("lang.zh_cn"), i18n.t("lang.zh_tw")]
    window.show_quick_panel(
        items, lambda choice: _on_language_chosen(window, choice), 0, -1, i18n.t("lang.prompt")
    )


def _on_language_chosen(window, choice):
    mapping = {0: "en", 1: "zh_CN", 2: "zh_TW"}
    language = mapping.get(choice, "en")
    i18n.set_language(language)
    applied = i18n.apply_menu(force=True)
    if applied and language != "en" and window.is_valid():
        window.status_message(i18n.t("lang.applied_hint"))