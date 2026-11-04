import sublime


SETTINGS_FILE = "MySideBar.sublime-settings"
SHADOW_ENABLED = "menu_shadow_default_items"

SHADOW_TARGETS = ("delete_file", "delete_folder", "new_file_at")


def enabled():
    settings = sublime.load_settings(SETTINGS_FILE)
    value = settings.get(SHADOW_ENABLED, True)
    return _as_bool(value)


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def should_drop(command_name):
    return command_name in SHADOW_TARGETS