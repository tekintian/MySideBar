import json
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGETS = (
    "Side Bar.sublime-menu",
    "Tab Context.sublime-menu",
    "Tab Sidebar Context.sublime-menu",
)

sandbox = tempfile.mkdtemp(prefix="mysidebar_menu_")
for name in TARGETS:
    source = os.path.join(ROOT, name)
    if os.path.isfile(source):
        shutil.copy2(source, os.path.join(sandbox, name))
originals = {}
for name in TARGETS:
    path = os.path.join(sandbox, name)
    if os.path.isfile(path):
        originals[name] = open(path, encoding="utf-8").read()

sublime_stub = types.ModuleType("sublime")
sublime_stub.version = lambda: "4173"
sublime_stub.packages_path = lambda: sandbox
sublime_stub.load_settings = lambda name: types.SimpleNamespace(get=lambda k, d=None: d)
sublime_stub.save_settings = lambda name: None
sys.modules["sublime"] = sublime_stub

pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.join(ROOT, "mysidebar")]
sys.modules["mysidebar"] = pkg

i18n_src = open(os.path.join(ROOT, "mysidebar", "i18n.py"), encoding="utf-8").read()
i18n_mod = types.ModuleType("mysidebar.i18n")
i18n_mod.__file__ = os.path.join(ROOT, "mysidebar", "i18n.py")
exec(compile(i18n_src, i18n_mod.__file__, "exec"), i18n_mod.__dict__)
sys.modules["mysidebar.i18n"] = i18n_mod
pkg.i18n = i18n_mod

strings_src = open(os.path.join(ROOT, "mysidebar", "strings.py"), encoding="utf-8").read()
strings_mod = types.ModuleType("mysidebar.strings")
exec(compile(strings_src, "strings.py", "exec"), strings_mod.__dict__)
sys.modules["mysidebar.strings"] = strings_mod
i18n_mod.strings = strings_mod

i18n_mod._pkg_root = lambda: sandbox
i18n_mod._backup_dir = lambda: os.path.join(sandbox, "..", "tmp", "menu_backup_test")
overlay_dir = os.path.join(sandbox, "User", "MySideBar")
i18n_mod._user_menu_dir = lambda: overlay_dir
backup_dir = i18n_mod._backup_dir()
if os.path.isdir(backup_dir):
    shutil.rmtree(backup_dir)

failures = []


def check(label, got, expected):
    if got != expected:
        failures.append("%s: got %r expected %r" % (label, got, expected))


i18n_mod._state["language"] = "zh_CN"
applied = i18n_mod.apply_menu(force=True)
check("apply zh_CN ok", applied, True)

translated = open(os.path.join(overlay_dir, "Side Bar.sublime-menu"), encoding="utf-8").read()
data = json.loads(translated)
labels = [node["caption"] for node in data if isinstance(node, dict) and node.get("caption") not in (None, "-")]
check("captions translated", any("\u91cd" in l for l in labels) or any("\u6587\u4ef6" in l for l in labels), True)
check("package menu untouched", open(os.path.join(sandbox, "Side Bar.sublime-menu"), encoding="utf-8").read(), originals["Side Bar.sublime-menu"])

i18n_mod._state["language"] = "en"
i18n_mod.apply_menu(force=True)

for name, original in originals.items():
    now = open(os.path.join(sandbox, name), encoding="utf-8").read()
    check("byte identical %s" % name, now == original, True)
check("overlay removed", sorted(os.listdir(overlay_dir)) if os.path.isdir(overlay_dir) else [], [])

check("backup dir created", os.path.isdir(backup_dir), True)

i18n_mod._state["language"] = "zh_CN"
i18n_mod.apply_menu(force=True)
i18n_mod.clear_applied_menu()
for name, original in originals.items():
    now = open(os.path.join(sandbox, name), encoding="utf-8").read()
    check("clear restores %s" % name, now == original, True)

i18n_mod._state["language"] = "en"
restored = i18n_mod._restore_all_menus()
check("restore idempotent", restored >= 0, True)

print("ROUNDTRIP_FAILURES", len(failures))
for item in failures:
    print(item)
shutil.rmtree(sandbox, ignore_errors=True)
shutil.rmtree(backup_dir, ignore_errors=True)