import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sublime = types.ModuleType("sublime")
sublime.version = lambda: "4173"
sublime.load_settings = lambda name: {}
sublime.active_window = lambda: None
sublime.set_timeout = lambda fn, delay=0: None
sys.modules["sublime"] = sublime

plugin = types.ModuleType("sublime_plugin")


class _Base:
    pass


for _name in (
    "ApplicationCommand",
    "WindowCommand",
    "TextCommand",
    "EventListener",
    "ViewEventListener",
):
    setattr(plugin, _name, type(_name, (_Base,), {}))
plugin.TextInputHandler = type("TextInputHandler", (_Base,), {})
sys.modules["sublime_plugin"] = plugin

entry_path = os.path.join(ROOT, "MySideBar.py")
entry = types.ModuleType("MySideBar")
entry.__file__ = entry_path
exec(compile(open(entry_path, encoding="utf-8").read(), entry_path, "exec"), entry.__dict__)

loaded = sorted(
    name for name in sys.modules if name == "mysidebar" or name.startswith("mysidebar.")
)
print("LOADED_MODULES", len(loaded))
for name in loaded:
    print(" ", name)

expected = ["mysidebar.listener", "mysidebar.encoding_detect"]
missing = [n for n in expected if n not in sys.modules]
print("MISSING", missing)
print("BOOTSTRAP_OK", entry.mysidebar is not None)