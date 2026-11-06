import ast
import json
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.normpath(os.path.join(ROOT, "..", "src")))


class PatchedOS(object):
    pass


def load_module(path, name):
    tree = ast.parse(open(path, encoding="utf-8").read())
    module = types.ModuleType(name)
    exec(compile(tree, path, "exec"), module.__dict__)
    return module


pkg = types.ModuleType("mysidebar")
pkg.__path__ = [os.path.abspath("mysidebar")]
sys.modules["mysidebar"] = pkg

i18n_stub = types.ModuleType("mysidebar.i18n")
i18n_stub.t = lambda key, **kw: key
sys.modules["mysidebar.i18n"] = i18n_stub
pkg.i18n = i18n_stub

platform_stub = types.ModuleType("mysidebar.platform")
platform_stub.normalize = lambda p: os.path.normpath(os.path.abspath(p))
platform_stub.same_path = lambda a, b: os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
sys.modules["mysidebar.platform"] = platform_stub

pkg.platform = platform_stub

failures = list()


def check(name, actual, expected):
    if actual != expected:
        failures.append("%s: got %r expected %r" % (name, actual, expected))


menu_file = "Context.sublime-menu"
check("empty ctx menu removed", os.path.isfile(menu_file), False)

strings_mod = load_module("mysidebar/strings.py", "mysidebar.strings")
caption_map = {v: k for k, v in strings_mod.STRINGS[strings_mod.DEFAULT_LANGUAGE].items() if k.endswith(".caption")}
i18n_src = open("mysidebar/i18n.py", encoding="utf-8").read()
check("menu target registered", '"Tab Sidebar Context.sublime-menu"' in i18n_src, True)
check("empty menu target dropped", '"Context.sublime-menu"' not in i18n_src, True)
check("rename strings removed", "rename." in open("mysidebar/strings.py", encoding="utf-8").read(), False)
check("rename setting removed", "batch_rename_max_items" in open("MySideBar.sublime-settings", encoding="utf-8").read(), False)

main_menu = json.load(open("Main.sublime-menu", "r", encoding="utf-8"))
main_captions = []


def _walk_menu(node):
    if isinstance(node, list):
        for item in node:
            _walk_menu(item)
        return
    if not isinstance(node, dict):
        return
    caption_text = node.get("caption")
    if isinstance(caption_text, str) and caption_text != "-":
        main_captions.append(caption_text)
    children = node.get("children")
    if children is not None:
        _walk_menu(children)


_walk_menu(main_menu)
EXEMPT_CAPTIONS = ("MySideBar", "English", "简体中文", "繁體中文")
missing_main = [c for c in main_captions if c not in caption_map and c not in EXEMPT_CAPTIONS]
check("main menu captions translatable", missing_main, [])

for lang in strings_mod.LANGUAGES:
    table = strings_mod.STRINGS[lang]
    for c in main_captions:
        key = caption_map.get(c)
        if key is not None and key not in table:
            failures.append("main menu caption missing %s in %s" % (key, lang))

lang_commands = [n["command"] for n in main_menu[0]["children"][1]["children"][3]["children"]]
check("main lang commands", lang_commands, ["my_sidebar_set_language"] * 3)
lang_args = [n["args"]["language"] for n in main_menu[0]["children"][1]["children"][3]["children"]]
check("main lang args", lang_args, list(strings_mod.LANGUAGES))
check("main settings uses edit_settings", main_menu[0]["children"][1]["children"][0]["command"], "edit_settings")
check("main settings has default", "default" in main_menu[0]["children"][1]["children"][0]["args"], True)
check("main settings base_file", main_menu[0]["children"][1]["children"][0]["args"]["base_file"], "${packages}/MySideBar/MySideBar.sublime-settings")

settings_src = open("mysidebar/cmds/settings.py", encoding="utf-8").read()
check("lang cmd is_enabled", "def is_enabled(self, language):" in settings_src, True)
check("lang cmd is_checked", "def is_checked(self, language):" in settings_src, True)
check("apply menus is_enabled", "def is_enabled(self):" in settings_src, True)

init_src = open("mysidebar/__init__.py", encoding="utf-8").read()
check("apply_menu unconditional", "i18n.apply_menu()" in init_src, True)
check("apply_menu not blocked by language", "return\n\n    i18n.apply_menu()" not in init_src, True)

