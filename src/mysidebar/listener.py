import os

import sublime
import sublime_plugin

from . import encoding_detect
from . import encodings
from . import i18n

SETTLE_DELAY = 60
SETTLE_LIMIT = 20
VERIFY_DELAY = 120
VERIFY_LIMIT = 30

_handled = {}
_pending = {}


def _normalize(path):
    return os.path.normcase(os.path.abspath(path))


def _settings():
    return sublime.load_settings("MySideBar.sublime-settings")


def _enabled():
    try:
        return bool(_settings().get("auto_detect_encoding", True))
    except Exception:
        return True


def _report(message):
    print("[MySideBar] %s" % message)


def _key(view):
    path = view.file_name()
    if not path:
        return None
    return _normalize(path)


def _busy(key):
    return key in _pending


def _mark_pending(key, view):
    _pending[key] = view.id()


def _clear_pending(key):
    _pending.pop(key, None)


def _mark_handled(key, name):
    _handled[key] = name


def _forget(key):
    _handled.pop(key, None)
    _pending.pop(key, None)


def target_encoding(view):
    if view is None or not view.is_valid():
        return None
    if view.is_scratch():
        return None
    path = view.file_name()
    if not path:
        return None
    name = encoding_detect.detect(path)
    if name is None:
        return None
    if name not in encodings.CONVERTIBLE:
        return None
    if view.encoding() == name:
        return None
    if _handled.get(_key(view)) == name:
        return None
    return name


class MySidebarEncodingListener(sublime_plugin.EventListener):
    def on_load(self, view):
        self._kick(view, immediate=True)

    def on_load_async(self, view):
        self._kick(view, immediate=False)

    def _kick(self, view, immediate):
        if not _enabled():
            return
        key = _key(view)
        if key is None or _busy(key):
            return
        if key in _handled:
            return
        _mark_pending(key, view)
        if immediate and not view.is_loading():
            self._inspect(view, key, 0)
            return
        sublime.set_timeout(lambda: self._inspect(view, key, 0), SETTLE_DELAY)

    def _inspect(self, view, key, attempt):
        if not view.is_valid():
            _clear_pending(key)
            return
        path = view.file_name()
        if _key(view) != key:
            _clear_pending(key)
            return
        if key in _handled:
            _clear_pending(key)
            return
        if view.is_loading():
            if attempt >= SETTLE_LIMIT:
                _clear_pending(key)
                _report("still loading, skip %s" % path)
                return
            sublime.set_timeout(lambda: self._inspect(view, key, attempt + 1), SETTLE_DELAY)
            return
        name = target_encoding(view)
        if name is None:
            _clear_pending(key)
            return
        _report("reopen %s as %s" % (path, name))
        if not encodings.reopen_view(view, name):
            _clear_pending(key)
            _report("reopen rejected %s for %s" % (name, path))
            return
        _clear_pending(key)
        _mark_handled(key, name)
        sublime.set_timeout(lambda: self._verify(view, key, name, 0), VERIFY_DELAY)

    def _verify(self, view, key, name, attempt):
        if not view.is_valid():
            _clear_pending(key)
            _forget(key)
            return
        if view.is_loading() or view.encoding() != name:
            if attempt >= VERIFY_LIMIT:
                _clear_pending(key)
                _forget(key)
                _report("reopen did not take effect for %s" % view.file_name())
                return
            sublime.set_timeout(lambda: self._verify(view, key, name, attempt + 1), VERIFY_DELAY)
            return
        _clear_pending(key)
        window = view.window()
        if window is not None and window.is_valid():
            window.status_message(
                i18n.t(
                    "encoding.auto_detected",
                    path=view.file_name() or "",
                    encoding=name,
                )
            )

    def on_close(self, view):
        key = _key(view)
        if key is None:
            return
        _forget(key)