import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "mysidebar")

sublime = types.ModuleType("sublime")
sublime.version = lambda: "4173"
sys.modules["sublime"] = sublime

plugin = types.ModuleType("sublime_plugin")


class _Base:
    pass


class ApplicationCommand(_Base):
    pass


class WindowCommand(_Base):
    pass


class TextCommand(_Base):
    pass


class EventListener(_Base):
    pass


class ViewEventListener(_Base):
    pass


plugin.ApplicationCommand = ApplicationCommand
plugin.WindowCommand = WindowCommand
plugin.TextCommand = TextCommand
plugin.EventListener = EventListener
plugin.ViewEventListener = ViewEventListener
sys.modules["sublime_plugin"] = plugin

failures = []


def check(label, got, expected):
    if got != expected:
        failures.append("%s: got %r expected %r" % (label, got, expected))


entry_path = os.path.join(ROOT, "MySideBar.py")
entry = types.ModuleType("MySideBar")
entry.__file__ = entry_path

code = compile(open(entry_path, encoding="utf-8").read(), entry_path, "exec")
exec(code, entry.__dict__)

exported = {k: v for k, v in entry.__dict__.items() if isinstance(v, type)}
listener_cls = exported.get("MySidebarEncodingListener")
check("listener exported to entry", listener_cls is not None, True)
if listener_cls is not None:
    check("listener is EventListener", issubclass(listener_cls, EventListener), True)
    check("listener has on_load_async", hasattr(listener_cls, "on_load_async"), True)
    check(
        "listener module correct",
        listener_cls.__module__,
        "mysidebar.listener",
    )

commands = [
    name
    for name, value in exported.items()
    if isinstance(value, type) and value.__module__.startswith("mysidebar.")
]
check("commands still exported", len(commands) > 0, True)

print("ENTRY_FAILURES", len(failures))
for item in failures:
    print(item)