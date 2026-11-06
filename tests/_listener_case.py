import os
import shutil
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = []


def check(name, actual, expected):
    if actual != expected:
        failures.append("%s: got %r expected %r" % (name, actual, expected))


class FakeRegion:
    def __init__(self, a, b):
        self.a = a
        self.b = b


class FakeSettings:
    def __init__(self, widget=False):
        self.widget = widget

    def get(self, key, default=None):
        if key == "is_widget":
            return self.widget
        return default


class FakeWindow:
    def __init__(self):
        self.messages = []

    def is_valid(self):
        return True

    def status_message(self, msg):
        self.messages.append(msg)


class FakeView:
    _next_id = 1

    def __init__(self, path, text="", encoding="Western (Windows 1252)"):
        self._path = path
        self._text = text
        self._encoding = encoding
        self._valid = True
        self._dirty = False
        self._scratch = False
        self._loading = False
        self._id = FakeView._next_id
        FakeView._next_id += 1
        self._window = FakeWindow()
        self.reopened = []
        self.status = {}

    def is_valid(self):
        return self._valid

    def is_dirty(self):
        return self._dirty

    def is_loading(self):
        return self._loading

    def is_scratch(self):
        return self._scratch

    def set_scratch(self, value):
        self._scratch = value

    def file_name(self):
        return self._path

    def encoding(self):
        return self._encoding

    def id(self):
        return self._id

    def size(self):
        return len(self._text)

    def substr(self, region):
        return self._text[region.a : region.b]

    def settings(self):
        return FakeSettings()

    def window(self):
        return self._window

    def run_command(self, name, args=None):
        self.reopened.append((name, args))

    def set_status(self, key, text):
        self.status[key] = text

    def erase_status(self, key):
        self.status.pop(key, None)

    def apply_reopen(self):
        raw = open(self._path, "rb").read()
        if self.reopened and self.reopened[-1][1].get("encoding") == "Chinese (GB18030)":
            self._encoding = "Chinese (GB18030)"
            self._text = raw.decode("gb18030")


class _Settings:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.status_bar = True
        self.locale = "zh_CN"
        self.widget = False

    def get(self, key, default=None):
        if key == "auto_detect_encoding":
            return self.enabled
        if key == "encoding_status_bar":
            return self.status_bar
        if key == "encoding_auto_locales":
            return self.locale
        return default


ACTIVE = _Settings()

_pending = []


def _step():
    if _pending:
        fn = _pending.pop(0)
        fn()


def _pump(limit=0):
    steps = 0
    while _pending:
        fn = _pending.pop(0)
        fn()
        steps += 1
        if limit and steps >= limit:
            break


sublime = types.ModuleType("sublime")
sublime.cache_path = lambda: os.path.join(ROOT, "tmp", "_probe_cache")
sublime.load_settings = lambda name: ACTIVE
sublime.set_timeout = lambda fn, delay=0: _pending.append(fn)
sublime.Region = FakeRegion
sys.modules["sublime"] = sublime

plugin = types.ModuleType("sublime_plugin")
plugin.EventListener = type("EventListener", (), {})
plugin.TextCommand = type("TextCommand", (), {})
plugin.WindowCommand = type("WindowCommand", (), {})
sys.modules["sublime_plugin"] = plugin

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(ROOT, "mysidebar")]
sys.modules["mysidebar"] = pkg


def load(name):
    path = os.path.join(ROOT, "mysidebar", name + ".py")
    mod = types.ModuleType("mysidebar." + name)
    mod.__file__ = path
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), mod.__dict__)
    sys.modules["mysidebar." + name] = mod
    setattr(pkg, name, mod)
    return mod


load("strings")
load("i18n")
encodings = load("encodings")
load("encoding_detect")
listener = load("listener")

tmp = os.path.join(ROOT, "tmp", "_listener_case")
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)


def write(name, payload):
    path = os.path.join(tmp, name)
    with open(path, "wb") as fp:
        fp.write(payload)
    return path


def read(path):
    with open(path, "rb") as fp:
        return fp.read()


def view_for(path):
    raw = read(path)
    try:
        raw.decode("utf-8", "strict")
        encoding = "UTF-8"
    except UnicodeDecodeError:
        encoding = "Western (Windows 1252)"
    return FakeView(path, raw.decode("latin-1"), encoding=encoding)


def key_of(path):
    return os.path.normcase(os.path.abspath(path))


