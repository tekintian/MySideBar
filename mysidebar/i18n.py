import json
import os

import sublime

from . import strings


_state = {"language": None}

_MENU_TARGETS = (
    "Side Bar.sublime-menu",
    "Tab Context.sublime-menu",
    "Tab Sidebar Context.sublime-menu",
    "Context.sublime-menu",
)

_STALE_MENU_TARGETS = (
    "Main.sublime-menu",
)

_CAPTION_KEYS = {value: key for key, value in strings.STRINGS[strings.DEFAULT_LANGUAGE].items() if key.endswith(".caption")}


def t(key, **kwargs):
    lang = _state["language"]
    table = strings.STRINGS.get(lang) if lang else None
    if table is None:
        table = strings.STRINGS[strings.DEFAULT_LANGUAGE]
    template = table.get(key)
    if template is None:
        template = strings.STRINGS[strings.DEFAULT_LANGUAGE].get(key)
        if template is None:
            return key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def caption(key):
    return t(key)


def get_language():
    return _state["language"]


def set_language(lang, persist=True):
    if lang is not None and lang not in strings.LANGUAGES:
        lang = strings.DEFAULT_LANGUAGE
    _state["language"] = lang
    if not persist:
        return
    settings = sublime.load_settings("MySideBar.sublime-settings")
    settings.set("ui_language", lang)
    sublime.save_settings("MySideBar.sublime-settings")


def languages():
    return strings.LANGUAGES


def is_first_run():
    return _state["language"] is None


def _user_menu_dir():
    return os.path.join(sublime.packages_path(), "User", "MySideBar")


def _marker_path():
    return os.path.join(_user_menu_dir(), ".applied")


def _pkg_root():
    return os.path.join(sublime.packages_path(), "MySideBar")


def apply_menu(force=False):
    lang = _state["language"]
    target_dir = _user_menu_dir()

    needs_translation = lang is not None and lang != strings.DEFAULT_LANGUAGE
    needs_shadow = _shadow_enabled()

    if not needs_translation and not needs_shadow:
        _remove_user_menus(target_dir)
        return True

    if not os.path.isdir(target_dir):
        try:
            os.makedirs(target_dir)
        except OSError as exc:
            _report("menu dir create failed: %s" % exc)
            return False

    marker = _marker_path()
    if not force and os.path.isfile(marker):
        try:
            with open(marker, "r", encoding="utf-8") as fp:
                if fp.read().strip() == _signature():
                    return True
        except OSError:
            pass

    written = 0
    for name in _MENU_TARGETS:
        src = os.path.join(_pkg_root(), name)
        if not os.path.isfile(src):
            _report("menu source missing: %s" % name)
            continue
        try:
            with open(src, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, ValueError) as exc:
            _report("menu source unreadable %s: %s" % (name, exc))
            continue
        transformed = _transform_menu(data, needs_translation, needs_shadow)
        if not transformed:
            _report("menu became empty after shadow: %s" % name)
            continue
        try:
            dst = os.path.join(target_dir, name)
            with open(dst, "w", encoding="utf-8") as fp:
                json.dump(transformed, fp, ensure_ascii=False, indent="\t")
                fp.write("\n")
            written += 1
        except OSError as exc:
            _report("menu write failed %s: %s" % (name, exc))

    try:
        with open(marker, "w", encoding="utf-8") as fp:
            fp.write(_signature())
    except OSError as exc:
        _report("menu marker write failed: %s" % exc)

    _report("menu applied: lang=%s files=%d shadow=%s" % (lang, written, needs_shadow))
    return written > 0


def _shadow_enabled():
    try:
        from .cmds import shadow
        return shadow.enabled()
    except Exception as exc:
        _report("shadow unavailable: %s" % exc)
        return False


def _signature():
    shadow_flag = "1" if _shadow_enabled() else "0"
    targets = ",".join(_MENU_TARGETS)
    return "%s:%s:%s:%s" % (_state["language"], sublime.version(), shadow_flag, targets)


def _transform_menu(node, translate, shadow):
    if isinstance(node, list):
        result = []
        pending_separator = False
        for item in node:
            if isinstance(item, dict) and _is_separator(item):
                pending_separator = bool(result)
                continue
            transformed = _transform_menu(item, translate, shadow)
            if transformed is None:
                continue
            if pending_separator and result and not _is_separator(result[-1]):
                result.append({"caption": "-"})
            pending_separator = False
            result.append(transformed)
        return result
    if not isinstance(node, dict):
        return node

    command_name = node.get("command")
    if isinstance(command_name, str) and shadow and _should_drop(command_name):
        return None

    out = {}
    for key, value in node.items():
        if key == "caption" and isinstance(value, str):
            out[key] = _translate_caption(value) if translate else value
        elif key == "children":
            children = _transform_menu(value, translate, shadow)
            if not children:
                return None
            out[key] = children
        else:
            out[key] = value
    return out


def _is_separator(node):
    return node.get("caption") == "-" and not node.get("command")


def _should_drop(command_name):
    try:
        from .cmds import shadow
        return shadow.should_drop(command_name)
    except Exception as exc:
        _report("shadow check failed: %s" % exc)
        return False


def _remove_user_menus(target_dir):
    if not os.path.isdir(target_dir):
        return
    for name in _MENU_TARGETS + _STALE_MENU_TARGETS:
        path = os.path.join(target_dir, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError as exc:
                _report("menu remove failed %s: %s" % (name, exc))
    marker = _marker_path()
    if os.path.isfile(marker):
        try:
            os.remove(marker)
        except OSError as exc:
            _report("menu marker remove failed: %s" % exc)
    try:
        os.rmdir(target_dir)
    except OSError:
        pass


def clear_applied_menu():
    if _state["language"] is not None and _state["language"] != strings.DEFAULT_LANGUAGE:
        return
    if _shadow_enabled():
        return
    _remove_user_menus(_user_menu_dir())


def _translate_caption(caption_text, prefix=None):
    key = _CAPTION_KEYS.get(caption_text)
    if key is None:
        return caption_text
    if prefix is not None and not key.startswith(prefix + "."):
        return caption_text
    return t(key)


def _report(message):
    print("[MySideBar] %s" % message)