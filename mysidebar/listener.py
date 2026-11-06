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


def _auto_locale():
    try:
        value = _settings().get("encoding_auto_locales", encodings.DEFAULT_LOCALE)
    except Exception:
        value = encodings.DEFAULT_LOCALE
    if not isinstance(value, str):
        return encodings.DEFAULT_LOCALE
    return value


def _single_candidate():
    candidates = encodings.auto_candidates(_auto_locale())
    if len(candidates) != 1:
        return None
    return candidates[0].name


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
    encoding_detect.forget(key)


def target_encoding(view):
    if view is None or not view.is_valid():
        return None
    if view.is_scratch():
        return None
    path = view.file_name()
    if not path:
        return None
    expected = _single_candidate()
    if expected is None:
        _report("auto detect skipped: locale %s yields %d candidates"
                % (_auto_locale(), len(encodings.auto_candidates(_auto_locale()))))
        return None
    name = encoding_detect.detect(path, _auto_locale())
    if name is None:
        return None
    if name != expected:
        _report("auto detect rejected %s: not the locale candidate %s" % (name, expected))
        return None
    if view.encoding() == name:
        return None
    if _handled.get(_key(view)) == name:
        return None
    return name


STATUS_KEY = "mysidebar_encoding"


def _status_bar_enabled():
    try:
        return bool(_settings().get("encoding_status_bar", True))
    except Exception:
        return True


def _is_widget(view):
    try:
        return bool(view.settings().get("is_widget"))
    except Exception:
        return True


def refresh_status(view):
    if view is None or not view.is_valid():
        return
    if _is_widget(view):
        return
    if not _status_bar_enabled():
        try:
            view.erase_status(STATUS_KEY)
        except Exception:
            pass
        return
    try:
        name = view.encoding()
    except Exception:
        return
    if not name:
        try:
            view.erase_status(STATUS_KEY)
        except Exception:
            pass
        return
    try:
        view.set_status(STATUS_KEY, i18n.t("encoding.status_bar", encoding=name))
    except Exception:
        pass


def clear_status():
    for window in sublime.windows():
        for view in window.views():
            try:
                view.erase_status(STATUS_KEY)
            except Exception:
                pass


class MySidebarEncodingListener(sublime_plugin.EventListener):
    def on_load(self, view):
        refresh_status(view)
        self._kick(view, immediate=True)

    def on_load_async(self, view):
        refresh_status(view)
        self._kick(view, immediate=False)

    def on_activated(self, view):
        refresh_status(view)

    def on_post_save(self, view):
        refresh_status(view)

    def on_activated_async(self, view):
        refresh_status(view)

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
        refresh_status(view)
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