import os

import sublime

from . import platform as plat


_state = {"mode": None, "paths": ()}

COPY = "copy"
CUT = "cut"


def set_copy(paths):
    _state["mode"] = COPY
    _state["paths"] = tuple(plat.normalize(p) for p in (paths or []) if p)


def set_cut(paths):
    _state["mode"] = CUT
    _state["paths"] = tuple(plat.normalize(p) for p in (paths or []) if p)


def clear():
    _state["mode"] = None
    _state["paths"] = ()


def mode():
    return _state["mode"]


def is_cut():
    return _state["mode"] == CUT


def pending_paths():
    return tuple(_state["paths"])


def is_cut_path(path):
    if _state["mode"] != CUT:
        return False
    target = os.path.normcase(plat.normalize(path))
    for item in _state["paths"]:
        if os.path.normcase(item) == target:
            return True
    return False


def has_clipboard():
    return _state["mode"] is not None and bool(_state["paths"])


def consume():
    result = (COPY if _state["mode"] == COPY else CUT, tuple(_state["paths"]))
    clear()
    return result


def set_clipboard_text(text):
    try:
        sublime.set_clipboard(text)
        return True
    except (RuntimeError, ValueError) as exc:
        print("[MySideBar] clipboard write failed: %s" % exc)
        return False