import sublime
import sublime_plugin

from .. import i18n


class MySidebarSetLanguageCommand(sublime_plugin.ApplicationCommand):
    def run(self, language):
        if language not in i18n.languages():
            return
        i18n.set_language(language)
        applied = i18n.apply_menu(force=True)
        window = sublime.active_window()
        if window is not None and applied and language != "en":
            window.status_message(i18n.t("lang.applied_hint"))

    def is_checked(self, language):
        return i18n.get_language() == language


class MySidebarApplyMenusCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        i18n.apply_menu(force=True)