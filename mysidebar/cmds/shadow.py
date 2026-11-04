import sublime


SHADOW_ENABLED = "menu_shadow_default_items"

SHADOW_TARGETS = ("delete_file", "delete_folder", "new_file_at")


def enabled():
    settings = sublime.load_settings("MySideBar.sublime-settings")
    value = settings.get(SHADOW_ENABLED, True)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def should_drop(command_name):
    if not enabled():
        return False
    return command_name in SHADOW_TARGETS