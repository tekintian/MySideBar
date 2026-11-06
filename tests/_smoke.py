import sys
import types
import traceback

sublime = types.ModuleType("sublime")


class _Settings(object):
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def has(self, key):
        return key in self._data

    def erase(self, key):
        self._data.pop(key, None)

    def add_on_change(self, key, cb):
        pass

    def clear_on_change(self, key):
        pass

    def to_dict(self):
        return dict(self._data)


PACKAGES = "/tmp/fake_packages"
_settings = _Settings({})
sublime.load_settings = lambda name: _settings
sublime.Settings = _Settings
sublime.set_timeout = lambda fn, delay=0: None
sublime.set_timeout_async = lambda fn, delay=0: None
sublime.status_message = lambda msg: None
sublime.message_dialog = lambda msg: None
sublime.ok_cancel_dialog = lambda msg, ok_title="": True
sublime.error_message = lambda msg: None
sublime.packages_path = lambda: PACKAGES
sublime.installed_packages_path = lambda: "/tmp/fake_installed"
sublime.executable_path = lambda: "/tmp/fake_sublime"
sublime.version = lambda: "4215"
sublime.platform = lambda: "osx"
sublime.arch = lambda: "x64"
sublime.python_version = lambda: "3.8"


class _Window(object):
    def id(self):
        return 1

    def is_valid(self):
        return True

    def status_message(self, msg):
        pass

    def show_quick_panel(self, items, on_select, *args, **kw):
        pass

    def run_command(self, cmd, args=None):
        pass

    def active_view(self):
        return None

    def create_output_panel(self, name):
        return None


class _View(object):
    def __init__(self):
        self._settings = _Settings({})

    def id(self):
        return 1

    def is_valid(self):
        return True

    def settings(self):
        return self._settings

    def run_command(self, cmd, args=None):
        pass

    def window(self):
        return _Window()

    def file_name(self):
        return None

    def substr(self, region):
        return ""

    def size(self):
        return 0

    def change_count(self):
        return 0


sublime.active_window = lambda: _Window()
sublime.Window = _Window
sublime.View = _View
sublime.Region = lambda a=0, b=0: (a, b)

pl = types.ModuleType("sublime_plugin")


class _Command(object):
    def is_enabled(self, *a, **kw):
        return True

    def is_visible(self, *a, **kw):
        return True

    def is_checked(self, *a, **kw):
        return False

    def description(self, *a, **kw):
        return None

    def want_event(self):
        return False


class _ApplicationCommand(_Command):
    def run(self, *a, **kw):
        pass


class _WindowCommand(_Command):
    def __init__(self, window=None):
        self.window = window

    def run(self, *a, **kw):
        pass


class _TextCommand(_Command):
    def __init__(self, view=None):
        self.view = view

    def run(self, edit, *a, **kw):
        pass


class _EventListener(object):
    pass


class _ViewEventListener(object):
    def __init__(self, view=None):
        self.view = view


pl.Command = _Command
pl.ApplicationCommand = _ApplicationCommand
pl.WindowCommand = _WindowCommand
pl.TextCommand = _TextCommand
pl.EventListener = _EventListener
pl.ViewEventListener = _ViewEventListener
pl.TextInputHandler = _Command
pl.ListInputHandler = _Command

sys.modules["sublime"] = sublime
sys.modules["sublime_plugin"] = pl

import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYMLINK = os.path.join(PACKAGES, "MySideBar")
if not os.path.isdir(PACKAGES):
    os.makedirs(PACKAGES)
if not os.path.exists(SYMLINK):
    os.symlink(BASE, SYMLINK)

sys.path.insert(0, BASE)

import importlib.util

spec = importlib.util.spec_from_file_location("MySideBar", os.path.join(SYMLINK, "MySideBar.py"))
entry = importlib.util.module_from_spec(spec)
sys.modules["MySideBar"] = entry
try:
    spec.loader.exec_module(entry)
    print("ENTRY_IMPORT_OK")
except Exception:
    print("ENTRY_IMPORT_FAILED")
    traceback.print_exc()
    sys.exit(1)

import mysidebar

print("VISIBLE_COMMANDS", len([n for n in vars(entry) if not n.startswith('_') and isinstance(vars(entry)[n], type) and issubclass(vars(entry)[n], (pl.Command, pl.ApplicationCommand))]))
for n in sorted(vars(entry)):
    v = vars(entry)[n]
    if not n.startswith('_') and isinstance(v, type):
        if issubclass(v, (pl.Command, pl.ApplicationCommand)) and v.__module__ != __name__:
            print("  ", n)

try:
    entry.plugin_loaded()
    print("PLUGIN_LOADED_OK")
except Exception:
    print("PLUGIN_LOADED_FAILED")
    traceback.print_exc()
    sys.exit(2)