try:
    l = listener.MySidebarEncodingListener()

    check("reopen arg for gb18030", encodings.reopen_arg(encodings.GB18030), "Chinese (GB18030)")
    check("reopen arg unknown", encodings.reopen_arg("Shift-JIS"), None)

    gbk_text = "中文测试内容\n第二行\n"
    gbk = write("gbk.txt", gbk_text.encode("gb18030"))
    gbk_key = key_of(gbk)

    listener._forget(gbk_key)
    v1 = view_for(gbk)
    l.on_load(v1)
    check("sync load reopens before any timeout", v1.reopened, [("reopen", {"encoding": "Chinese (GB18030)"})])
    check("sync load leaves no queued work", len(_pending), 1)
    l.on_load_async(v1)
    _step()
    check("gbk reopen issued", v1.reopened, [("reopen", {"encoding": "Chinese (GB18030)"})])
    check("gbk handled recorded", listener._handled.get(gbk_key), encodings.GB18030)
    check("gbk pending cleared", gbk_key in listener._pending, False)
    v1.apply_reopen()
    _pump()
    check("gbk encoding applied", v1.encoding(), "Chinese (GB18030)")
    check("gbk text decoded", v1.substr(FakeRegion(0, v1.size())), gbk_text)
    check("gbk stays clean", v1.is_dirty(), False)
    check("gbk status message", any("reopened as" in m for m in v1.window().messages), True)
    check("gbk file untouched", read(gbk), gbk_text.encode("gb18030"))

    v1.reopened = []
    l.on_load(v1)
    l.on_load_async(v1)
    _pump()
    check("same file not reopened twice", v1.reopened, [])

    l.on_close(v1)
    check("close clears handled", gbk_key in listener._handled, False)
    v1c = view_for(gbk)
    l.on_load(v1c)
    _step()
    check("reopen after close works", v1c.reopened, [("reopen", {"encoding": "Chinese (GB18030)"})])
    _pump()

    utf8_text = "中文 UTF-8\n"
    utf8 = write("utf8.txt", utf8_text.encode("utf-8"))
    v2 = view_for(utf8)
    l.on_load(v2)
    l.on_load_async(v2)
    _pump()
    check("utf8 no reopen", v2.reopened, [])

    ascii_path = write("ascii.txt", b"plain ascii\n")
    v3 = view_for(ascii_path)
    l.on_load(v3)
    _pump()
    check("ascii no reopen", v3.reopened, [])

    already = view_for(gbk)
    already._encoding = "Chinese (GB18030)"
    l.on_load(already)
    _pump()
    check("already correct encoding no reopen", already.reopened, [])

    punct_text = "—— … ・ 　\n"
    punct = write("punct.txt", punct_text.encode("gb18030"))
    v4 = view_for(punct)
    l.on_load(v4)
    _pump(limit=1)
    v4.apply_reopen()
    _pump()
    check("punct reopened", v4.substr(FakeRegion(0, v4.size())), punct_text)

    ACTIVE.enabled = False
    v5 = view_for(gbk)
    l.on_load(v5)
    _pump()
    check("disabled skips reopen", v5.reopened, [])
    ACTIVE.enabled = True

    scratch_view = view_for(gbk)
    scratch_view._scratch = True
    l.on_load(scratch_view)
    _pump()
    check("scratch skipped", scratch_view.reopened, [])

    binary_path = write("binary.bin", b"\x00\x01\x02\x03\xff")
    v6 = view_for(binary_path)
    l.on_load(v6)
    _pump()
    check("binary skipped", v6.reopened, [])

    loading_path = write("loading.txt", gbk_text.encode("gb18030"))
    loading_key = key_of(loading_path)
    listener._forget(loading_key)
    loading_view = view_for(loading_path)
    loading_view._loading = True
    l.on_load(loading_view)
    _step()
    check("loading rescheduled not reopened", loading_view.reopened, [])
    check("loading retry queued", len(_pending), 1)
    for _ in range(listener.SETTLE_LIMIT + 2):
        _step()
    check("loading gives up when stuck", loading_view.reopened, [])
    check("loading queue drained", len(_pending), 0)
    check("loading pending released", loading_key in listener._pending, False)

    ready_view = view_for(loading_path)
    ready_view._loading = True
    l.on_load(ready_view)
    _step()
    check("loading waits first", ready_view.reopened, [])
    ready_view._loading = False
    _step()
    check("loading resumes when ready", ready_view.reopened, [("reopen", {"encoding": "Chinese (GB18030)"})])
    _pump()

    verify_path = write("verify.txt", gbk_text.encode("gb18030"))
    verify_key = key_of(verify_path)
    listener._forget(verify_key)
    v7 = view_for(verify_path)
    l.on_load(v7)
    _step()
    _pending[:] = []
    l._verify(v7, verify_key, encodings.GB18030, listener.VERIFY_LIMIT)
    check("verify gives up clears handled", verify_key in listener._handled, False)

    check("no pending leaks", listener._pending, {})

    status_path = write("status.txt", gbk_text.encode("gb18030"))
    status_key = key_of(status_path)
    listener._forget(status_key)
    sv = view_for(status_path)
    sv._encoding = encodings.GB18030
    l.on_activated(sv)
    check("status bar shows encoding", sv.status.get(listener.STATUS_KEY), encodings.GB18030)

    sv_utf8 = view_for(status_path)
    sv_utf8._encoding = encodings.UTF8
    l.on_activated(sv_utf8)
    check("status bar follows encoding", sv_utf8.status.get(listener.STATUS_KEY), encodings.UTF8)

    widget_settings = FakeSettings(widget=True)
    wv = view_for(status_path)
    wv.settings = lambda: widget_settings
    l.on_activated(wv)
    check("widget view untouched", wv.status.get(listener.STATUS_KEY), None)

    ACTIVE.status_bar = False
    off_view = view_for(status_path)
    l.on_activated(off_view)
    check("status bar disabled erases", off_view.status.get(listener.STATUS_KEY), None)
    ACTIVE.status_bar = True

    before = sv.reopened[:]
    sv._encoding = encodings.GB18030
    l.on_activated(sv)
    check("activated does not reopen", sv.reopened, before)

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("LISTENER_FAILURES", len(failures))
for item in failures:
    print(item)
sys.exit(1 if failures else 0)