check("shadow module removed", os.path.isfile("mysidebar/cmds/shadow.py"), False)
check("shadow setting removed", "menu_shadow_default_items" in open("MySideBar.sublime-settings", encoding="utf-8").read(), False)
check("shadow strings removed", "shadow." in open("mysidebar/strings.py", encoding="utf-8").read(), False)
check("no user menu write", "dst = os.path.join(target_dir, name)" in i18n_src, False)
check("user menu purge kept", "_remove_user_menus(_user_menu_dir())" in i18n_src, True)
check("menu backup helper", "def _ensure_backup(name, src_path):" in i18n_src, True)
check("menu restore helper", "def _restore_menu(name):" in i18n_src, True)
check("menu restore all", "def _restore_all_menus():" in i18n_src, True)
check("clear restores menus", "_restore_all_menus()\n    _remove_user_menus" in i18n_src, True)
check("menu writes user overlay", '"User", "MySideBar"' in i18n_src, True)
check("menu never rewrites package file", 'with open(src, "w"' not in i18n_src, True)

sidebar_menu = __import__("json").load(open("Side Bar.sublime-menu", encoding="utf-8"))
registered = set()
for dirpath, _, filenames in os.walk("mysidebar"):
    for filename in filenames:
        if not filename.endswith(".py"):
            continue
        full = os.path.join(dirpath, filename)
        tree = ast.parse(open(full, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            if not any(b.endswith("Command") for b in bases):
                continue
            name = node.name
            if not name.startswith("MySidebar") or not name.endswith("Command"):
                continue
            stem = name[len("MySidebar"):-len("Command")]
            snake = ""
            for i, ch in enumerate(stem):
                if ch.isupper() and i > 0:
                    snake += "_"
                snake += ch.lower()
            registered.add("my_sidebar_" + snake)
menu_commands = [n["command"] for n in sidebar_menu if n.get("command")]
missing = [c for c in menu_commands if c not in registered]
check("sidebar menu commands registered", missing, [])

check("no window method dialog", "window.show_ok_cancel_dialog" in "".join(open(os.path.join(d, f), encoding="utf-8").read() for d, _, fs in os.walk("mysidebar") for f in fs if f.endswith(".py")), False)

encoding_src = open("mysidebar/cmds/encoding.py", encoding="utf-8").read()
check("encoding no view buffer rewrite", "view.run_command(\"select_all\")" not in encoding_src, True)
check("encoding no view manual insert", "view.run_command(\"insert\"" not in encoding_src, True)
check("encoding source from user", 'source = getattr(self, "_source_encoding", None)' in encoding_src, True)
check("encoding no guessed source", "source = view.encoding()" not in encoding_src, True)
check("encoding byte decode", 'raw.decode(source_codec)' in encoding_src, True)
check("encoding byte encode", "text.encode(codec)" in encoding_src, True)
check("encoding honours target bom", "encodings.bom(target)" in encoding_src, True)
check("encoding auto detect source", 'source = encoding_detect.detect(item.path)' in encoding_src, True)
check("encoding writes bytes", "self._write_bytes(item.path, payload)" in encoding_src, True)
check("encoding reloads view", "self._reload_view(view, target)" in encoding_src, True)
check("encoding reopens view", "encodings.reopen_view(view, target)" in encoding_src, True)
check("encoding no revert", encoding_src.count('view.run_command("revert")'), 0)
check("encoding picks source", 'show_quick_panel(labels, self._on_source)' in encoding_src, True)
check("encoding picks target", 'show_quick_panel(labels, self._on_target)' in encoding_src, True)
check("encoding panel writer kept", "panel.run_command(\"insert\"" in encoding_src, True)

detect_src = open("mysidebar/encoding_detect.py", encoding="utf-8").read()
check("detect utf8 first", 'if _clean_utf8(raw):' in detect_src, True)
check(
    "detect single candidate fallback",
    'sample.decode(spec.py_codec, "strict")' in detect_src and "def _trusted(raw, spec)" in detect_src,
    True,
)
check(
    "detect refuses ambiguous candidate set",
    "if len(candidates) != 1:" in detect_src,
    True,
)
check(
    "detect caches by stat",
    "_cached(key, mtime, size)" in detect_src and "_UNKNOWN" in detect_src,
    True,
)
check(
    "detect rejects implausible gb18030",
    "_text_is_plausible(text)" in detect_src,
    True,
)
check(
    "detect guards pua noise",
    "_PUA_RATIO_MAX" in detect_src,
    True,
)
check("detect binary guard", "if _looks_binary(raw):" in detect_src, True)
check("detect bom guard", "_bom_encoding(raw)" in detect_src, True)
check("detect has no dead dedupe", "should_reopen" not in detect_src, True)
check("detect has no view id cache", "_processed" not in detect_src, True)
check("detect size guard", "size > MAX_BYTES" in detect_src, True)

listener_src = open("mysidebar/listener.py", encoding="utf-8").read()
check("listener auto detect", "on_load_async" in listener_src, True)
check("listener hooks sync load", "def on_load(self, view):" in listener_src, True)
check("listener delegates reopen", "encodings.reopen_view(view, name)" in listener_src, True)
check("listener no set_encoding", "set_encoding" not in listener_src, True)
check("listener no buffer replace", "view.replace(edit" not in listener_src, True)
check("listener avoids revert", '"revert"' not in listener_src, True)
check("listener no latin1 channel", 'BYTE_CHANNEL = "latin-1"' not in listener_src, True)
check(
    "listener has no temp files",
    "TEMP_SUFFIX" not in listener_src,
    True,
)
check("listener respects switch", 'get("auto_detect_encoding", True)' in listener_src, True)
check("listener dedupes by path", "_handled.get(_key(view)) == name" in listener_src, True)
check("listener guards concurrent kicks", "if key is None or _busy(key):" in listener_src, True)
check(
    "listener verifies reopen result",
    "view.encoding() != name" in listener_src,
    True,
)
check(
    "listener limits verify retries",
    "VERIFY_LIMIT" in listener_src,
    True,
)
check(
    "listener limits settle retries",
    "SETTLE_LIMIT" in listener_src,
    True,
)
check(
    "listener skips scratch",
    "view.is_scratch()" in listener_src,
    True,
)
check("listener clears state on close", "def on_close(self, view):" in listener_src, True)

encodings_src = open("mysidebar/encodings.py", encoding="utf-8").read()
check("encodings registry present", "_SOURCE =" in encodings_src, True)
check(
    "encodings reopen uses verified arg",
    '"Chinese (GB18030)"' in encodings_src,
    True,
)
check("encodings reopen command", 'view.run_command("reopen", {"encoding": arg})' in encodings_src, True)
check(
    "encodings reopen arg equals display name",
    "return name" in encodings_src,
    True,
)

encoding_cmd_src = open("mysidebar/cmds/encoding.py", encoding="utf-8").read()
check(
    "encoding cmd reloads via reopen",
    "encodings.reopen_view(view, target)" in encoding_cmd_src,
    True,
)
check("encoding cmd drops revert", '"revert"' not in encoding_cmd_src, True)

api_src = open("mysidebar/api.py", encoding="utf-8").read()
check("api has no dead encoding helper", "set_encoding_checked" not in api_src, True)

doctor_src = open("mysidebar/cmds/doctor.py", encoding="utf-8").read()
check("doctor uses reopen", "encodings.reopen_arg(detected)" in doctor_src, True)
check("doctor drops set_encoding", "view.set_encoding(" not in doctor_src, True)
check("doctor report dir derived", 'REPORT_DIR = "/Volumes' not in doctor_src, True)

init_src = open("mysidebar/__init__.py", encoding="utf-8").read()
check("package keeps plugin hooks", "def on_plugin_loaded():" in init_src, True)
check("package no manual listener load", "_load_listener" not in init_src, True)

entry_src = open("MySideBar.py", encoding="utf-8").read()
check("entry walks whole package", "pkgutil.walk_packages(package.__path__" in entry_src, True)
check("entry exports by module name", "attr_value.__module__ != info.name" in entry_src, True)
check("entry exports listeners", "EventListener," in entry_src, True)
check("entry guards import failure", 'print("[MySideBar] failed to import %s" % info.name)' in entry_src, True)

settings_src = open("MySideBar.sublime-settings", encoding="utf-8").read()
check("auto detect setting", '"auto_detect_encoding": true' in settings_src, True)

strings_src = open("mysidebar/strings.py", encoding="utf-8").read()
check("auto detected string", "encoding.auto_detected" in strings_src, True)

print("failures", len(failures))
for item in failures:
    print(item)
sys.exit(1 if failures else 0)